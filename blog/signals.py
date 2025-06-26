from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.mail import send_mail
from django.conf import settings
from .models import Comment

@receiver(post_save, sender=Comment)
def send_comment_notification(sender, instance, created, **kwargs):
    if created and not instance.is_approved:
        subject = f"Nouveau commentaire en attente sur {instance.post.title}"
        message = (
            f"Un nouveau commentaire a été soumis sur l'article '{instance.post.title}'.\n\n"
            f"Contenu : {instance.content}\n"
            f"Auteur : {instance.author.username}\n"
            f"Date : {instance.created_at}\n\n"
            f"Approuver ce commentaire dans l'admin : "
            f"{settings.SITE_URL}/admin/blog/comment/{instance.id}/change/\n"
        )
        from_email = settings.DEFAULT_FROM_EMAIL
        recipient_list = settings.ADMIN_EMAILS  # Liste des emails d'admins
        send_mail(
            subject,
            message,
            from_email,
            recipient_list,
            fail_silently=True,  # Ne bloque pas si l'email échoue
        )