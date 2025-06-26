from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from store.models import Product, Category, Order, OrderItem, Notification
from returns.models import ReturnRequest, Refund
from returns.forms import ReturnRequestForm, ReturnReviewForm
from django.core.files.uploadedfile import SimpleUploadedFile
from asgiref.sync import async_to_sync, sync_to_async
from channels.layers import get_channel_layer
from channels.testing import WebsocketCommunicator
from admin_panel.consumers import NotificationConsumer
import stripe
import paypalrestsdk
from unittest.mock import patch
from django.conf import settings
from django.core import mail
import json
from datetime import datetime
from decimal import Decimal
import io
from PIL import Image

User = get_user_model()

class ReturnsTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.buyer = User.objects.create_user(
            username='buyer',
            email='buyer@example.com',
            password='pass123',
            user_type='buyer'
        )
        self.seller = User.objects.create_user(
            username='seller',
            email='seller@example.com',
            password='pass123',
            user_type='seller'
        )
        self.category = Category.objects.create(name='Test Category', slug='test-category')
        self.product = Product.objects.create(
            seller=self.seller,
            category=self.category,
            name='Test Product',
            description='Test Description',
            price=100,
            stock=10
        )
        self.order = Order.objects.create(
            user=self.buyer,
            total=100,
            status='delivered',
            payment_method='card',
            charge_id='ch_test_123',
            seller=self.seller
        )
        self.order_item = OrderItem.objects.create(
            order=self.order,
            product=self.product,
            quantity=1,
            price=100
        )
        image = io.BytesIO()
        Image.new('RGB', (100, 100)).save(image, 'JPEG')
        image.seek(0)
        self.return_request = ReturnRequest.objects.create(
            order=self.order,
            user=self.buyer,
            reason='Defective product',
            status='PENDING',
            image=SimpleUploadedFile('test.jpg', image.getvalue(), content_type='image/jpeg')
        )

    def test_return_request_creation(self):
        self.client.login(username='buyer', password='pass123')
        new_order = Order.objects.create(
            user=self.buyer,
            total=50,
            status='delivered',
            payment_method='card',
            charge_id='ch_test_456',
            seller=self.seller
        )
        OrderItem.objects.create(
            order=new_order,
            product=self.product,
            quantity=1,
            price=50
        )
        image = io.BytesIO()
        Image.new('RGB', (100, 100)).save(image, 'JPEG')
        image.seek(0)
        response = self.client.post(
            reverse('returns:return_create', kwargs={'order_id': new_order.id}),
            {
                'reason': 'Wrong item',
                'image': SimpleUploadedFile('test2.jpg', image.getvalue(), content_type='image/jpeg')
            }
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(ReturnRequest.objects.filter(order=new_order, reason='Wrong item').exists())
        # Vérifier la notification par email
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].subject, f'Nouvelle demande de retour #2')
        # Vérifier la notification en base
        self.assertTrue(Notification.objects.filter(
            user=self.seller,
            notification_type='return_request',
            message__contains='Une demande de retour a été soumise'
        ).exists())

    def test_return_request_list(self):
        self.client.login(username='buyer', password='pass123')
        response = self.client.get(reverse('returns:return_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Defective product')

    def test_return_request_review_approve(self):
        self.client.login(username='seller', password='pass123')
        with patch('stripe.Refund.create') as mock_refund:
            mock_refund.return_value = {'id': 're_test_123'}
            response = self.client.post(
                reverse('returns:return_review', kwargs={'return_id': self.return_request.id}),
                {'status': 'APPROVED'}
            )
            self.assertEqual(response.status_code, 302)
            self.return_request.refresh_from_db()
            self.assertEqual(self.return_request.status, 'APPROVED')
            self.assertTrue(Refund.objects.filter(return_request=self.return_request).exists())
            # Vérifier la notification pour l'acheteur
            self.assertTrue(Notification.objects.filter(
                user=self.buyer,
                notification_type='return_approved',
                message__contains='Votre demande de retour'
            ).exists())

    def test_return_request_review_reject(self):
        self.client.login(username='seller', password='pass123')
        response = self.client.post(
            reverse('returns:return_review', kwargs={'return_id': self.return_request.id}),
            {'status': 'REJECTED', 'rejection_reason': 'Not eligible'}
        )
        self.assertEqual(response.status_code, 302)
        self.return_request.refresh_from_db()
        self.assertEqual(self.return_request.status, 'REJECTED')
        self.assertEqual(self.return_request.rejection_reason, 'Not eligible')
        # Vérifier la notification pour l'acheteur
        self.assertTrue(Notification.objects.filter(
            user=self.buyer,
            notification_type='return_rejected',
            message__contains='Not eligible'
        ).exists())

    def test_return_form_validation(self):
        form_data = {
            'reason': 'Invalid reason' * 100,
            'image': SimpleUploadedFile('test.jpg', b'file_content', content_type='image/jpeg')
        }
        form = ReturnRequestForm(data=form_data, user=self.buyer, instance=ReturnRequest(order=self.order))
        self.assertFalse(form.is_valid())
        self.assertIn('reason', form.errors)

    def test_refunded_order(self):
        self.client.login(username='seller', password='pass123')
        with patch('stripe.Refund.create') as mock_refund:
            mock_refund.return_value = {'id': 're_test_123'}
            response = self.client.post(
                reverse('returns:return_review', kwargs={'return_id': self.return_request.id}),
                {'status': 'APPROVED'}
            )
            self.assertEqual(response.status_code, 302)
            refund = Refund.objects.get(return_request=self.return_request)
            self.assertEqual(refund.amount, self.order.total)
            self.assertEqual(refund.transaction_id, 're_test_123')

    def test_stripe_refund_failure(self):
        self.client.login(username='seller', password='pass123')
        with patch('stripe.Refund.create') as mock_refund:
            mock_refund.side_effect = stripe.error.StripeError('Invalid charge')
            response = self.client.post(
                reverse('returns:return_review', kwargs={'return_id': self.return_request.id}),
                {'status': 'APPROVED'}
            )
            self.assertEqual(response.status_code, 200)
            self.return_request.refresh_from_db()
            self.assertEqual(self.return_request.status, 'PENDING')
            self.assertFalse(Refund.objects.filter(return_request=self.return_request).exists())

    def test_paypal_refund_failure(self):
        self.order.payment_method = 'paypal'
        self.order.save()
        self.client.login(username='seller', password='pass123')
        with patch('paypalrestsdk.Sale.refund') as mock_refund:
            mock_refund.side_effect = paypalrestsdk.exceptions.ResourceNotFound('Sale not found')
            response = self.client.post(
                reverse('returns:return_review', kwargs={'return_id': self.return_request.id}),
                {'status': 'APPROVED'}
            )
            self.assertEqual(response.status_code, 200)
            self.return_request.refresh_from_db()
            self.assertEqual(self.return_request.status, 'PENDING')
            self.assertFalse(Refund.objects.filter(return_request=self.return_request).exists())

    def test_concurrent_refund_prevention(self):
        self.client.login(username='seller', password='pass123')
        with patch('stripe.Refund.create') as mock_refund:
            mock_refund.return_value = {'id': 're_test_123'}
            ReturnRequest.objects.filter(id=self.return_request.id).update(status='APPROVED')
            response = self.client.post(
                reverse('returns:return_review', kwargs={'return_id': self.return_request.id}),
                {'status': 'APPROVED'}
            )
            self.assertEqual(response.status_code, 302)
            self.assertEqual(Refund.objects.filter(return_request=self.return_request).count(), 1)

    async def test_return_notification_websocket(self):
        await sync_to_async(self.client.login)(username='seller', password='pass123')
        communicator = WebsocketCommunicator(NotificationConsumer.as_asgi(), '/ws/notifications/')
        communicator.scope['user'] = self.buyer
        connected, _ = await communicator.connect()
        self.assertTrue(connected)

        with patch('stripe.Refund.create') as mock_refund:
            mock_refund.return_value = {'id': 're_test_123'}
            response = await sync_to_async(self.client.post)(
                reverse('returns:return_review', kwargs={'return_id': self.return_request.id}),
                {'status': 'APPROVED'}
            )
            self.assertEqual(response.status_code, 302)

            notification = await communicator.receive_json_from()
            self.assertEqual(notification['type'], 'new_notification')
            self.assertIn('Votre demande de retour', notification['message'])

        await communicator.disconnect()

    def test_unauthorized_access(self):
        self.client.login(username='buyer', password='pass123')
        response = self.client.get(reverse('returns:return_review', kwargs={'return_id': self.return_request.id}))
        self.assertEqual(response.status_code, 403)

    def test_no_seller_associated(self):
        order_no_seller = Order.objects.create(
            user=self.buyer,
            total=50,
            status='delivered',
            payment_method='card',
            charge_id='ch_test_789'
        )
        self.client.login(username='buyer', password='pass123')
        image = io.BytesIO()
        Image.new('RGB', (100, 100)).save(image, 'JPEG')
        image.seek(0)
        response = self.client.post(
            reverse('returns:return_create', kwargs={'order_id': order_no_seller.id}),
            {
                'reason': 'Wrong item',
                'image': SimpleUploadedFile('test2.jpg', image.getvalue(), content_type='image/jpeg')
            }
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Aucun vendeur associé à cette commande')

    def test_email_notification_on_return_request(self):
        self.client.login(username='buyer', password='pass123')
        new_order = Order.objects.create(
            user=self.buyer,
            total=50,
            status='delivered',
            payment_method='card',
            charge_id='ch_test_456',
            seller=self.seller
        )
        OrderItem.objects.create(
            order=new_order,
            product=self.product,
            quantity=1,
            price=50
        )
        image = io.BytesIO()
        Image.new('RGB', (100, 100)).save(image, 'JPEG')
        image.seek(0)
        response = self.client.post(
            reverse('returns:return_create', kwargs={'order_id': new_order.id}),
            {
                'reason': 'Wrong item',
                'image': SimpleUploadedFile('test2.jpg', image.getvalue(), content_type='image/jpeg')
            }
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].subject, f'Nouvelle demande de retour #2')
        self.assertIn('Une demande de retour a été soumise', mail.outbox[0].body)