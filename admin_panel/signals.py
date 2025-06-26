from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from .models import Report
from store.models import Notification

User = get_user_model()

@receiver(post_save, sender=Report)
def check_report_count(sender, instance, created, **kwargs):
    """
    Vérifie si un utilisateur a 10 signalements ouverts après la création d'un nouveau signalement.
    Si oui, désactive le compte de l'utilisateur, envoie une notification à l'utilisateur et aux admins.
    Envoie également une notification anonyme au vendeur à chaque signalement.
    """
    if created and instance.user:  # Vérifie que le signalement est nouveau et concerne un utilisateur
        # Notification anonyme au vendeur signalé
        Notification.objects.create(
            user=instance.user,
            message=f"Votre compte a été signalé pour : {instance.reason}",
            notification_type='report_received',
            related_object_id=instance.id
        )

        # Vérification des signalements pour désactivation
        open_reports = Report.objects.filter(user=instance.user, status='open').count()
        if open_reports >= 10:
            user = instance.user
            user.is_active = False
            user.save()
            # Notification à l'utilisateur désactivé
            Notification.objects.create(
                user=user,
                message="Votre compte a été désactivé en raison de 10 signalements ouverts.",
                notification_type='account_deactivation',
                related_object_id=instance.id
            )
            # Notification à tous les admins
            for admin in User.objects.filter(is_staff=True):
                Notification.objects.create(
                    user=admin,
                    message=f"Le compte de {user.username} a été désactivé pour 10 signalements ouverts.",
                    notification_type='account_deactivation_alert',
                    related_object_id=instance.id
                )