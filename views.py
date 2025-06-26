from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q, Sum, Avg, F, ExpressionWrapper, DecimalField
from django.db import transaction
from django.contrib.auth import get_user_model
import stripe
import requests
import paypalrestsdk
from django.conf import settings
from .models import Product, ProductView, Cart, CartItem, Order, OrderItem, Favorite, Category, Review, Notification, Address, ShippingOption, SellerProfile, Conversation, Message, SellerRating, UserProductView, Subscription, ProductRequest, Discount
import logging
from .forms import ProductForm, OrderStatusForm, ReviewForm, AddressForm, ApplyDiscountForm, SellerProfileForm, ProductRequestForm, ReportForm, ShippingMethodForm
from django.db import OperationalError, IntegrityError
from django.http import HttpResponse, JsonResponse
import json
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.utils import timezone
from django.urls import reverse
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from datetime import date, timedelta
from marketing.models import LoyaltyPoint, PromoCode
from admin_panel.models import ProductModeration
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views import View
from returns.models import ReturnRequest
from returns.forms import ReturnRequestForm
from delivery.forms import LocationForm
from delivery.models import Delivery, Location
from delivery.utils import get_exif_data, get_gps_info

# Configurer le logging
logger = logging.getLogger(__name__)

stripe.api_key = settings.STRIPE_SECRET_KEY

# Configurer PayPal pour les paiements
paypalrestsdk.configure({
    "mode": "sandbox" if settings.DEBUG else "live",
    "client_id": settings.PAYPAL_CLIENT_ID,
    "client_secret": settings.PAYPAL_CLIENT_SECRET
})

# Fonction pour vérifier si l'utilisateur est un vendeur
def is_seller(user):
    return user.is_authenticated and getattr(user, 'user_type', '') == 'seller'

def home(request):
    try:
        categories = Category.objects.values_list('name', flat=True)
    except OperationalError:
        categories = []
    unread_notifications = 0
    if request.user.is_authenticated:
        unread_notifications = request.user.notifications.filter(is_read=False).count()
    return render(request, 'home.html', {
        'categories': categories,
        'unread_notifications': unread_notifications
    })

def product_list(request, category_slug=None):
    # Récupération des paramètres de filtrage
    query = request.GET.get('q', '')
    category_name = request.GET.get('category', '')
    price_min = request.GET.get('price_min', '')
    price_max = request.GET.get('price_max', '')
    in_stock = request.GET.get('in_stock', '')
    sort_by = request.GET.get('sort_by', 'default')
    size_filter = request.GET.get('size', '')
    brand_filter = request.GET.get('brand', '')
    color_filter = request.GET.get('color', '')
    material_filter = request.GET.get('material', '')

    # Base queryset - Filtre uniquement les produits approuvés
    products = Product.objects.filter(
        sold_out=False,
        is_sold=False,
    ).select_related('category')

    # Filtre pour les produits approuvés
    approved_product_ids = ProductModeration.objects.filter(status='approved').values_list('product_id', flat=True)
    products = products.filter(id__in=approved_product_ids)

    # Filtrage par recherche
    if query:
        products = products.filter(
            Q(name__icontains=query) | 
            Q(description__icontains=query) | 
            Q(brand__icontains=query) | 
            Q(color__icontains=query) | 
            Q(material__icontains=query)
        )

    # Filtrage par catégorie
    selected_category = ''
    if category_slug:
        try:
            category = get_object_or_404(Category, slug=category_slug)
            products = products.filter(category=category)
            selected_category = category.name
        except OperationalError:
            pass
    elif category_name:
        try:
            category = Category.objects.filter(name__iexact=category_name).first()
            if category:
                products = products.filter(category=category)
                selected_category = category.name
        except OperationalError:
            pass

    # Filtrage par prix
    try:
        if price_min:
            products = products.filter(price__gte=float(price_min))
        if price_max:
            products = products.filter(price__lte=float(price_max))
    except ValueError:
        pass

    # Filtrage par stock
    if in_stock == 'yes':
        products = products.filter(stock__gt=0)
    elif in_stock == 'no':
        products = products.filter(stock=0)

    # Filtres supplémentaires
    filter_mapping = {
        'size': size_filter,
        'brand__icontains': brand_filter,
        'color__icontains': color_filter,
        'material__icontains': material_filter
    }
    
    for field, value in filter_mapping.items():
        if value:
            products = products.filter(**{field: value})

    # Tri
    sort_options = {
        'price_asc': 'price',
        'price_desc': '-price',
        'views_desc': '-view_count',
        'date_desc': '-created_at',
        'date_asc': 'created_at'
    }
    products = products.order_by(sort_options.get(sort_by, 'id'))

    # Pagination
    paginator = Paginator(products, settings.PRODUCTS_PER_PAGE)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    now = timezone.now()
    # Préparation des données pour le template
    context = {
        'page_obj': page_obj,
        'categories': Category.objects.all(),
        'query': query,
        'selected_category': selected_category,
        'price_min': price_min,
        'price_max': price_max,
        'in_stock': in_stock,
        'sort_by': sort_by,
        'size_filter': size_filter,
        'brand_filter': brand_filter,
        'color_filter': color_filter,
        'material_filter': material_filter,
        'product_sizes': Product.SIZE_CHOICES,
        'now': timezone.now()
    }

    return render(request, 'store/product_list.html', context)

def product_detail(request, product_id):
    # Récupération du produit et mise à jour des vues
    product = get_object_or_404(Product, id=product_id)
    product.views += 1
    product.save()

    # Enregistrement de la vue dans ProductView (stats journalières)
    today = date.today()
    product_view, created = ProductView.objects.get_or_create(
        product=product,
        view_date=today,
        defaults={'view_count': 1}
    )
    if not created:
        product_view.view_count += 1
        product_view.save()

    # Enregistrement de la vue utilisateur si authentifié
    if request.user.is_authenticated:
        UserProductView.objects.create(user=request.user, product=product)

    # Gestion des favoris
    favorite_count = Favorite.objects.filter(product=product).count()
    is_favorite = Favorite.objects.filter(user=request.user, product=product).exists() if request.user.is_authenticated else False

    # Calcul de la note moyenne
    average_rating = product.reviews.aggregate(Avg('rating'))['rating__avg'] or 0

    # Gestion des avis
    reviews = product.reviews.all().order_by('-created_at')
    can_review = False
    has_reviewed = False
    
    if request.user.is_authenticated:
        has_reviewed = Review.objects.filter(product=product, user=request.user).exists()
        if request.user.user_type == 'buyer':
            has_purchased = OrderItem.objects.filter(
                order__user=request.user,
                product=product,
                order__status='delivered'
            ).exists()
            can_review = has_purchased and not has_reviewed

    # Traitement du formulaire d'avis
    if request.method == 'POST' and can_review:
        review_form = ReviewForm(request.POST)
        if request.user.user_type != 'buyer':
            messages.error(request, "Seuls les acheteurs peuvent laisser un avis.")
            return redirect('store:product_detail', product_id=product.id)
        if review_form.is_valid():
            review = review_form.save(commit=False)
            review.product = product
            review.user = request.user
            review.save()
            Notification.objects.create(
                user=product.seller,
                message=f"Un nouvel avis a été laissé sur votre produit '{product.name}' par {request.user.username}.",
                notification_type='review_added',
                related_object_id=product.id
            )
            logger.info(f"Review added by {request.user.username} on product {product.name}")
            messages.success(request, "Votre avis a été soumis avec succès !")
            return redirect('store:product_detail', product_id=product.id)
        else:
            logger.error(f"Review submission failed for user {request.user.username}: {review_form.errors}")
            messages.error(request, "Erreur dans le formulaire. Veuillez vérifier les champs.")
    else:
        review_form = ReviewForm()

    # Produits similaires
    similar_products = Product.objects.filter(
        Q(category=product.category) |
        Q(brand=product.brand) |
        Q(color=product.color) |
        Q(material=product.material)
    ).exclude(id=product.id).filter(
        is_sold=False,
        sold_out=False,
        stock__gt=0
    ).annotate(
        avg_rating=Avg('reviews__rating')
    ).order_by('-avg_rating', '-views')[:4]

    # Produits recommandés (basés sur les favoris de l'utilisateur)
    recommended_products = []
    if request.user.is_authenticated:
        favorite_categories = Favorite.objects.filter(user=request.user).values('product__category').distinct()
        favorite_brands = Favorite.objects.filter(user=request.user).values('product__brand').distinct()
        recommended_products = Product.objects.filter(
            Q(category__in=favorite_categories) |
            Q(brand__in=favorite_brands)
        ).exclude(id=product.id).filter(
            is_sold=False,
            sold_out=False,
            stock__gt=0
        ).annotate(
            avg_rating=Avg('reviews__rating')
        ).order_by('-avg_rating', '-views')[:4]

        if len(recommended_products) < 4:
            popular_products = Product.objects.exclude(id=product.id).filter(
                is_sold=False,
                sold_out=False,
                stock__gt=0
            ).annotate(
                avg_rating=Avg('reviews__rating')
            ).order_by('-views')[:4 - len(recommended_products)]
            recommended_products = list(recommended_products) + list(popular_products)

    # Produits populaires (basés sur les vues des 30 derniers jours)
    thirty_days_ago = today - timedelta(days=30)
    popular_products = Product.objects.filter(
        product_views__view_date__gte=thirty_days_ago,
        is_sold=False,
        sold_out=False,
        stock__gt=0
    ).exclude(id=product.id).annotate(
        total_views=Sum('product_views__view_count'),
        avg_rating=Avg('reviews__rating')
    ).order_by('-total_views')[:4]

    # Vérification si la réduction est active
    now = timezone.now()

    return render(request, 'store/product_detail.html', {
        'product': product,
        'average_rating': average_rating,
        'favorite_count': favorite_count,
        'is_favorite': is_favorite,
        'reviews': reviews,
        'review_form': review_form,
        'can_review': can_review,
        'has_reviewed': has_reviewed,
        'similar_products': similar_products,
        'recommended_products': recommended_products,
        'popular_products': popular_products,
        'now': now,
    })

