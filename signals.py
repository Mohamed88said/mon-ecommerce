from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from .models import AIPreferences, Order, ProductRequest, OrderItem

@receiver(post_save, sender=User)
def create_ai_preferences(sender, instance, created, **kwargs):
    if created:
        AIPreferences.objects.create(user=instance)

@receiver(post_save, sender=Order)
def update_product_sales(sender, instance, created, **kwargs):
    if created and instance.status == 'delivered':
        for item in instance.items.all():
            if item.product:
                item.product.sales_count += item.quantity
                item.product.save()

@receiver(post_save, sender=ProductRequest)
def update_product_views(sender, instance, created, **kwargs):
    if created:
        instance.product.views += 1
        instance.product.save()