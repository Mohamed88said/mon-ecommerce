from django.db import models
from django.conf import settings
from django.utils import timezone
from decimal import Decimal
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db.models.signals import post_save
from django.dispatch import receiver

# === Modèle Category ===
class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True)

    def __str__(self):
        return self.name

# === Modèle Discount ===
class Discount(models.Model):
    product = models.ForeignKey('Product', on_delete=models.CASCADE, related_name='discounts')
    percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Pourcentage de réduction (0-100)"
    )
    start_date = models.DateTimeField(help_text="Date de début de la réduction")
    end_date = models.DateTimeField(help_text="Date de fin de la réduction")
    is_active = models.BooleanField(default=True, help_text="Indique si la réduction est active")

    def clean(self):
        if self.start_date and self.end_date and self.start_date >= self.end_date:
            raise ValidationError("La date de fin doit être postérieure à la date de début.")
        if self.percentage <= 0 or self.percentage > 100:
            raise ValidationError("Le pourcentage de réduction doit être entre 0 et 100.")
        super().clean()

    def __str__(self):
        return f"Réduction {self.percentage}% sur {self.product.name}"

# === Modèle Product ===
class Product(models.Model):
    SIZE_CHOICES = [
        ('', 'Select Size'),
        ('XS', 'Extra Small'),
        ('S', 'Small'),
        ('M', 'Medium'),
        ('L', 'Large'),
        ('XL', 'Extra Large'),
        ('XXL', 'Double Extra Large'),
        ('XXXL', 'Triple Extra Large'),
        ('One Size', 'One Size Fits All'),
        ('Custom', 'Custom Size'),
        ('Free Size', 'Free Size'),
        ('Adjustable', 'Adjustable Size'),
        ('Petite', 'Petite Size'),
        ('Tall', 'Tall Size'),
        ('Plus Size', 'Plus Size'),
        ('Big and Tall', 'Big and Tall'),
        ('Junior', 'Junior Size'),
        ('Maternity', 'Maternity Size'),
        ('Kids', 'Kids Size'),
        ('Infant', 'Infant Size'),
    ]

    seller = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='products')
    category = models.ForeignKey('Category', on_delete=models.SET_NULL, null=True, blank=True)
    name = models.CharField(max_length=255)
    description = models.TextField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    stock = models.PositiveIntegerField()
    image1 = models.ImageField(upload_to='products/', blank=True, null=True)
    image2 = models.ImageField(upload_to='products/', blank=True, null=True)
    image3 = models.ImageField(upload_to='products/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    views = models.PositiveIntegerField(default=0)
    sales_count = models.PositiveIntegerField(default=0, help_text="Nombre total d'unités vendues")
    is_sold = models.BooleanField(default=False)
    sold_out = models.BooleanField(default=False)
    size = models.CharField(max_length=20, choices=SIZE_CHOICES, blank=True, null=True, help_text="Taille du produit")
    brand = models.CharField(max_length=100, blank=True, null=True, help_text="Marque du produit")
    color = models.CharField(max_length=50, blank=True, null=True, help_text="Couleur du produit")
    material = models.CharField(max_length=100, blank=True, null=True, help_text="Matériau du produit")

    def __str__(self):
        return self.name

    @property
    def discounted_price(self):
        current_time = timezone.now()
        active_discount = self.discounts.filter(is_active=True, start_date__lte=current_time, end_date__gte=current_time).order_by('-percentage').first()
        if active_discount:
            discount_amount = self.price * (active_discount.percentage / Decimal('100'))
            return self.price - discount_amount
        return self.price

    @property
    def active_discount_percentage(self):
        current_time = timezone.now()
        active_discount = self.discounts.filter(is_active=True, start_date__lte=current_time, end_date__gte=current_time).order_by('-percentage').first()
        return active_discount.percentage if active_discount else 0

    @property
    def active_discount_end_date(self):
        current_time = timezone.now()
        active_discount = self.discounts.filter(is_active=True, start_date__lte=current_time, end_date__gte=current_time).order_by('-percentage').first()
        return active_discount.end_date if active_discount else None

    @property
    def is_sold_out(self):
        return self.stock == 0 or self.is_sold or self.sold_out

    @property
    def average_rating(self):
        reviews = self.reviews.all()
        if reviews.exists():
            return round(sum(review.rating for review in reviews) / reviews.count(), 1)
        return 0

    class Meta:
        verbose_name = "Produit"
        verbose_name_plural = "Produits"

# === Modèles Cart et CartItem ===
class Cart(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Cart of {self.user.username}"

class CartItem(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)

    def __str__(self):
        return f"{self.quantity} x {self.product.name}"

    @property
    def subtotal(self):
        return self.quantity * self.product.discounted_price

# === Modèle ShippingOption ===
class ShippingOption(models.Model):
    name = models.CharField(max_length=100)
    cost = models.DecimalField(max_digits=10, decimal_places=2)
    estimated_days = models.PositiveIntegerField()
    is_active = models.BooleanField(default=True)
    description = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.name} - {self.cost}€ ({self.estimated_days} jours)"

# === Modèle Address ===
class Address(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='addresses')
    full_name = models.CharField(max_length=100)
    street_address = models.CharField(max_length=255)
    city = models.CharField(max_length=100)
    postal_code = models.CharField(max_length=20)
    country = models.CharField(max_length=100)
    phone_number = models.CharField(max_length=20, blank=True)
    is_default = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.full_name}, {self.street_address}, {self.city}, {self.postal_code}, {self.country}"

    def save(self, *args, **kwargs):
        if self.is_default:
            Address.objects.filter(user=self.user, is_default=True).exclude(id=self.id).update(is_default=False)
        super().save(*args, **kwargs)

