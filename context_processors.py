
from .models import Product

def categories(request):
    return {
        'categories': Product.objects.values_list('category', flat=True).distinct()
    }