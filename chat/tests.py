from django.test import TestCase
from channels.testing import WebsocketCommunicator
from django.contrib.auth import get_user_model
from store.models import Conversation, Message, Product, Category
from .consumers import ChatConsumer
from django.urls import reverse

User = get_user_model()

class ChatTests(TestCase):
    def setUp(self):
        self.user1 = User.objects.create_user(username='user1', email='user1@example.com', password='pass123', user_type='buyer')
        self.user2 = User.objects.create_user(username='user2', email='user2@example.com', password='pass123', user_type='seller')
        self.category = Category.objects.create(name='Test Category', slug='test-category')
        self.product = Product.objects.create(
            seller=self.user2,
            category=self.category,
            name='Test Product',
            description='Test Description',
            price=100,
            stock=10
        )
        self.conversation = Conversation.objects.create(
            initiator=self.user1,
            recipient=self.user2,
            product=self.product
        )

    async def test_websocket_connection(self):
        communicator = WebsocketCommunicator(ChatConsumer.as_asgi(), f'/ws/chat/{self.conversation.id}/')
        communicator.scope['user'] = self.user1
        connected, _ = await communicator.connect()
        self.assertTrue(connected)
        await communicator.disconnect()

    async def test_send_and_receive_message(self):
        communicator = WebsocketCommunicator(ChatConsumer.as_asgi(), f'/ws/chat/{self.conversation.id}/')
        communicator.scope['user'] = self.user1
        connected, _ = await communicator.connect()
        self.assertTrue(connected)

        message = {'message': 'Hello, world!'}
        await communicator.send_json_to(message)
        response = await communicator.receive_json_from()
        self.assertEqual(response['message'], 'Hello, world!')
        self.assertEqual(response['sender'], self.user1.username)

        await communicator.disconnect()

    def test_chat_view(self):
        self.client.login(username='user1', password='pass123')
        response = self.client.get(reverse('chat:conversation', kwargs={'conversation_id': self.conversation.id}))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'chat/chat.html')