import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from store.models import Notification

class NotificationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        # Vérifier si l'utilisateur est dans le scope
        if 'user' not in self.scope or self.scope['user'].is_anonymous:
            print("User is anonymous or not found in scope, closing connection")
            await self.close()
        else:
            self.user = self.scope['user']
            self.group_name = f"user_{self.user.id}"
            print(f"Connecting user: {self.user}")
            try:
                print(f"Adding user {self.user.id} to group {self.group_name}")
                await self.channel_layer.group_add(
                    self.group_name,
                    self.channel_name
                )
                await self.accept()
                unread_count = await self.get_unread_notifications_count()
                print(f"Sending unread count: {unread_count}")
                await self.send(text_data=json.dumps({
                    'type': 'unread_count',
                    'count': unread_count,
                }))
            except Exception as e:
                print(f"Error during connection: {e}")
                await self.close()

    async def disconnect(self, close_code):
        if hasattr(self, 'user') and not self.user.is_anonymous:
            print(f"Disconnecting user {self.user.id} from group {self.group_name}")
            try:
                await self.channel_layer.group_discard(
                    self.group_name,
                    self.channel_name
                )
            except Exception as e:
                print(f"Error during disconnect: {e}")

    async def receive(self, text_data):
        data = json.loads(text_data)
        if data.get('type') == 'mark_as_read':
            await self.mark_notifications_as_read()

    async def send_notification(self, event):
        try:
            await self.send(text_data=json.dumps({
                'type': 'new_notification',
                'message': event['message'],
                'notification_type': event['notification_type'],
                'related_object_id': event['related_object_id'],
            }))

            unread_count = await self.get_unread_notifications_count()
            print(f"Sending updated unread count: {unread_count}")
            await self.send(text_data=json.dumps({
                'type': 'unread_count',
                'count': unread_count,
            }))
        except Exception as e:
            print(f"Error sending notification: {e}")

    @database_sync_to_async
    def get_unread_notifications_count(self):
        return Notification.objects.filter(user=self.user, is_read=False).count()

    @database_sync_to_async
    def mark_notifications_as_read(self):
        Notification.objects.filter(user=self.user, is_read=False).update(is_read=True)