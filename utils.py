from django.db.models import Sum, Count, F
from .models import OrderItem, Product

def get_sales_metrics(user):
    """
    Calcule les métriques de ventes pour un vendeur.
    """
    total_sales = OrderItem.objects.filter(
        product__seller=user,
        order__status='delivered'
    ).aggregate(total=Sum(F('quantity') * F('price')))['total'] or 0.00

    total_orders = OrderItem.objects.filter(
        product__seller=user
    ).values('order').distinct().count()

    products_in_stock = Product.objects.filter(
        seller=user, stock__gt=0, is_sold=False, sold_out=False
    ).count()

    return {
        'total_sales': total_sales,
        'total_orders': total_orders,
        'products_in_stock': products_in_stock,
    }