@login_required
@user_passes_test(is_seller, login_url='store:home')
def product_create(request):
    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES)
        if form.is_valid():
            product = form.save(commit=False)
            product.seller = request.user
            product.save()
            has_image = product.image1 or product.image2 or product.image3
            logger.info(f"Product created: {product.name}, Images: {has_image and 'Present' or 'None'}, Size: {product.size}, Brand: {product.brand}, Color: {product.color}, Material: {product.material}")
            messages.success(request, f"Produit ajouté avec succès ! Images: {has_image and 'Présentes' or 'Aucune'}")
            return redirect('store:product_list')
        else:
            logger.error(f"Product creation failed: {form.errors}")
            messages.error(request, f"Erreur dans le formulaire : {form.errors}")
    else:
        form = ProductForm()
    return render(request, 'store/product_form.html', {'form': form})

@login_required
def product_update(request, pk):
    product = get_object_or_404(Product, id=pk)
    if request.user.user_type != 'seller' or product.seller != request.user:
        messages.error(request, "Vous n'êtes pas autorisé à modifier ce produit.")
        return redirect('store:home')
    old_price = product.price
    old_size = product.size
    old_brand = product.brand
    old_color = product.color
    old_material = product.material
    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES, instance=product)
        if form.is_valid():
            form.save()
            has_image = product.image1 or product.image2 or product.image3
            logger.info(f"Product updated: {product.name}, Images: {has_image and 'Present' or 'None'}, Size: {product.size} (was {old_size}), Brand: {product.brand} (was {old_brand}), Color: {product.color} (was {old_color}), Material: {product.material} (was {old_material})")
            if product.price < old_price:
                favorites = Favorite.objects.filter(product=product)
                for favorite in favorites:
                    Notification.objects.create(
                        user=favorite.user,
                        message=f"Le produit '{product.name}' que vous avez mis en favori est en promotion ! Nouveau prix : {product.discounted_price} €.",
                        notification_type='product_discount',
                        related_object_id=product.id
                    )
            messages.success(request, f"Produit mis à jour avec succès ! Images: {has_image and 'Présentes' or 'Aucune'}")
            return redirect('store:product_detail', product_id=product.id)
        else:
            logger.error(f"Product update failed: {form.errors}")
            messages.error(request, f"Erreur dans le formulaire : {form.errors}")
    else:
        form = ProductForm(instance=product)
    return render(request, 'store/product_form.html', {'form': form, 'product': product})

@login_required
def product_delete(request, pk):
    product = get_object_or_404(Product, id=pk)
    if request.user.user_type != 'seller' or product.seller != request.user:
        messages.error(request, "Vous n'êtes pas autorisé à supprimer ce produit.")
        return redirect('store:home')
    if request.method == 'POST':
        logger.info(f"Product deleted: {product.name}")
        product.delete()
        messages.success(request, "Produit supprimé avec succès !")
        return redirect('store:product_list')
    return render(request, 'store/product_confirm_delete.html', {'product': product})

@login_required
def cart(request):
    try:
        cart = Cart.objects.get(user=request.user)
        logger.info(f"Cart retrieved for user {request.user.username}: {cart.id}")
    except Cart.DoesNotExist:
        cart = Cart.objects.create(user=request.user)
        logger.info(f"New cart created for user {request.user.username}: {cart.id}")
    except Cart.MultipleObjectsReturned:
        carts = Cart.objects.filter(user=request.user).order_by('created_at')
        cart = carts.first()
        logger.warning(f"Multiple carts found for user {request.user.username}, merging into {cart.id}")
        for duplicate_cart in carts[1:]:
            for item in duplicate_cart.items.all():
                existing_item, created = CartItem.objects.get_or_create(cart=cart, product=item.product)
                if not created:
                    existing_item.quantity += item.quantity
                    existing_item.save()
            duplicate_cart.delete()

    cart_items = cart.items.all()
    logger.info(f"Cart items for user {request.user.username}: {cart_items.count()} items")
    
    # Calcul des montants en Decimal
    subtotal = sum(item.subtotal for item in cart_items)
    shipping_cost = Decimal('5.00')
    discount_amount = Decimal('0.00')
    
    # Vérification d'un code promo existant dans la session
    promo_code = request.session.get('promo_code')
    if promo_code:
        try:
            code = PromoCode.objects.get(code=promo_code)
            if code.is_valid(user=request.user):
                discount_amount = code.apply(subtotal)
            else:
                del request.session['promo_code']
                del request.session['discount_amount']
        except PromoCode.DoesNotExist:
            del request.session['promo_code']
            del request.session['discount_amount']

    total = subtotal + shipping_cost - discount_amount
    
    return render(request, 'store/cart.html', {
        'cart': cart,
        'cart_items': cart_items,
        'subtotal': subtotal,
        'shipping_cost': shipping_cost,
        'discount_amount': discount_amount,
        'total': total
    })

@login_required
def add_to_cart(request, product_id):
    try:
        product = get_object_or_404(Product, id=product_id)
        if product.is_sold_out:
            messages.error(request, "Ce produit est vendu ou en rupture de stock.")
            return redirect('store:product_detail', product_id=product.id)

        with transaction.atomic():
            cart, created = Cart.objects.get_or_create(user=request.user)
            logger.info(f"Cart retrieved/created for user {request.user.username} in add_to_cart: {cart.id}")

            cart_item, created = CartItem.objects.get_or_create(cart=cart, product=product)
            if not created:
                if cart_item.quantity + 1 > product.stock:
                    messages.error(request, f"Stock insuffisant. Seulement {product.stock} unités disponibles.")
                    return redirect('store:cart')
                cart_item.quantity += 1
                cart_item.save()
                logger.info(f"Incremented quantity for {cart_item.product.name} in cart {cart.id}")
            else:
                if product.stock < 1:
                    messages.error(request, f"Stock insuffisant. Seulement {product.stock} unités disponibles.")
                    return redirect('store:cart')
                logger.info(f"Added new item {product.name} to cart {cart.id}")
            messages.success(request, f"{product.name} ajouté au panier !")
            return redirect('store:cart')
    except (OperationalError, IntegrityError) as e:
        logger.error(f"Database error in add_to_cart for product {product_id}: {str(e)}")
        messages.error(request, "Une erreur est survenue lors de l'ajout au panier. Veuillez réessayer.")
        return redirect('store:product_detail', product_id=product_id)
    except Exception as e:
        logger.error(f"Unexpected error in add_to_cart for product {product_id}: {str(e)}")
        messages.error(request, "Une erreur inattendue est survenue. Veuillez contacter le support.")
        return redirect('store:product_detail', product_id=product_id)

