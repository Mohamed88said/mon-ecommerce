from django.urls import path
from . import views

app_name = 'store'

urlpatterns = [
    path('', views.home, name='home'),
    path('products/', views.product_list, name='product_list'),
    path('products/<int:product_id>/', views.product_detail, name='product_detail'),
    path('products/<str:category_slug>/', views.product_list, name='product_list_category'),
    path('products/create/', views.product_create, name='product_create'),
    path('products/<int:pk>/update/', views.product_update, name='product_update'),
    path('products/<int:pk>/delete/', views.product_delete, name='product_delete'),
    path('cart/', views.cart, name='cart'),
    path('cart/add/<int:product_id>/', views.add_to_cart, name='add_to_cart'),
    path('cart/remove/<int:item_id>/', views.remove_from_cart, name='remove_from_cart'),
    path('cart/update/<int:item_id>/', views.update_cart, name='update_cart'),
    path('address/add/', views.add_address, name='add_address'),
    path('checkout/', views.checkout, name='checkout'),
    path('geocode/', views.geocode, name='geocode'),  # Nouvel endpoint
    path('payment/process/', views.process_payment, name='process_payment'),
    path('payment/success/<int:order_id>/', views.payment_success, name='payment_success'),
    path('orders/', views.order_history, name='order_history'),
    path('orders/<int:order_id>/', views.order_detail, name='order_detail'),
    path('seller/orders/', views.seller_order_list, name='seller_order_list'),
    path('discount/apply/', views.apply_discount, name='apply_discount'),
    path('discount/apply/<int:product_id>/', views.apply_discount_for_product, name='apply_discount_for_product'),
    path('discount/apply-multiple/', views.apply_discount_multiple, name='apply_discount_multiple'),
    path('orders/<int:order_id>/status/', views.update_order_status, name='update_order_status'),
    path('products/<int:product_id>/mark-sold/', views.mark_as_sold, name='mark_as_sold'),
    path('products/<int:product_id>/request/', views.product_request, name='product_request'),
    path('product-request/<int:request_id>/respond/', views.respond_product_request, name='respond_product_request'),
    path('favorites/toggle/<int:product_id>/', views.toggle_favorite, name='toggle_favorite'),
    path('favorites/', views.favorites, name='favorites'),
    path('notifications/', views.notifications, name='notifications'),
    path('notifications/mark-all-read/', views.mark_all_notifications_read, name='mark_all_notifications_read'),
    path('products/<int:product_id>/message-seller/', views.message_seller, name='message_seller'),
    path('chat/<int:conversation_id>/', views.chat, name='chat'),
    path('orders/<int:order_id>/rate-seller/', views.rate_seller, name='rate_seller'),
    path('seller/<str:username>/', views.seller_public_profile, name='seller_public_profile'),
    path('seller/profile/', views.seller_profile, name='seller_profile'),
    path('subscription/create/', views.create_subscription, name='create_subscription'),
    path('subscription/plans/', views.subscription_plans, name='subscription_plans'),
    path('subscription/success/', views.subscription_success, name='subscription_success'),
    path('subscription/cancel/', views.subscription_cancel, name='subscription_cancel'),
    path('stripe/webhook/', views.stripe_webhook, name='stripe_webhook'),
    path('reviews/<int:review_id>/delete/', views.delete_review, name='delete_review'),
    path('reviews/<int:review_id>/reply/', views.reply_to_review, name='reply_to_review'),
    path('search/autocomplete/', views.autocomplete_search, name='autocomplete_search'),
    path('notifications/mark-read/', views.mark_as_read, name='mark_as_read'),
    path('report/', views.ReportCreateView.as_view(), name='report_create'),
    path('orders/<int:order_id>/status/', views.update_order_status, name='update_order_status'),
    path('apply_promo_code/', views.apply_promo_code, name='apply_promo_code'),
]