# === Modèles Order et OrderItem ===
class Order(models.Model):
    STATUS_CHOICES = [
        ('pending', 'En attente'),
        ('processing', 'En cours de traitement'),
        ('shipped', 'Expédié'),
        ('delivered', 'Livré'),
        ('cancelled', 'Annulé'),
    ]
    PAYMENT_METHODS = [
        ('card', 'Carte de crédit'),
        ('cod', 'Paiement à la livraison'),
        ('paypal', 'PayPal'),
        ('sepa', 'Virement SEPA'),
    ]
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='orders')
    seller = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='orders_sold')  # Restauré
    total = models.DecimalField(max_digits=10, decimal_places=2)
    shipping_address = models.ForeignKey(Address, on_delete=models.SET_NULL, null=True, blank=True)
    shipping_option = models.ForeignKey(ShippingOption, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHODS, default='card')
    charge_id = models.CharField(max_length=100, null=True, blank=True, help_text="ID de la charge Stripe pour le paiement")

    def __str__(self):
        return f"Order {self.id} by {self.user.username}"

class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    seller = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='order_items')  # Conserver ce champ

    def __str__(self):
        return f"{self.quantity} x {self.product.name} in Order {self.order.id}"

# === Extension de SellerProfile ===
class SellerProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='seller_profile')
    first_name = models.CharField(max_length=100, blank=True, null=True)
    last_name = models.CharField(max_length=100, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    business_name = models.CharField(max_length=200, blank=True, null=True)
    business_address = models.CharField(max_length=255, blank=True, null=True)
    contact_phone = models.CharField(max_length=20, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    profile_picture = models.ImageField(upload_to='profile_pictures/', blank=True, null=True)

    def __str__(self):
        return f"Profil de {self.user.username}"

# === Modèle Favorite ===
class Favorite(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    product = models.ForeignKey('Product', on_delete=models.CASCADE)
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'product')

    def __str__(self):
        return f"{self.user.username} a favorisé {self.product.name}"

# === Modèle Review ===
class Review(models.Model):
    product = models.ForeignKey('Product', on_delete=models.CASCADE, related_name='reviews')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    rating = models.PositiveIntegerField(choices=[(i, str(i)) for i in range(1, 6)])
    comment = models.TextField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    reply = models.TextField(max_length=500, blank=True, null=True)
    is_approved = models.BooleanField(default=False, help_text="Indique si l'avis est approuvé par le vendeur")

    class Meta:
        unique_together = ('product', 'user')
        ordering = ['-created_at']

    def __str__(self):
        return f"Avis de {self.user.username} sur {self.product.name} ({self.rating}/5)"

# === Modèle ProductRequest ===
class ProductRequest(models.Model):
    product = models.ForeignKey('Product', on_delete=models.CASCADE, related_name='requests')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='product_requests', null=True, blank=True)
    email = models.EmailField(blank=True, null=True)
    message = models.TextField(blank=True, null=True)
    desired_quantity = models.PositiveIntegerField(default=1)
    desired_date = models.DateField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_notified = models.BooleanField(default=False, help_text="Indique si le vendeur a été notifié ou a répondu")

    def __str__(self):
        return f"Demande de {self.user.username if self.user else self.email} pour {self.product.name}"

# === Modèle ProductView ===
class ProductView(models.Model):
    product = models.ForeignKey('Product', on_delete=models.CASCADE, related_name='product_views')
    view_date = models.DateTimeField(auto_now_add=True)
    view_count = models.PositiveIntegerField(default=1)

    class Meta:
        unique_together = ('product', 'view_date')

    def __str__(self):
        return f"{self.product.name} vu le {self.view_date.strftime('%Y-%m-%d')} ({self.view_count} vues)"

# === Modèle Notification ===
class Notification(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notifications')
    notification_type = models.CharField(max_length=50)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)
    related_object_id = models.PositiveIntegerField(null=True, blank=True, help_text="ID de l'objet lié")

    def __str__(self):
        return f"Notification pour {self.user.username}: {self.message[:50]}..."

    class Meta:
        ordering = ['-created_at']

# === Modèles Conversation et Message ===
class Conversation(models.Model):
    initiator = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='conversations_initiated')
    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='conversations_received')
    product = models.ForeignKey('Product', on_delete=models.CASCADE, related_name='conversations')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('initiator', 'recipient', 'product')

    def __str__(self):
        return f"Conversation entre {self.initiator} et {self.recipient}"

