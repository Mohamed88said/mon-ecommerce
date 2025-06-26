from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from .models import Report, UserModeration
from store.models import Product, Notification
from datetime import datetime

User = get_user_model()

class ReportSignalTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        cls.reporter = User.objects.create_user(
            username=f'reporter_{timestamp}',
            email=f'reporter_{timestamp}@example.com',
            password='testpass123'
        )
        cls.target_user = User.objects.create_user(
            username=f'target_{timestamp}',
            email=f'target_{timestamp}@example.com',
            password='testpass123'
        )
        cls.admin_user = User.objects.create_user(
            username=f'admin_{timestamp}',
            email=f'admin_{timestamp}@example.com',
            password='testpass123',
            is_staff=True,
            is_superuser=True
        )
        cls.product = Product.objects.create(
            name='Test Product',
            price=10.99,
            stock=100,
            description='Test description',
            seller=cls.target_user
        )

    def setUp(self):
        self.client = Client()
        self.client.login(username=self.admin_user.username, password='testpass123')

    def test_report_creation(self):
        """Teste la création d'un signalement."""
        report = Report.objects.create(
            reporter=self.reporter,
            user=self.target_user,
            product=self.product,
            reason='inappropriate_content',
            description='Test report',
            status='open'
        )
        self.assertEqual(Report.objects.count(), 1)
        self.assertEqual(report.reporter, self.reporter)
        self.assertEqual(report.user, self.target_user)
        self.assertEqual(report.product, self.product)
        notification = Notification.objects.filter(
            user=self.target_user,
            notification_type='report_received'
        ).first()
        self.assertIsNotNone(notification)
        self.assertEqual(
            notification.message,
            f"Votre compte a été signalé pour : {report.reason}"
        )

    def test_report_detail_page(self):
        """Teste l'affichage de la page de détail du signalement."""
        report = Report.objects.create(
            reporter=self.reporter,
            product=self.product,
            reason='inappropriate_content',
            description='Test report',
            status='open'
        )
        url = reverse('admin_panel:report_detail', args=[report.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'inappropriate_content')
        self.assertContains(response, self.product.name)
        self.assertContains(response, self.target_user.username)

    def test_notify_seller(self):
        """Teste l'action 'Notifier le vendeur'."""
        report = Report.objects.create(
            reporter=self.reporter,
            product=self.product,
            reason='inappropriate_content',
            description='Test report',
            status='open'
        )
        url = reverse('admin_panel:report_detail', args=[report.id])
        response = self.client.post(url, {'action': 'notify_seller'})
        self.assertEqual(response.status_code, 302)
        notification = Notification.objects.filter(
            user=self.target_user,
            notification_type='report_received'
        ).first()
        self.assertIsNotNone(notification)
        self.assertEqual(
            notification.message,
            f"Votre produit '{self.product.name}' a été signalé pour : inappropriate_content"
        )

    def test_delete_product(self):
        """Teste l'action 'Supprimer le produit'."""
        report = Report.objects.create(
            reporter=self.reporter,
            product=self.product,
            reason='inappropriate_content',
            description='Test report',
            status='open'
        )
        url = reverse('admin_panel:report_detail', args=[report.id])
        response = self.client.post(url, {'action': 'delete_product'})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Product.objects.filter(id=self.product.id).count(), 0)
        notification = Notification.objects.filter(
            user=self.target_user,
            notification_type='product_deleted'
        ).first()
        self.assertIsNotNone(notification)
        self.assertEqual(
            notification.message,
            f"Votre produit 'Test Product' a été supprimé suite à un signalement."
        )

    def test_deactivate_seller(self):
        """Teste l'action 'Désactiver le vendeur'."""
        report = Report.objects.create(
            reporter=self.reporter,
            product=self.product,
            reason='inappropriate_content',
            description='Test report',
            status='open'
        )
        url = reverse('admin_panel:report_detail', args=[report.id])
        response = self.client.post(url, {'action': 'deactivate_seller'})
        self.assertEqual(response.status_code, 302)
        self.target_user.refresh_from_db()
        self.assertFalse(self.target_user.is_active)
        notification = Notification.objects.filter(
            user=self.target_user,
            notification_type='account_deactivation_manual'
        ).first()
        self.assertIsNotNone(notification)
        self.assertEqual(
            notification.message,
            "Votre compte a été désactivé par un administrateur suite à un signalement."
        )
        moderation = UserModeration.objects.filter(user=self.target_user, action='ban').first()
        self.assertIsNotNone(moderation)
        self.assertEqual(
            moderation.reason,
            f"Désactivation manuelle via signalement {report.id} pour : inappropriate_content"
        )