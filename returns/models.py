from django.db import models
from django.conf import settings
from store.models import Order
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from datetime import timedelta

class ReturnRequest(models.Model):
    STATUS_CHOICES = (
        ('PENDING', 'En attente'),
        ('APPROVED', 'Approuvé'),
        ('REJECTED', 'Rejeté'),
        ('COMPLETED', 'Terminé'),
    )

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='return_requests')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='return_requests')
    reason = models.TextField(max_length=500, help_text="Raison du retour")
    image = models.ImageField(upload_to='returns/images/', blank=True, null=True, help_text="Photo du produit retourné")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    rejection_reason = models.TextField(blank=True, null=True, help_text="Raison du rejet, si applicable")

    def clean(self):
        if not hasattr(self, 'order') or self.order is None:
            return  # Skip validation if order is not set yet
        # Vérifier que la demande de retour est soumise dans les 30 jours après la création de la commande
        max_return_period = self.order.created_at + timedelta(days=30)
        if self.created_at and self.created_at > max_return_period:
            raise ValidationError(
                "Les demandes de retour doivent être soumises dans les 30 jours suivant la date de la commande."
            )
        super().clean()

    def __str__(self):
        return f"Retour #{self.id} pour la commande #{self.order.id} ({self.status})"

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Demande de retour"
        verbose_name_plural = "Demandes de retour"

class Refund(models.Model):
    METHOD_CHOICES = (
        ('card', 'Carte de crédit'),
        ('paypal', 'PayPal'),
        ('sepa', 'Virement SEPA'),
    )
    STATUS_CHOICES = (
        ('PENDING', 'En attente'),
        ('COMPLETED', 'Terminé'),
        ('FAILED', 'Échoué'),
    )

    return_request = models.OneToOneField(ReturnRequest, on_delete=models.CASCADE, related_name='refund')
    amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    method = models.CharField(max_length=20, choices=METHOD_CHOICES)
    transaction_id = models.CharField(max_length=100, blank=True, null=True, help_text="ID de la transaction de remboursement")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def clean(self):
        if self.return_request and self.return_request.order:
            if self.method != self.return_request.order.payment_method:
                raise ValidationError(
                    f"La méthode de remboursement ({self.method}) doit correspondre à la méthode de paiement de la commande ({self.return_request.order.payment_method})."
                )
        super().clean()

    def __str__(self):
        return f"Remboursement #{self.id} pour retour #{self.return_request.id} ({self.amount} €)"

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Remboursement"
        verbose_name_plural = "Remboursements"