from django.test import TestCase
from .models import Category, Product
from accounts.models import CustomUser

class ProductTests(TestCase):
    def setUp(self):
        self.user = CustomUser.objects.create_user(
            username='seller1', email='seller1@example.com', password='testpass123', user_type='seller'
        )
        self.category = Category.objects.create(name='Test Category')
        self.product = Product.objects.create(
            seller=self.user,
            category=self.category,
            name='Test Product',
            description='Test Description',
            price=10.00,
            stock=100
        )

    def test_product_creation(self):
        self.assertEqual(self.product.name, 'Test Product')
        self.assertEqual(self.product.seller.username, 'seller1')






from django.urls import reverse

class ProductViewTests(TestCase):
    def setUp(self):
        self.user = CustomUser.objects.create_user(
            username='buyer1', email='buyer1@example.com', password='testpass123', user_type='buyer'
        )
        self.client.login(username='buyer1', password='testpass123')

    def test_product_list_view(self):
        response = self.client.get(reverse('product_list'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'store/product_list.html')



from django.test import TestCase, Client
from django.urls import reverse
from .models import Category, Product, Order, OrderItem, ProductView
from accounts.models import CustomUser

class SellerDashboardTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.seller = CustomUser.objects.create_user(
            username='seller',
            password='testpass123',
            user_type='seller'
        )
        self.buyer = CustomUser.objects.create_user(
            username='buyer',
            password='testpass123',
            user_type='buyer'
        )
        self.category = Category.objects.create(name='Test Category')
        self.product = Product.objects.create(
            seller=self.seller,
            category=self.category,
            name='Test Product',
            description='Test Description',
            price=100.00,
            stock=10
        )
        self.order = Order.objects.create(
            user=self.buyer,
            total_price=100.00
        )
        OrderItem.objects.create(
            order=self.order,
            product=self.product,
            quantity=1,
            price=100.00
        )
        ProductView.objects.create(
            product=self.product,
            view_count=10
        )

    def test_seller_dashboard_access(self):
        self.client.login(username='seller', password='testpass123')
        response = self.client.get(reverse('store:seller_dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'store/seller_dashboard.html')
        self.assertContains(response, 'Ventes totales')
        self.assertContains(response, '100.00')

    def test_seller_dashboard_non_seller(self):
        self.client.login(username='buyer', password='testpass123')
        response = self.client.get(reverse('store:seller_dashboard'))
        self.assertEqual(response.status_code, 302)  # Redirection
        self.assertTrue(response.url.startswith('/accounts/login/'))

    def test_dashboard_data(self):
        self.client.login(username='seller', password='testpass123')
        response = self.client.get(reverse('store:dashboard_data'))
        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(response.content, {
            'labels': [],
            'data': [],
        })