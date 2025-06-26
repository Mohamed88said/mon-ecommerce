import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from store.models import Notification

class NotificationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        if self.scope["user"].is_anonymous:
            await self.close()
        else:
            self.user = self.scope["user"]
            self.group_name = f"user_{self.user.id}"

            await self.channel_layer.group_add(
                self.group_name,
                self.channel_name
            )
            await self.accept()

            unread_count = await self.get_unread_notifications_count()
            await self.send(text_data=json.dumps({
                'type': 'unread_count',
                'count': unread_count,
            }))

    async def disconnect(self, close_code):
        if not self.scope["user"].is_anonymous:
            await self.channel_layer.group_discard(
                self.group_name,
                self.channel_name
            )

    async def receive(self, text_data):
        data = json.loads(text_data)
        if data.get('type') == 'mark_as_read':
            await self.mark_notifications_as_read()

    async def send_notification(self, event):
        await self.send(text_data=json.dumps({
            'type': 'new_notification',
            'message': event['message'],
            'notification_type': event['notification_type'],
            'related_object_id': event['related_object_id'],
        }))

        unread_count = await self.get_unread_notifications_count()
        await self.send(text_data=json.dumps({
            'type': 'unread_count',
            'count': unread_count,
        }))

    @database_sync_to_async
    def get_unread_notifications_count(self):
        return Notification.objects.filter(user=self.user, is_read=False).count()

    @database_sync_to_async
    def mark_notifications_as_read(self):
        Notification.objects.filter(user=self.user, is_read=False).update(is_read=True)