@login_required
def remove_from_cart(request, item_id):
    cart_item = get_object_or_404(CartItem, id=item_id, cart__user=request.user)
    logger.info(f"Removed item {cart_item.product.name} from cart for user {request.user.username}")
    cart_item.delete()
    messages.success(request, "Article retiré du panier.")
    return redirect('store:cart')

@login_required
def update_cart(request, item_id):
    cart_item = get_object_or_404(CartItem, id=item_id, cart__user=request.user)
    if request.method == 'POST':
        quantity = int(request.POST.get('quantity', 1))
        if quantity > cart_item.product.stock:
            messages.error(request, f"Stock insuffisant. Seulement {cart_item.product.stock} unités disponibles.")
            return redirect('store:cart')
        if quantity > 0:
            cart_item.quantity = quantity
            cart_item.save()
            logger.info(f"Updated quantity for {cart_item.product.name} to {quantity} in cart for user {request.user.username}")
            messages.success(request, "Panier mis à jour.")
        else:
            logger.info(f"Removed item {cart_item.product.name} from cart for user {request.user.username}")
            cart_item.delete()
            messages.success(request, "Article retiré du panier.")
        return redirect('store:cart')
    return render(request, 'store/update_cart.html', {'cart_item': cart_item})

@login_required
def add_address(request):
    if request.user.user_type != 'buyer':
        messages.error(request, "Seuls les acheteurs peuvent ajouter une adresse.")
        return redirect('store:checkout')
    if request.method == 'POST':
        form = AddressForm(request.POST)
        if form.is_valid():
            address = form.save(commit=False)
            address.user = request.user
            address.save()
            logger.info(f"Address added for user {request.user.username}")
            messages.success(request, "Adresse ajoutée avec succès !")
            return redirect('store:checkout')
        else:
            logger.error(f"Address addition failed for user {request.user.username}: {form.errors}")
            messages.error(request, "Erreur dans le formulaire. Veuillez vérifier les champs.")
    else:
        form = AddressForm()
    return render(request, 'store/add_address.html', {'form': form})


@login_required
def checkout(request):
    try:
        cart = Cart.objects.get(user=request.user)
        logger.info(f"Cart retrieved for user {request.user.username}: {cart.id}")
    except Cart.DoesNotExist:
        cart = Cart.objects.create(user=request.user)
        logger.info(f"New cart created for user {request.user.username}: {cart.id}")
    except Cart.MultipleObjectsReturned:
        carts = Cart.objects.filter(user=request.user).order_by('created_at')
        cart = carts.first()
        logger.warning(f"Multiple carts found for user {request.user.username}, merging into {cart.id}")
        for duplicate_cart in carts[1:]:
            for item in duplicate_cart.cartitem_set.all():
                existing_item, created = CartItem.objects.get_or_create(cart=cart, product=item.product)
                if not created:
                    existing_item.quantity += item.quantity
                    existing_item.save()
            duplicate_cart.delete()

    if not cart.items.exists():
        messages.error(request, "Votre panier est vide.")
        return redirect('store:cart')

    cart_items = cart.items.all()
    subtotal = sum(item.subtotal for item in cart_items)
    addresses = Address.objects.filter(user=request.user)
    shipping_options = ShippingOption.objects.filter(is_active=True)

    if not shipping_options.exists():
        messages.error(request, "Aucune option de livraison disponible. Veuillez contacter l'administrateur.")
        return redirect('store:cart')

    shipping_option_form = ShippingMethodForm(request.POST or None)
    address_form = AddressForm(request.POST or None)
    location_form = LocationForm(request.POST, request.FILES or None)

    if not addresses.exists():
        messages.warning(request, "Veuillez ajouter une adresse avant de continuer.")
        return redirect('store:add_address', next=reverse('store:checkout'))

    shipping_cost = Decimal('0.00')
    selected_shipping_option = None
    discount_amount = Decimal(request.session.get('discount_amount', '0.00'))
    promo_code = request.session.get('promo_code')
    latitude = None
    longitude = None
    geocoded_address = None

    if promo_code and discount_amount > 0:
        try:
            code = PromoCode.objects.get(code=promo_code)
            if not code.is_valid(user=request.user):
                discount_amount = Decimal('0.00')
                messages.error(request, "Code promo invalide ou expiré.")
                del request.session['promo_code']
                del request.session['discount_amount']
        except PromoCode.DoesNotExist:
            discount_amount = Decimal('0.00')
            messages.error(request, "Code promo introuvable.")
            del request.session['promo_code']
            del request.session['discount_amount']

    if shipping_option_form.is_valid():
        shipping_option_id = shipping_option_form.cleaned_data['shipping_option'].id
        selected_shipping_option = ShippingOption.objects.get(id=shipping_option_id)
        shipping_cost = selected_shipping_option.cost

    total = subtotal + shipping_cost - discount_amount

    if request.method == 'POST' and location_form.is_valid():
        photo = location_form.cleaned_data['photo']
        description = location_form.cleaned_data['description']
        latitude = location_form.cleaned_data.get('latitude')
        longitude = location_form.cleaned_data.get('longitude')

        if photo:
            try:
                exif_data = get_exif_data(photo)
                gps_latitude, gps_longitude = get_gps_info(exif_data)
                if gps_latitude is not None and gps_longitude is not None:
                    latitude = gps_latitude
                    longitude = gps_longitude
                    logger.info(f"GPS coordinates extracted: lat={latitude}, lon={longitude}")
                else:
                    logger.warning("No GPS data found in photo")
                    messages.warning(request, "Aucune donnée GPS trouvée dans la photo. Veuillez sélectionner une position sur la carte.")
            except Exception as e:
                logger.error(f"Error extracting GPS data: {e}")
                messages.warning(request, "Erreur lors de l'extraction des données GPS. Veuillez sélectionner une position sur la carte.")
        else:
            logger.info("No photo provided, using form coordinates if available")

        if latitude and longitude:
            location = Location.objects.create(
                user=request.user,
                description=description,
                latitude=latitude,
                longitude=longitude,
                photo=photo if photo else None
            )
            # Convertir les coordonnées en adresse via Nominatim
            try:
                response = requests.get(
                    'https://nominatim.openstreetmap.org/reverse',
                    params={
                        'lat': latitude,
                        'lon': longitude,
                        'format': 'json',
                        'addressdetails': 1
                    },
                    headers={'User-Agent': 'EcommerceApp/1.0'}
                )
                if response.status_code == 200:
                    data = response.json()
                    address_data = data.get('address', {})
                    geocoded_address = Address.objects.create(
                        user=request.user,
                        full_name=request.user.username,
                        street_address=address_data.get('road', 'Inconnue'),
                        city=address_data.get('city', '') or address_data.get('town', '') or address_data.get('village', ''),
                        postal_code=address_data.get('postcode', ''),
                        country=address_data.get('country', 'Inconnue'),
                        is_default=False
                    )
                    messages.success(request, "Adresse extraite des coordonnées GPS.")
                    addresses = Address.objects.filter(user=request.user)  # Rafraîchir la liste des adresses
                else:
                    messages.warning(request, "Impossible de convertir les coordonnées en adresse.")
            except Exception as e:
                logger.error(f"Error geocoding coordinates: {e}")
                messages.warning(request, "Erreur lors de la conversion des coordonnées en adresse.")
        else:
            messages.warning(request, "Veuillez fournir une photo avec des données GPS ou sélectionner une position sur la carte.")

    context = {
        'cart': cart,
        'cart_items': cart_items,
        'subtotal': subtotal,
        'shipping_cost': shipping_cost,
        'discount_amount': discount_amount,
        'total': total,
        'addresses': addresses,
        'shipping_options': shipping_options,
        'address_form': address_form,
        'shipping_option_form': shipping_option_form,
        'location_form': location_form,
        'latitude': latitude,
        'longitude': longitude,
        'geocoded_address': geocoded_address,
        'stripe_publishable_key': settings.STRIPE_PUBLISHABLE_KEY,
        'paypal_client_id': settings.PAYPAL_CLIENT_ID,
        'promo_code': promo_code,
    }

    return render(request, 'store/checkout.html', context)