class Message(models.Model):
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    content = models.TextField()
    sent_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)

    class Meta:
        ordering = ['sent_at']

    def __str__(self):
        return f"Message de {self.sender}"

# === Modèle SellerRating ===
class SellerRating(models.Model):
    seller = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='ratings_received')
    rater = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='ratings_given')
    order = models.ForeignKey('Order', on_delete=models.CASCADE, related_name='ratings')
    rating = models.PositiveIntegerField(choices=[(i, i) for i in range(1, 6)])
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('seller', 'rater', 'order')

    def __str__(self):
        return f"Note {self.rating}/5 par {self.rater}"

# === Modèle UserProductView ===
class UserProductView(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    product = models.ForeignKey('Product', on_delete=models.CASCADE, related_name='user_views')
    view_date = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'product', 'view_date')

    def __str__(self):
        return f"{self.user} a vu {self.product}"

# === Modèle Subscription ===
class Subscription(models.Model):
    PLAN_CHOICES = [
        ('free', 'Gratuit'),
        ('basic', 'Basique'),
        ('pro', 'Professionnel'),
    ]
    
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='subscription')
    plan = models.CharField(max_length=10, choices=PLAN_CHOICES, default='free')
    stripe_subscription_id = models.CharField(max_length=100, blank=True, null=True)
    start_date = models.DateTimeField(auto_now_add=True)
    end_date = models.DateTimeField(blank=True, null=True)
    active = models.BooleanField(default=False)

    def __str__(self):
        return f"Abonnement {self.plan} de {self.user}"

# === Signal pour attribuer automatiquement le seller à l'Order ===
@receiver(post_save, sender=Order)
def set_order_seller(sender, instance, created, **kwargs):
    if created and not instance.seller:  # Si c'est une nouvelle commande et que seller n'est pas défini
        # Récupère le seller du premier OrderItem
        first_item = instance.items.first()
        if first_item and first_item.product and first_item.product.seller:
            instance.seller = first_item.product.seller
            instance.save(update_fields=['seller'])
        else:
            print(f"Aucun seller trouvé pour l'Order {instance.id}. Vérifiez les produits associés.")