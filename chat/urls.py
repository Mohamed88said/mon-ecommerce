from django.urls import path
from . import views

app_name = 'chat'

urlpatterns = [
    path('conversation/<int:conversation_id>/', views.ChatView.as_view(), name='conversation'),
]