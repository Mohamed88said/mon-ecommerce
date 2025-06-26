
from django.db import models
from django.contrib.auth.models import AbstractUser

class CustomUser(AbstractUser):
    USER_TYPE_CHOICES = (
        ('buyer', 'Acheteur'),
        ('seller', 'Vendeur'),
    )
    user_type = models.CharField(max_length=10, choices=USER_TYPE_CHOICES, default='buyer')
    email = models.EmailField(unique=True)

class Profile(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE)
    address = models.TextField(blank=True, verbose_name="Adresse principale")
    phone = models.CharField(max_length=15, blank=True, verbose_name="Téléphone")
    profile_picture = models.ImageField(upload_to='profile_pics/', blank=True, null=True, verbose_name="Photo de profil")
    description = models.TextField(blank=True, verbose_name="Description (pour vendeurs)", help_text="Décrivez votre boutique ou vos services.")

    def __str__(self):
        return f"Profil de {self.user.username}"

class Address(models.Model):
    profile = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name='addresses')
    address_line1 = models.CharField(max_length=255, verbose_name="Ligne d'adresse 1")
    address_line2 = models.CharField(max_length=255, blank=True, verbose_name="Ligne d'adresse 2")
    city = models.CharField(max_length=100, verbose_name="Ville")
    postal_code = models.CharField(max_length=20, verbose_name="Code postal")
    country = models.CharField(max_length=100, verbose_name="Pays")
    is_default = models.BooleanField(default=False, verbose_name="Adresse par défaut")

    def __str__(self):
        return f"{self.address_line1}, {self.city}, {self.country}"
    
    