stripe.api_key = settings.STRIPE_SECRET_KEY
paypalrestsdk.configure({
    "mode": settings.PAYPAL_MODE,
    "client_id": settings.PAYPAL_CLIENT_ID,
    "client_secret": settings.PAYPAL_CLIENT_SECRET
})

@login_required
@transaction.atomic
def process_payment(request):
    if request.method != 'POST':
        messages.error(request, "Méthode non autorisée.")
        return redirect('store:checkout')

    try:
        cart = Cart.objects.get(user=request.user)
        logger.info(f"Panier récupéré pour l'utilisateur {request.user.username}: {cart.id}")
    except Cart.DoesNotExist:
        messages.error(request, "Votre panier est vide.")
        return redirect('store:cart')

    cart_items = cart.items.all()
    if not cart_items.exists():
        messages.error(request, "Votre panier est vide.")
        return redirect('store:cart')

    address_id = request.POST.get('address')
    shipping_option_form = ShippingMethodForm(request.POST)
    payment_method = request.POST.get('payment_method')
    payment_method_id = request.POST.get('payment_method_id')
    paypal_order_id = request.POST.get('paypal_order_id')

    if not address_id or not shipping_option_form.is_valid() or not payment_method:
        messages.error(request, "Veuillez remplir tous les champs requis.")
        return redirect('store:checkout')

    try:
        address = Address.objects.get(id=address_id, user=request.user)
        shipping_option = shipping_option_form.cleaned_data['shipping_option']
    except (Address.DoesNotExist):
        messages.error(request, "Adresse invalide.")
        return redirect('store:checkout')

    address_form = AddressForm(request.POST)
    if address_form.is_valid():
        new_address = address_form.save(commit=False)
        new_address.user = request.user
        new_address.save()
        address_id = new_address.id
        address = new_address

    location_form = LocationForm(request.POST, request.FILES)
    if not location_form.is_valid():
        messages.error(request, "Erreur dans le formulaire de localisation.")
        return redirect('store:checkout')

    subtotal = sum(item.subtotal for item in cart_items)
    shipping_cost = shipping_option.cost
    discount_amount = Decimal(request.session.get('discount_amount', '0.00'))

    promo_code = request.session.get('promo_code')
    if promo_code and discount_amount > 0:
        try:
            code = PromoCode.objects.get(code=promo_code)
            if not code.is_valid(user=request.user):
                discount_amount = Decimal('0.00')
                del request.session['promo_code']
                del request.session['discount_amount']
        except PromoCode.DoesNotExist:
            discount_amount = Decimal('0.00')
            del request.session['promo_code']
            del request.session['discount_amount']

    total = subtotal + shipping_cost - discount_amount

    for item in cart_items:
        product = Product.objects.select_for_update().get(id=item.product.id)
        if item.quantity > product.stock or product.is_sold_out:
            messages.error(request, f"Stock insuffisant pour {item.product.name}.")
            return redirect('store:cart')

    order = Order.objects.create(
        user=request.user,
        total=total,
        shipping_address=address,
        shipping_option=shipping_option,
        subtotal=subtotal,
        shipping_cost=shipping_cost,
        discount_amount=discount_amount,
        status='pending',
        payment_method=payment_method
    )
    logger.info(f"Commande créée pour l'utilisateur {request.user.username}: #{order.id}, Total: {total} €")

    for item in cart_items:
        product = Product.objects.get(id=item.product.id)
        order_item = OrderItem.objects.create(
            order=order,
            product=product,
            quantity=item.quantity,
            price=product.discounted_price,
            seller=product.seller
        )
        product.stock -= item.quantity
        product.save()

    location = location_form.save(commit=False)
    if location.photo:
        exif_data = get_exif_data(location.photo)
        latitude, longitude = get_gps_info(exif_data)
        if latitude and longitude:
            location.latitude = latitude
            location.longitude = longitude
    location.user = request.user
    location.save()

    delivery = Delivery.objects.create(
        order=order,
        location=location,
        status='pending'
    )

    points = int(total // 10)
    if points > 0:
        LoyaltyPoint.objects.create(
            user=request.user,
            points=points,
            description=f"Points pour commande #{order.id}"
        )
        logger.info(f"{points} points de fidélité attribués à {request.user.username}")

    if 'promo_code' in request.session:
        del request.session['promo_code']
        del request.session['discount_amount']

    charge_id = None
    stripe.api_key = settings.STRIPE_SECRET_KEY
    if payment_method == 'card' and payment_method_id:
        try:
            customers = stripe.Customer.list(email=request.user.email, limit=1)
            if customers.data:
                stripe_customer = customers.data[0]
            else:
                stripe_customer = stripe.Customer.create(email=request.user.email)
            stripe.PaymentMethod.attach(payment_method_id, customer=stripe_customer.id)
            intent = stripe.PaymentIntent.create(
                amount=int(total * 100),
                currency='eur',
                customer=stripe_customer.id,
                payment_method=payment_method_id,
                confirmation_method='manual',
                confirm=True,
                return_url=request.build_absolute_uri(reverse('store:payment_success', kwargs={'order_id': order.id}))
            )
            if intent.status == 'succeeded':
                charges = stripe.Charge.list(payment_intent=intent.id, limit=1)
                if charges.data:
                    charge_id = charges.data[0].id
                    logger.info(f"Charge ID récupéré pour la commande #{order.id}: {charge_id}")
                else:
                    logger.error(f"Aucune charge trouvée pour PaymentIntent {intent.id} pour la commande #{order.id}")
                    raise stripe.error.InvalidRequestError(
                        "Aucune charge associée au PaymentIntent.", 
                        param='payment_intent'
                    )
                order.charge_id = charge_id
                order.status = 'processing'
                order.save()
                logger.info(f"Paiement Stripe réussi pour la commande #{order.id}, charge_id: {charge_id}")
            else:
                logger.error(f"PaymentIntent {intent.id} non finalisé pour la commande #{order.id}, statut: {intent.status}")
                raise stripe.error.CardError("Paiement non finalisé", 'payment_intent', intent.status)
        except stripe.error.StripeError as e:
            logger.error(f"Erreur Stripe pour la commande #{order.id}: {str(e)}")
            order.charge_id = None
            order.status = 'pending'
            order.save()
            messages.error(request, f"Erreur lors du paiement : {str(e)}")
            return redirect('store:checkout')

    elif payment_method == 'paypal' and paypal_order_id:
        try:
            payment = paypalrestsdk.Payment.find(paypal_order_id)
            if payment.state == 'approved':
                charge_id = payment.transactions[0].related_resources[0].sale.id
                order.charge_id = charge_id
                order.status = 'processing'
                order.save()
                logger.info(f"Paiement PayPal réussi pour la commande #{order.id}, sale_id: {charge_id}")
            else:
                logger.error(f"Paiement PayPal non approuvé pour la commande #{order.id}: {payment.state}")
                order.charge_id = None
                order.status = 'pending'
                order.save()
                messages.error(request, "Le paiement PayPal n’a pas été approuvé.")
                return redirect('store:checkout')
        except paypalrestsdk.exceptions.ResourceNotFound as e:
            logger.error(f"Erreur PayPal pour la commande #{order.id}: {str(e)}")
            order.charge_id = None
            order.status = 'pending'
            order.save()
            messages.error(request, f"Erreur lors du paiement PayPal : {str(e)}")
            return redirect('store:checkout')
        except Exception as e:
            logger.error(f"Erreur inattendue PayPal pour la commande #{order.id}: {str(e)}")
            order.charge_id = None
            order.status = 'pending'
            order.save()
            messages.error(request, f"Erreur inattendue lors du paiement PayPal : {str(e)}")
            return redirect('store:checkout')

    else:
        logger.error(f"Méthode de paiement ou ID manquant pour la commande #{order.id}")
        order.charge_id = None
        order.status = 'pending'
        order.save()
        messages.error(request, "Méthode de paiement ou ID de paiement manquant.")
        return redirect('store:checkout')

    if order.seller:
        Notification.objects.create(
            user=order.seller,
            message=f"Une nouvelle commande (#{order.id}) contient votre produit.",
            notification_type='new_order',
            related_object_id=order.id
        )
    else:
        logger.warning(f"Aucun seller principal défini pour la commande #{order.id}")

    cart.delete()
    messages.success(request, "Commande passée avec succès !")
    return redirect('store:payment_success', order_id=order.id)

@login_required
def payment_success(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    return render(request, 'store/payment_success.html', {
        'message': 'Paiement effectué avec succès !',
        'order': order
    })

@login_required
def order_history(request):
    orders = Order.objects.filter(user=request.user).order_by('-created_at')
    for order in orders:
        if request.user.user_type == 'buyer' and order.status == 'delivered':
            order_items = OrderItem.objects.filter(order=order)
            sellers = set(item.product.seller for item in order_items)
            already_rated_sellers = set(
                SellerRating.objects.filter(order=order, rater=request.user)
                .values_list('seller', flat=True)
            )
            order.can_rate_sellers = bool(sellers - already_rated_sellers)
        else:
            order.can_rate_sellers = False
        order.items_with_totals = [
            {
                'product_name': item.product.name,
                'quantity': item.quantity,
                'unit_price': item.price,
                'total': item.price * item.quantity
            }
            for item in order.items.all()
        ]
    return render(request, 'store/order_history.html', {'orders': orders})

@login_required
def order_detail(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    if request.user != order.user:
        messages.error(request, "Vous n'êtes pas autorisé à voir les détails de cette commande.")
        return redirect('store:order_history')

    order_items = OrderItem.objects.filter(order=order)
    return_requests = ReturnRequest.objects.filter(order=order)
    return_form = ReturnRequestForm() if request.user.user_type == 'buyer' and order.status == 'delivered' else None
    return render(request, 'store/order_detail.html', {
        'order': order,
        'order_items': order_items,
        'return_requests': return_requests,
        'return_form': return_form,
    })

@login_required
@user_passes_test(is_seller, login_url='store:home')
def apply_discount_for_product(request, product_id):
    if request.user.user_type != 'seller':
        messages.error(request, "Seuls les vendeurs peuvent gérer les promotions.")
        return redirect('store:product_list')
    
    product = get_object_or_404(Product, id=product_id, seller=request.user)
    
    if request.method == 'POST':
        form = ApplyDiscountForm(request.POST, seller=request.user, single_product=product)
        if form.is_valid():
            percentage = form.cleaned_data['percentage']
            start_date = form.cleaned_data['start_date']
            end_date = form.cleaned_data['end_date']

            if start_date >= end_date:
                messages.error(request, "La date de fin doit être postérieure à la date de début.")
                return render(request, 'store/apply_discount.html', {'form': form, 'product': product})

            Discount.objects.create(
                product=product,
                percentage=percentage,
                start_date=start_date,
                end_date=end_date,
                is_active=True
            )

            # Notification pour les favoris
            favorites = Favorite.objects.filter(product=product)
            for favorite in favorites:
                Notification.objects.create(
                    user=favorite.user,
                    message=f"Le produit '{product.name}' que vous avez mis en favori est en promotion ! Nouveau prix : {product.discounted_price} €.",
                    notification_type='product_discount',
                    related_object_id=product.id
                )

            logger.info(f"Discount applied by user {request.user.username}: {percentage}% on product {product.id}")
            messages.success(request, "Réduction appliquée avec succès !")
            return redirect('store:product_detail', product_id=product.id)
        else:
            logger.error(f"Discount application failed for user {request.user.username}: {form.errors}")
            messages.error(request, f"Erreur dans le formulaire. Veuillez vérifier les champs : {form.errors}")
    else:
        form = ApplyDiscountForm(seller=request.user, single_product=product)

    return render(request, 'store/apply_discount.html', {'form': form, 'product': product})

@login_required
@require_POST
def apply_discount(request):
    if request.method == 'POST':
        code = request.POST.get('code', '').strip()
        cart = Cart.objects.get(user=request.user)
        subtotal = sum(item.subtotal for item in cart.items.all())
        try:
            promo_code = PromoCode.objects.get(code=code)
            if promo_code.is_valid(user=request.user):
                discount_amount = promo_code.apply(subtotal)
                request.session['promo_code'] = code
                request.session['discount_amount'] = float(discount_amount)
                messages.success(request, f"Code promo '{code}' appliqué avec succès ! Réduction : {discount_amount:.2f} €")
            else:
                messages.error(request, "Code promo invalide ou expiré.")
        except PromoCode.DoesNotExist:
            messages.error(request, "Code promo introuvable.")
        return redirect('store:cart')
    return redirect('store:cart')

@login_required
@user_passes_test(is_seller, login_url='store:home')
def update_order_status(request, order_id):
    # Obtenir la commande distincte qui contient au moins un article du vendeur
    orders = Order.objects.filter(
        id=order_id,
        items__product__seller=request.user
    ).distinct()
    
    # Vérifier s'il y a exactement une commande
    if orders.count() != 1:
        raise ValueError(f"Problème avec la commande {order_id}: {orders.count()} résultats trouvés")
    
    order = orders.first()
    
    if request.method == 'POST':
        form = OrderStatusForm(request.POST, instance=order)
        if form.is_valid():
            old_status = order.status
            form.save()
            if old_status != 'shipped' and order.status == 'shipped':
                Notification.objects.create(
                    user=order.user,
                    message=f"Votre commande #{order.id} a été expédiée !",
                    notification_type='order_shipped',
                    related_object_id=order.id
                )
            logger.info(f"Order status updated: #{order.id} to {order.status} by user {request.user.username}")
            return JsonResponse({'success': True})
        return JsonResponse({'success': False, 'error': form.errors})
    elif request.method == 'GET':
        form = OrderStatusForm(instance=order)
        return render(request, 'store/update_order_status.html', {'form': form, 'order': order})
    return JsonResponse({'success': False, 'error': 'Méthode non autorisée.'})

@login_required
def mark_as_sold(request, product_id):
    product = get_object_or_404(Product, id=product_id, seller=request.user)
    if request.user.user_type != 'seller':
        messages.error(request, "Seuls les vendeurs peuvent marquer un produit comme vendu.")
        return redirect('store:product_list')
    if request.method == 'POST':
        product.is_sold = True
        product.stock = 0
        product.sold_out = True
        product.save()
        logger.info(f"Product marked as sold: {product.name} by user {request.user.username}")
        messages.success(request, f"{product.name} marqué comme vendu !")
        return redirect('store:product_list')
    return render(request, 'store/confirm_sold.html', {'product': product})

def product_request(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    if not product.is_sold_out:
        messages.warning(request, "Ce produit est encore en stock.")
        return redirect('store:product_detail', product_id=product.id)
    
    if request.method == 'POST':
        form = ProductRequestForm(request.POST, user=request.user)
        if form.is_valid():
            email = form.cleaned_data.get('email')
            try:
                if request.user.is_authenticated:
                    if ProductRequest.objects.filter(user=request.user, product=product).exists():
                        messages.warning(request, "Vous avez déjà fait une demande pour ce produit.")
                        return redirect('store:product_detail', product_id=product.id)
                elif email and ProductRequest.objects.filter(email=email, product=product).exists():
                    messages.warning(request, "Une demande a déjà été faite avec cet email pour ce produit.")
                    return redirect('store:product_detail', product_id=product.id)
                
                product_request = form.save(commit=False)
                product_request.product = product
                if request.user.is_authenticated:
                    product_request.user = request.user
                product_request.save()
                
                Notification.objects.create(
                    user=product.seller,
                    message=f"Une nouvelle demande a été faite pour {product.name} par {request.user.username if request.user.is_authenticated else 'un utilisateur anonyme'}.",
                    notification_type='product_request',
                    related_object_id=product.id
                )
                
                logger.info(f"Product request submitted for {product.name} by {request.user.username if request.user.is_authenticated else email}")
                messages.success(request, "Votre demande a été envoyée. Vous serez notifié lorsque le produit sera disponible.")
                return redirect('store:product_detail', product_id=product.id)
            except IntegrityError:
                logger.error(f"Duplicate detected for product request {product.name} by {request.user.username if request.user.is_authenticated else email}")
                messages.error(request, "Une erreur est survenue. Vous avez peut-être déjà fait une demande pour ce produit.")
                return redirect('store:product_detail', product_id=product.id)
        else:
            logger.error(f"Form errors for product request {product.name}: {form.errors}")
            messages.error(request, "Erreur dans le formulaire. Veuillez vérifier les champs.")
    else:
        form = ProductRequestForm(user=request.user)
    
    return render(request, 'store/request_product.html', {'form': form, 'product': product})

@login_required
@user_passes_test(is_seller, login_url='store:home')
def respond_product_request(request, request_id):
    product_request = get_object_or_404(ProductRequest, id=request_id, product__seller=request.user)
    if request.method == 'POST':
        response = request.POST.get('response', '').strip()
        restock_quantity = request.POST.get('restock_quantity', '')
        if response or restock_quantity:
            if restock_quantity:
                try:
                    restock_quantity = int(restock_quantity)
                    if restock_quantity > 0:
                        product = product_request.product
                        product.stock += restock_quantity
                        product.is_sold = False
                        product.sold_out = False
                        product.save()
                        logger.info(f"Product {product.name} restocked with {restock_quantity} units by {request.user.username}")
                except ValueError:
                    messages.error(request, "La quantité de restockage doit être un nombre valide.")
                    return redirect('store:product_list')

            product_request.is_notified = True
            product_request.save()

            user_message = f"Le vendeur a répondu à votre demande pour {product_request.product.name}."
            if response:
                user_message += f" Message : {response}"
            if restock_quantity and restock_quantity > 0:
                user_message += f" Le produit a été restocké avec {restock_quantity} unités."

            if product_request.user:
                Notification.objects.create(
                    user=product_request.user,
                    message=user_message,
                    notification_type='product_request',
                    related_object_id=product_request.product.id
                )
            elif product_request.email:
                logger.info(f"Email notification would be sent to {product_request.email}: {user_message}")
                # Implémentation d'envoi d'email non incluse ici

            logger.info(f"Response sent for product request {product_request.id} by {request.user.username}")
            messages.success(request, "Réponse envoyée avec succès !")
            return redirect('store:product_list')
        else:
            messages.error(request, "Veuillez fournir une réponse ou une quantité de restockage.")
    return render(request, 'store/respond_product_request.html', {'product_request': product_request})

@login_required
@require_POST
def toggle_favorite(request, product_id):
    logger.info(f"Requête toggle_favorite reçue pour product_id: {product_id}")
    try:
        if not request.user.is_authenticated:
            logger.warning("Utilisateur non authentifié")
            return JsonResponse({'status': 'error', 'message': 'Authentication required'}, status=401)
        
        logger.info(f"Recherche du produit avec ID: {product_id}")
        product = get_object_or_404(Product, id=product_id)
        logger.info(f"Produit trouvé: {product.name}")
        
        logger.info(f"Tentative de création/mise à jour du favori pour l'utilisateur: {request.user.username}")
        favorite, created = Favorite.objects.get_or_create(
            user=request.user,
            product=product
        )
        
        if not created:
            favorite.delete()
            action = 'removed'
            logger.info(f"Favori supprimé pour product_id: {product_id}")
        else:
            action = 'added'
            logger.info(f"Favori ajouté pour product_id: {product_id}")
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            response_data = {
                'status': 'success',
                'action': action,
                'favorite_count': Favorite.objects.filter(product=product).count()
            }
            logger.info(f"Réponse JSON envoyée: {response_data}")
            return JsonResponse(response_data)
        
        return redirect(request.META.get('HTTP_REFERER', 'store:product_list'))
    except Product.DoesNotExist:
        logger.error(f"Produit avec ID {product_id} non trouvé")
        return JsonResponse({'status': 'error', 'message': 'Produit non trouvé'}, status=404)
    except Favorite.DoesNotExist:
        logger.error(f"Favori inexistant pour product_id: {product_id}")
        return JsonResponse({'status': 'error', 'message': 'Favori inexistant'}, status=404)
    except Exception as e:
        logger.error(f"Erreur inattendue dans toggle_favorite: {str(e)}", exc_info=True)
        return JsonResponse({'status': 'error', 'message': f'Erreur serveur: {str(e)}'}, status=500)

@login_required
def delete_review(request, review_id):
    review = get_object_or_404(Review, id=review_id)
    if request.user != review.user and (request.user.user_type != 'seller' or review.product.seller != request.user):
        messages.error(request, "Vous n'êtes pas autorisé à supprimer cet avis.")
        return redirect('store:product_detail', product_id=review.product.id)
    if request.method == 'POST':
        product_id = review.product.id
        logger.info(f"Review deleted: ID {review_id} by user {request.user.username}")
        review.delete()
        messages.success(request, "Avis supprimé !")
        return redirect('store:product_detail', product_id=product_id)
    return render(request, 'store/review_confirm_delete.html', {'review': review})

@login_required
@user_passes_test(is_seller, login_url='store:home')
def reply_to_review(request, review_id):
    review = get_object_or_404(Review, id=review_id)
    if review.product.seller != request.user:
        messages.error(request, "Vous n'êtes pas autorisé à répondre à cet avis.")
        return redirect('store:product_detail', product_id=review.product.id)

    if request.method == 'POST':
        reply = request.POST.get('reply', '').strip()
        if reply:
            review.reply = reply
            review.save()
            logger.info(f"Reply added to review {review.id} by seller {request.user.username}")
            messages.success(request, "Votre réponse a été ajoutée avec succès !")
            return redirect('store:product_detail', product_id=review.product.id)
        else:
            messages.error(request, "La réponse ne peut pas être vide.")
    return render(request, 'store/reply_to_review.html', {'review': review})

@login_required
def favorites(request):
    favorites = Favorite.objects.filter(user=request.user).select_related('product')
    return render(request, 'store/favorites.html', {'favorites': favorites})

@login_required
def notifications(request):
    # Récupérer toutes les notifications de l'utilisateur sans filtre strict
    notifications = Notification.objects.filter(user=request.user).order_by('-created_at')
    
    # Calculer le nombre de notifications non lues
    unread_count = notifications.filter(is_read=False).count()
    
    # Ajouter des logs détaillés pour déboguer
    logger.info(f"Notifications pour {request.user.username}: {notifications.count()} totales, {unread_count} non lues")
    for n in notifications:
        logger.info(f"Notification ID: {n.id}, Message: {n.message}, Read: {n.is_read}, Related ID: {n.related_object_id}")
    
    return render(request, 'store/notifications.html', {
        'notifications': notifications,
        'unread_count': unread_count
    })

@login_required
def mark_all_notifications_read(request):
    request.user.notifications.update(is_read=True)
    messages.success(request, "Toutes les notifications ont été marquées comme lues")
    return redirect('store:notifications')

@login_required
def message_seller(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    if request.user == product.seller:
        messages.error(request, "Vous ne pouvez pas vous envoyer un message à vous-même.")
        return redirect('store:product_detail', product_id=product.id)
    if request.user.user_type != 'buyer':
        messages.error(request, "Seuls les acheteurs peuvent contacter les vendeurs.")
        return redirect('store:product_detail', product_id=product_id)

    conversation = Conversation.objects.filter(
        initiator=request.user,
        recipient=product.seller,
        product=product
    ).first()

    if not conversation:
        conversation = Conversation.objects.create(
            initiator=request.user,
            recipient=product.seller,
            product=product
        )
        logger.info(f"New conversation created between {request.user.username} and {product.seller.username} for product {product.name}")

    return redirect('store:chat', conversation_id=conversation.id)

@login_required
def chat(request, conversation_id):
    conversation = get_object_or_404(Conversation, id=conversation_id)
    
    if request.user not in [conversation.initiator, conversation.recipient]:
        messages.error(request, "Vous n'êtes pas autorisé à accéder à cette conversation.")
        return redirect('store:home')

    Message.objects.filter(
        conversation=conversation,
        is_read=False
    ).exclude(sender=request.user).update(is_read=True)

    if request.method == 'POST':
        content = request.POST.get('content', '').strip()
        if content:
            message = Message.objects.create(
                conversation=conversation,
                sender=request.user,
                content=content
            )
            logger.info(f"New message sent by {request.user.username} in conversation {conversation.id}")

            recipient = conversation.initiator if request.user == conversation.recipient else conversation.recipient
            Notification.objects.create(
                user=recipient,
                message=f"Vous avez un nouveau message de {request.user.username} concernant le produit '{conversation.product.name}'.",
                notification_type='new_message',
                related_object_id=conversation.id
            )

    messages = conversation.messages.all().order_by('sent_at')
    other_user = conversation.initiator if request.user == conversation.recipient else conversation.recipient

    return render(request, 'store/messages.html', {
        'conversation': conversation,
        'messages': messages,
        'other_user': other_user,
    })

@login_required
def rate_seller(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    if request.user.user_type != 'buyer':
        messages.error(request, "Seuls les acheteurs peuvent noter les vendeurs.")
        return redirect('store:order_history')
    if order.status != 'delivered':
        messages.error(request, "Vous ne pouvez noter le vendeur qu'après avoir reçu la commande.")
        return redirect('store:order_history')

    order_items = OrderItem.objects.filter(order=order)
    sellers = set(item.product.seller for item in order_items)

    if request.method == 'POST':
        for seller in sellers:
            rating = request.POST.get(f'rating_{seller.id}')
            comment = request.POST.get(f'comment_{seller.id}', '').strip()
            if rating:
                try:
                    rating = int(rating)
                    if rating < 1 or rating > 5:
                        messages.error(request, f"La note pour {seller.username} doit être entre 1 et 5.")
                        return redirect('store:rate_seller', order_id=order.id)
                    existing_rating = SellerRating.objects.filter(
                        seller=seller,
                        rater=request.user,
                        order=order
                    ).exists()
                    if existing_rating:
                        messages.error(f"Vous avez déjà noté {seller.username} pour cette commande.")
                        continue
                    SellerRating.objects.create(
                        seller=seller,
                        rater=request.user,
                        order=order,
                        rating=rating,
                        comment=comment if comment else None
                    )
                    Notification.objects.create(
                        user=seller,
                        message=f"{request.user.username} vous a donné une note de {rating}/5 pour la commande #{order.id}.",
                        notification_type='seller_rated',
                        related_object_id=order.id
                    )
                    logger.info(f"Seller {seller.username} rated {rating}/5 by user {request.user.username} for order {order.id}")
                    messages.success(request, f"Votre note pour {seller.username} a été enregistrée !")
                except ValueError:
                    messages.error(request, f"La note pour {seller.username} doit être un nombre valide.")
                    return redirect('store:rate_seller', order_id=order.id)
            else:
                messages.error(request, f"Veuillez fournir une note pour {seller.username}.")
                return redirect('store:rate_seller', order_id=order.id)
        return redirect('store:order_history')

    return render(request, 'store/rate_seller.html', {
        'order': order,
        'sellers': sellers,
    })

def seller_public_profile(request, username):
    User = get_user_model()
    seller = get_object_or_404(User, username=username, user_type='seller')
    profile = get_object_or_404(SellerProfile, user=seller)
    products = Product.objects.filter(seller=seller, is_sold=False, sold_out=False)
    ratings = SellerRating.objects.filter(seller=seller).order_by('-created_at')
    return render(request, 'accounts/seller_public_profile.html', {
        'profile': profile,
        'products': products,
        'ratings': ratings,
    })

@login_required
@user_passes_test(is_seller, login_url='store:home')
def seller_profile(request):
    profile, created = SellerProfile.objects.get_or_create(user=request.user)
    
    if request.method == 'POST':
        form = SellerProfileForm(request.POST, request.FILES, instance=profile)
        if form.is_valid():
            form.save()
            logger.info(f"Profile updated for user {request.user.username}")
            messages.success(request, "Profil mis à jour avec succès !")
            return redirect('store:seller_profile')
        else:
            logger.error(f"Profile update failed for user {request.user.username}: {form.errors}")
            messages.error(request, "Erreur dans le formulaire. Veuillez vérifier les champs.")
    else:
        form = SellerProfileForm(instance=profile)
    
    return render(request, 'accounts/seller_profile.html', {'form': form})

@login_required
@user_passes_test(is_seller, login_url='store:home')
def create_subscription(request):
    if request.method == 'POST':
        plan = request.POST.get('plan', 'pro')
        if plan not in ['free', 'pro']:
            messages.error(request, "Plan d'abonnement invalide.")
            return redirect('store:subscription_plans')
        
        if plan == 'free':
            Subscription.objects.filter(user=request.user, active=True).update(active=False)
            subscription, created = Subscription.objects.get_or_create(
                user=request.user,
                plan='free',
                defaults={'active': True}
            )
            if not created:
                subscription.active = True
                subscription.save()
            messages.success(request, "Vous êtes passé au plan Gratuit.")
            return redirect('store:product_list')
        
        try:
            customer = stripe.Customer.create(
                email=request.user.email,
                metadata={'user_id': request.user.id}
            )
            session = stripe.checkout.Session.create(
                customer=customer.id,
                payment_method_types=['card'],
                line_items=[{
                    'price': settings.STRIPE_PRO_PRICE_ID,
                    'quantity': 1,
                }],
                mode='subscription',
                success_url='http://localhost:8000/store/subscription/success/',
                cancel_url='http://localhost:8000/store/subscription/cancel/',
            )
            logger.info(f"Subscription checkout session created for user {request.user.username}")
            return redirect(session.url, code=303)
        except stripe.error.StripeError as e:
            logger.error(f"Subscription creation failed for user {request.user.username}: {str(e)}")
            messages.error(request, "Erreur lors de la création de l'abonnement. Veuillez réessayer.")
            return redirect('store:subscription_plans')

    return redirect('store:subscription_plans')

@login_required
def subscription_plans(request):
    subscription = Subscription.objects.filter(user=request.user, active=True).first()
    return render(request, 'store/subscription_plans.html', {'subscription': subscription})

@login_required
def subscription_success(request):
    messages.success(request, "Abonnement activé avec succès !")
    return redirect('store:product_list')

@login_required
def subscription_cancel(request):
    messages.error(request, "L'abonnement a été annulé.")
    return redirect('store:subscription_plans')

@csrf_exempt
def stripe_webhook(request):
    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')
    endpoint_secret = settings.STRIPE_WEBHOOK_SECRET

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, endpoint_secret
        )
    except ValueError:
        logger.error("Invalid webhook payload")
        return HttpResponse(status=400)
    except stripe.error.SignatureVerificationError:
        logger.error("Invalid webhook signature")
        return HttpResponse(status=400)

    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        customer_id = session.get('customer')
        subscription_id = session.get('subscription')
        user_id = session.get('metadata', {}).get('user_id')
        
        if user_id:
            user = get_object_or_404(get_user_model(), id=user_id)
            Subscription.objects.filter(user=user, active=True).update(active=False)
            subscription, created = Subscription.objects.get_or_create(
                user=user,
                plan='pro',
                defaults={
                    'stripe_subscription_id': subscription_id,
                    'active': True
                }
            )
            if not created:
                subscription.stripe_subscription_id = subscription_id
                subscription.active = True
                subscription.save()
                
            logger.info(f"Subscription activated for user {user.username}: Pro plan")
    
    elif event['type'] == 'customer.subscription.deleted':
        subscription_id = event['data']['object']['id']
        subscription = Subscription.objects.filter(stripe_subscription_id=subscription_id).first()
        if subscription:
            subscription.active = False
            subscription.end_date = timezone.now()
            subscription.save()
            Subscription.objects.get_or_create(
                user=subscription.user,
                plan='free',
                defaults={'active': True}
            )
            logger.info(f"Subscription cancelled for user {subscription.user.username}")

    return HttpResponse(status=200)

def custom_404(request, exception):
    return render(request, '404.html', status=404)
def custom_500(request):
    return render(request, '500.html', status=500)

@login_required
@user_passes_test(is_seller, login_url='store:home')
def respond_product_request(request, request_id):
    product_request = get_object_or_404(ProductRequest, id=request_id, product__seller=request.user)
    if request.method == 'POST':
        response = request.POST.get('response', '').strip()
        restock_quantity = request.POST.get('restock_quantity', '')
        if response or restock_quantity:
            if restock_quantity:
                try:
                    restock_quantity = int(restock_quantity)
                    if restock_quantity > 0:
                        product = product_request.product
                        product.stock += restock_quantity
                        product.is_sold = False
                        product.sold_out = False
                        product.save()
                        logger.info(f"Product {product.name} restocked with {restock_quantity} units by {request.user.username}")
                except ValueError:
                    messages.error(request, "La quantité de restockage doit être un nombre valide.")
                    return redirect('store:product_list')

            product_request.is_notified = True
            product_request.save()

            user_message = f"Le vendeur a répondu à votre demande pour {product_request.product.name}."
            if response:
                user_message += f" Message : {response}"
            if restock_quantity and restock_quantity > 0:
                user_message += f" Le produit a été restocké avec {restock_quantity} unités."

            if product_request.user:
                Notification.objects.create(
                    user=product_request.user,
                    message=user_message,
                    notification_type='product_request',
                    related_object_id=product_request.product.id
                )
            elif product_request.email:
                logger.info(f"Email notification would be sent to {product_request.email}: {user_message}")
                # Implémentation d'envoi d'email non incluse ici

            logger.info(f"Response sent for product request {product_request.id} by {request.user.username}")
            messages.success(request, "Réponse envoyée avec succès !")
            return redirect('store:product_list')
        else:
            messages.error(request, "Veuillez fournir une réponse ou une quantité de restockage.")
    return render(request, 'store/respond_product_request.html', {'product_request': product_request})

@login_required
@require_POST
def apply_promo_code(request):
    try:
        data = json.loads(request.body)
        promo_code = data.get('promo_code')
        if not promo_code:
            return JsonResponse({'success': False, 'message': 'Code promo requis.'})

        cart = Cart.objects.get(user=request.user)
        if not cart.items.exists():
            return JsonResponse({'success': False, 'message': 'Panier vide.'})

        subtotal = sum(item.subtotal for item in cart.items.all())
        shipping_cost = Decimal('5.00')
        try:
            code = PromoCode.objects.get(code=promo_code)
            if not code.is_valid(user=request.user):
                return JsonResponse({'success': False, 'message': 'Code promo invalide ou expiré.'})

            discount_amount = code.apply(subtotal)
            new_total = subtotal + shipping_cost - discount_amount

            request.session['promo_code'] = promo_code
            request.session['discount_amount'] = float(discount_amount)
            return JsonResponse({
                'success': True,
                'discount_amount': float(discount_amount),
                'new_total': float(new_total)
            })
        except PromoCode.DoesNotExist:
            return JsonResponse({'success': False, 'message': 'Code promo introuvable.'})
    except Exception as e:
        logger.error(f"Erreur lors de l'application du code promo pour {request.user.username}: {str(e)}")
        return JsonResponse({'success': False, 'message': 'Erreur lors de l’application du code.'})

User = get_user_model()

class ReportCreateView(LoginRequiredMixin, View):
    template_name = 'store/report_form.html'

    def get(self, request, *args, **kwargs):
        product_id = request.GET.get('product_id')
        user_id = request.GET.get('user_id')
        form = ReportForm()
        return render(request, self.template_name, {
            'form': form,
            'product_id': product_id,
            'user_id': user_id,
        })

    def post(self, request, *args, **kwargs):
        product_id = request.POST.get('product_id')
        user_id = request.POST.get('user_id')
        form = ReportForm(
            request.POST,
            user=request.user,
            product=get_object_or_404(Product, id=product_id) if product_id else None
        )
        if form.is_valid():
            report = form.save(commit=False)
            if user_id:
                report.user = get_object_or_404(User, id=user_id)
            report.save()
            messages.success(request, "Signalement envoyé avec succès.")
            return redirect('store:product_detail', product_id=product_id) if product_id else redirect('store:seller_public_profile', username=report.user.username)
        return render(request, self.template_name, {
            'form': form,
            'product_id': product_id,
            'user_id': user_id,
        })

@login_required
@user_passes_test(is_seller, login_url='store:home')
def seller_order_list(request):
    order_items = OrderItem.objects.filter(product__seller=request.user).select_related('order', 'product')
    orders = {}
    for item in order_items:
        order = item.order
        if order.id not in orders:
            orders[order.id] = {
                'order': order,
                'items': [],
                'total': Decimal('0.00')
            }
        orders[order.id]['items'].append(item)
        orders[order.id]['total'] += item.price * item.quantity

    orders_list = list(orders.values())
    orders_list.sort(key=lambda x: x['order'].created_at, reverse=True)

    return render(request, 'store/seller_order_list.html', {'orders': orders_list})

def autocomplete_search(request):
    query = request.GET.get('q', '').strip()
    suggestions = []
    if query:
        products = Product.objects.filter(
            Q(name__icontains=query) | 
            Q(description__icontains=query) | 
            Q(brand__icontains=query)
        ).values('id', 'name', 'brand')[:5]
        suggestions = list(products)
    return JsonResponse({'suggestions': suggestions})

@login_required
@require_POST
def mark_as_read(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        notification_id = data.get('id')
        try:
            notification = Notification.objects.get(id=notification_id, user=request.user)
            notification.is_read = True
            notification.save()
            logger.info(f"Notification {notification_id} marked as read by {request.user.username}")
            return JsonResponse({'success': True})
        except Notification.DoesNotExist:
            logger.error(f"Notification {notification_id} not found for user {request.user.username}")
            return JsonResponse({'success': False, 'message': 'Notification non trouvée'}, status=404)
    return JsonResponse({'success': False, 'message': 'Méthode non autorisée'}, status=405)

@login_required
@user_passes_test(is_seller, login_url='store:home')
def apply_discount_multiple(request):
    if request.user.user_type != 'seller':
        messages.error(request, "Seuls les vendeurs peuvent gérer les promotions.")
        return redirect('store:product_list')
    
    if request.method == 'POST':
        form = ApplyDiscountForm(request.POST, seller=request.user)
        if form.is_valid():
            products = form.cleaned_data['products']
            percentage = form.cleaned_data['percentage']
            start_date = form.cleaned_data['start_date']
            end_date = form.cleaned_data['end_date']

            for product in products:
                Discount.objects.create(
                    product=product,
                    percentage=percentage,
                    start_date=start_date,
                    end_date=end_date,
                    is_active=True
                )
                # Notification pour les favoris
                favorites = Favorite.objects.filter(product=product)
                for favorite in favorites:
                    Notification.objects.create(
                        user=favorite.user,
                        message=f"Le produit '{product.name}' que vous avez mis en favori est en promotion ! Nouveau prix : {product.discounted_price} €.",
                        notification_type='product_discount',
                        related_object_id=product.id
                    )

            logger.info(f"Discount applied by user {request.user.username}: {percentage}% on {len(products)} products")
            messages.success(request, f"Réduction de {percentage}% appliquée avec succès à {len(products)} produits !")
            return redirect('store:product_list')
        else:
            logger.error(f"Discount application failed for user {request.user.username}: {form.errors}")
            messages.error(request, f"Erreur dans le formulaire. Veuillez vérifier les champs : {form.errors}")
    else:
        form = ApplyDiscountForm(seller=request.user)

    return render(request, 'store/apply_discount.html', {'form': form})


@login_required
def geocode(request):
    """Convertir latitude/longitude en adresse via Nominatim."""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            latitude = float(data.get('latitude'))
            longitude = float(data.get('longitude'))
            response = requests.get(
                'https://nominatim.openstreetmap.org/reverse',
                params={
                    'lat': latitude,
                    'lon': longitude,
                    'format': 'json',
                    'addressdetails': 1
                },
                headers={'User-Agent': 'EcommerceApp/1.0'}
            )
            if response.status_code == 200:
                address_data = response.json().get('address', {})
                address = {
                    'street_address': address_data.get('road', 'Inconnue'),
                    'city': address_data.get('city', '') or address_data.get('town', '') or address_data.get('village', ''),
                    'postal_code': address_data.get('postcode', ''),
                    'country': address_data.get('country', 'Inconnue')
                }
                return JsonResponse({'status': 'success', 'address': address})
            else:
                return JsonResponse({'status': 'error', 'message': 'Erreur lors de la conversion des coordonnées.'}, status=400)
        except Exception as e:
            logger.error(f"Error in geocode view: {e}")
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
    return JsonResponse({'status': 'error', 'message': 'Méthode non autorisée.'}, status=405)
