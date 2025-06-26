from django.db import models
from django.conf import settings  # Ajouté pour AUTH_USER_MODEL
from django.utils import timezone
from store.models import Product
from django.contrib.auth import get_user_model

User = get_user_model()

class UserModeration(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='moderations')
    moderator = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='moderated_users')
    action = models.CharField(max_length=50, choices=[('ban', 'Ban'), ('warn', 'Warning'), ('unban', 'Unban')], help_text="Action prise")
    reason = models.TextField(help_text="Raison de la modération")
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.user.username} - {self.action} ({self.created_at})"

class ProductModeration(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='moderations')
    moderator = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='moderated_products')
    status = models.CharField(max_length=20, choices=[('pending', 'En attente'), ('approved', 'Approuvé'), ('rejected', 'Rejeté')], default='pending')
    reason = models.TextField(blank=True, help_text="Raison du rejet ou commentaire")
    created_at = models.DateTimeField(default=timezone.now)
    approved_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.product.name} - {self.status} ({self.created_at})"
    






class Report(models.Model):
    STATUS_CHOICES = [
        ('open', 'Ouvert'),
        ('resolved', 'Résolu'),
        ('dismissed', 'Rejeté'),
    ]
    reporter = models.ForeignKey(User, related_name='reports_made', on_delete=models.CASCADE)
    user = models.ForeignKey(User, related_name='reports_received', on_delete=models.CASCADE, null=True, blank=True)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, null=True, blank=True)
    reason = models.CharField(max_length=100)
    description = models.TextField(default='', blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Report {self.id} - {self.product.name if self.product else 'No product'}"