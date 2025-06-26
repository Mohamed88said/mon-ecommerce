from django.contrib import admin
from .models import Product, Category, Cart, CartItem, Address, ShippingOption, Order, OrderItem, Favorite, Review, Notification, ProductView, ProductRequest
from marketing.admin import admin_site  # Importe admin_site depuis marketing

@admin.register(Product, site=admin_site)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['name', 'seller', 'category', 'price', 'stock', 'size', 'brand', 'color', 'material']
    list_filter = ['category', 'seller', 'size', 'brand', 'color', 'material']
    search_fields = ['name', 'description', 'brand', 'color', 'material']
    fieldsets = (
        (None, {
            'fields': ('seller', 'category', 'name', 'description', 'price', 'stock')
        }),
        ('Images', {
            'fields': ('image1', 'image2', 'image3')
        }),
        ('Détails supplémentaires', {
            'fields': ('size', 'brand', 'color', 'material')
        }),
        ('Statut et réduction', {
            'fields': ('discount_percentage', 'is_sold', 'sold_out')
        }),
    )

@admin.register(Category, site=admin_site)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug']
    search_fields = ['name']

@admin.register(Cart, site=admin_site)
class CartAdmin(admin.ModelAdmin):
    list_display = ['user', 'created_at']

@admin.register(CartItem, site=admin_site)
class CartItemAdmin(admin.ModelAdmin):
    list_display = ['cart', 'product', 'quantity']

@admin.register(Address, site=admin_site)
class AddressAdmin(admin.ModelAdmin):
    list_display = ['user', 'full_name', 'city', 'postal_code', 'is_default']

@admin.register(ShippingOption, site=admin_site)
class ShippingOptionAdmin(admin.ModelAdmin):
    list_display = ['name', 'cost', 'estimated_days', 'is_active']

@admin.register(Order, site=admin_site)
class OrderAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'seller', 'total', 'status', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['id', 'user__username', 'seller__username']
    date_hierarchy = 'created_at'
    readonly_fields = ['created_at', 'updated_at']  # Ajouté comme champs en lecture seule
    fieldsets = (
        ('Informations de base', {
            'fields': ('user', 'seller', 'total', 'shipping_address', 'shipping_option', 'status', 'payment_method')
        }),
        ('Dates (lecture seule)', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

@admin.register(OrderItem, site=admin_site)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ['order', 'product', 'quantity', 'price']

@admin.register(Favorite, site=admin_site)
class FavoriteAdmin(admin.ModelAdmin):
    list_display = ['user', 'product', 'added_at']

@admin.register(Review, site=admin_site)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ['product', 'user', 'rating', 'created_at']

@admin.register(Notification, site=admin_site)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ['user', 'notification_type', 'created_at', 'is_read']

@admin.register(ProductView, site=admin_site)
class ProductViewAdmin(admin.ModelAdmin):
    list_display = ['product', 'view_date', 'view_count']

@admin.register(ProductRequest, site=admin_site)
class ProductRequestAdmin(admin.ModelAdmin):
    list_display = ['product', 'user', 'email', 'message', 'desired_quantity', 'desired_date', 'created_at']
    list_filter = ['product', 'user']
    search_fields = ['product__name', 'email', 'message']
    readonly_fields = ['created_at']