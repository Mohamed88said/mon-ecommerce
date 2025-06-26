from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView
from store.models import Conversation, Message
from django.shortcuts import get_object_or_404

class ChatView(LoginRequiredMixin, TemplateView):
    template_name = 'chat/chat.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        conversation = get_object_or_404(
            Conversation,
            id=self.kwargs['conversation_id'],
            initiator=self.request.user
        ) | get_object_or_404(
            Conversation,
            id=self.kwargs['conversation_id'],
            recipient=self.request.user
        )
        messages = Message.objects.filter(conversation=conversation).order_by('sent_at')
        context['conversation'] = conversation
        context['messages'] = messages
        return context