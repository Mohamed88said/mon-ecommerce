from django.db.models.signals import post_save
from django.dispatch import receiver
from returns.models import ReturnRequest
from store.models import Notification
from django.core.mail import send_mail
from django.conf import settings
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
import logging

logger = logging.getLogger(__name__)

@receiver(post_save, sender=ReturnRequest)
def notify_seller_of_return_request(sender, instance, created, **kwargs):
    if created:
        order = instance.order
        sellers = set(item.product.seller for item in order.items.all() if item.product and item.product.seller)
        if not sellers:
            logger.warning(f"Aucun seller trouvé pour l'Order {order.id}. Vérifiez les produits associés.")
            return
        
        for seller in sellers:
            try:
                # Notification par email
                send_mail(
                    subject=f'Nouvelle demande de retour #{instance.id}',
                    message=f'Une demande de retour a été soumise pour la commande #{order.id}. Raison : {instance.reason}. Veuillez examiner la demande.',
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[seller.email],
                    fail_silently=True,
                )
                # Notification en base de données
                Notification.objects.create(
                    user=seller,
                    message=f"Une demande de retour a été soumise pour la commande #{order.id}.",
                    notification_type='return_request',
                    related_object_id=instance.id
                )
                # Notification WebSocket
                channel_layer = get_channel_layer()
                async_to_sync(channel_layer.group_send)(
                    f'notifications_{seller.id}',
                    {
                        'type': 'new_notification',
                        'message': f"Nouvelle demande de retour #{instance.id} pour la commande #{order.id}",
                        'notification_type': 'return_request',
                        'timestamp': instance.created_at.isoformat()
                    }
                )
                logger.info(f"Notifications (email et WebSocket) envoyées au vendeur {seller.username} pour la demande de retour #{instance.id}")
            except Exception as e:
                logger.error(f"Erreur lors de l'envoi des notifications pour la demande #{instance.id}: {str(e)}")