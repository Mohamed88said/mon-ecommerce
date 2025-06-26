import logging
import csv
from django.shortcuts import redirect, get_object_or_404, render
from django.contrib import messages
from django.views.generic import ListView, TemplateView, View, UpdateView, DetailView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth import get_user_model
from django.urls import reverse_lazy, reverse
from django.http import HttpResponse
from django.db.models import Sum, Count, Q
from django.db.models.functions import TruncMonth
from .models import ProductModeration, Report, UserModeration
from store.models import Product, Notification, Order, Review
from django.core.mail import send_mail
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from django.contrib.auth.decorators import login_required

logger = logging.getLogger('admin_panel')
User = get_user_model()

class AdminAccessMixin(UserPassesTestMixin):
    def test_func(self):
        if not self.request.user.is_authenticated:
            return False
        return self.request.user.is_staff

    def handle_no_permission(self):
        return redirect(reverse_lazy('login') + '?next=' + self.request.path)

class AdminDashboardView(LoginRequiredMixin, AdminAccessMixin, TemplateView):
    template_name = 'admin_panel/dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['total_users'] = User.objects.count()
        context['pending_products'] = ProductModeration.objects.filter(status='pending').count()
        context['approved_products'] = ProductModeration.objects.filter(status='approved').count()
        context['open_reports'] = Report.objects.filter(status='open').count()
        context['total_revenue'] = Order.objects.aggregate(total=Sum('total'))['total'] or 0
        context['recent_orders'] = Order.objects.order_by('-created_at')[:5]
        
        monthly_approvals = ProductModeration.objects.filter(status='approved') \
            .annotate(month=TruncMonth('created_at')) \
            .values('month') \
            .annotate(count=Count('id')) \
            .order_by('month')
        context['monthly_approvals'] = {
            'labels': [item['month'].strftime('%Y-%m') for item in monthly_approvals] if monthly_approvals.exists() else ['Pas de données'],
            'data': [float(item['count']) for item in monthly_approvals] if monthly_approvals.exists() else [0]
        }

        monthly_revenue = Order.objects.annotate(month=TruncMonth('created_at')) \
            .values('month') \
            .annotate(total=Sum('total')) \
            .order_by('month')
        context['monthly_revenue'] = {
            'labels': [item['month'].strftime('%Y-%m') for item in monthly_revenue] if monthly_revenue.exists() else ['Pas de données'],
            'data': [float(item['total'] or 0) for item in monthly_revenue] if monthly_revenue.exists() else [0]
        }

        monthly_reports = Report.objects.annotate(month=TruncMonth('created_at')) \
            .values('month') \
            .annotate(count=Count('id')) \
            .order_by('month')
        context['monthly_reports'] = {
            'labels': [item['month'].strftime('%Y-%m') for item in monthly_reports] if monthly_reports.exists() else ['Pas de données'],
            'data': [item['count'] for item in monthly_reports] if monthly_reports.exists() else [0]
        }
        return context

class UserListView(LoginRequiredMixin, AdminAccessMixin, ListView):
    model = User
    template_name = 'admin_panel/user_list.html'
    context_object_name = 'users'

    def get_queryset(self):
        queryset = User.objects.all()
        search_query = self.request.GET.get('search', '')
        if search_query:
            queryset = queryset.filter(
                Q(username__icontains=search_query) | 
                Q(email__icontains=search_query)
            )
        return queryset

    def post(self, request, *args, **kwargs):
        user_id = request.POST.get('user_id')
        action = request.POST.get('action')
        user = get_object_or_404(User, id=user_id)
        if action == 'toggle_active':
            if User.objects.filter(is_staff=True).count() <= 1 and user.is_staff:
                messages.error(request, "Vous ne pouvez pas désactiver le dernier compte staff.")
            else:
                user.is_active = not user.is_active
                user.save()
                messages.success(request, f"L'utilisateur {user.username} a été {'activé' if user.is_active else 'désactivé'}.")
        return redirect('admin_panel:user_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_query'] = self.request.GET.get('search', '')
        return context

class ProductListView(LoginRequiredMixin, AdminAccessMixin, ListView):
    model = Product
    template_name = 'admin_panel/product_list.html'
    context_object_name = 'products'

    def get_queryset(self):
        queryset = Product.objects.select_related('seller', 'category').all()
        search_query = self.request.GET.get('search', '')
        if search_query:
            queryset = queryset.filter(
                Q(name__icontains=search_query) | 
                Q(description__icontains=search_query) | 
                Q(seller__username__icontains=search_query)
            )
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_query'] = self.request.GET.get('search', '')
        return context

class ProductUpdateView(LoginRequiredMixin, AdminAccessMixin, UpdateView):
    model = Product
    template_name = 'admin_panel/product_edit.html'
    fields = ['name', 'description', 'price', 'stock', 'category', 'seller']
    success_url = reverse_lazy('admin_panel:product_list')

    def form_valid(self, form):
        messages.success(self.request, f"Le produit '{form.instance.name}' a été mis à jour.")
        return super().form_valid(form)

class ProductModerationView(LoginRequiredMixin, AdminAccessMixin, ListView):
    model = ProductModeration
    template_name = 'admin_panel/product_moderation.html'
    context_object_name = 'moderations'

    def get_queryset(self):
        print("Récupération des ProductModeration pour affichage")
        queryset = ProductModeration.objects.select_related('product', 'moderator').all()
        search_query = self.request.GET.get('search', '')
        if search_query:
            queryset = queryset.filter(
                Q(product__name__icontains=search_query) | 
                Q(product__description__icontains=search_query) | 
                Q(reason__icontains=search_query)
            )
        print(f"Nombre de moderations trouvées : {queryset.count()}")
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_query'] = self.request.GET.get('search', '')
        return context

class ApproveModerationView(LoginRequiredMixin, AdminAccessMixin, View):
    def post(self, request, moderation_id):
        logger.info(f"Approbation demandée pour moderation_id={moderation_id}")
        moderation = get_object_or_404(ProductModeration, id=moderation_id)
        if request.method == 'POST' and moderation.status == 'pending':
            moderation.status = 'approved'
            moderation.moderator = request.user
            moderation.save()
            messages.success(request, f'Le produit "{moderation.product.name}" a été approuvé.')
            Notification.objects.create(
                user=moderation.product.seller,
                message=f'Votre produit "{moderation.product.name}" a été approuvé.',
                notification_type='product_approved',
                related_object_id=moderation.product.id
            )
            send_mail(
                'Produit approuvé',
                f'Bonjour {moderation.product.seller.username},\nVotre produit "{moderation.product.name}" a été approuvé.\nCordialement,\nL\'équipe LuxeShop',
                'from@example.com',
                [moderation.product.seller.email],
                fail_silently=True,
            )
            logger.info(f"Produit {moderation.product.name} approuvé par {request.user.username}")
        else:
            messages.error(request, "Ce produit n'est pas en attente d'approbation ou la requête est invalide.")
        return redirect('admin_panel:product_moderation')

class RejectModerationView(LoginRequiredMixin, AdminAccessMixin, View):
    def post(self, request, moderation_id):
        logger.info(f"Rejet demandé pour moderation_id={moderation_id}, reason={request.POST.get('reason')}")
        moderation = get_object_or_404(ProductModeration, id=moderation_id)
        if request.method == 'POST' and moderation.status == 'pending':
            reason = request.POST.get('reason', 'Sans raison spécifiée')
            moderation.status = 'rejected'
            moderation.moderator = request.user
            moderation.reason = reason
            moderation.save()
            messages.success(request, f'Le produit "{moderation.product.name}" a été rejeté.')
            Notification.objects.create(
                user=moderation.product.seller,
                message=f'Votre produit "{moderation.product.name}" a été rejeté. Raison : {reason}',
                notification_type='product_rejected',
                related_object_id=moderation.product.id
            )
            send_mail(
                'Produit rejeté',
                f'Bonjour {moderation.product.seller.username},\nVotre produit "{moderation.product.name}" a été rejeté. Raison : {reason}\nCordialement,\nL\'équipe LuxeShop',
                'from@example.com',
                [moderation.product.seller.email],
                fail_silently=True,
            )
            logger.info(f"Produit {moderation.product.name} rejeté par {request.user.username} avec raison : {reason}")
        else:
            messages.error(request, "Ce produit n'est pas en attente d'approbation ou la requête est invalide.")
        return redirect('admin_panel:product_moderation')

class ReportListView(LoginRequiredMixin, AdminAccessMixin, ListView):
    model = Report
    template_name = 'admin_panel/report_list.html'
    context_object_name = 'reports'

    def get_queryset(self):
        queryset = Report.objects.select_related('product', 'user', 'reporter').all()
        search_query = self.request.GET.get('search', '')
        status_filter = self.request.GET.get('status', '')
        date_from = self.request.GET.get('date_from', '')
        date_to = self.request.GET.get('date_to', '')
        reporter_filter = self.request.GET.get('reporter', '')

        if search_query:
            queryset = queryset.filter(
                Q(product__name__icontains=search_query) |
                Q(user__username__icontains=search_query) |
                Q(reporter__username__icontains=search_query) |
                Q(description__icontains=search_query)
            )
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        if date_from:
            queryset = queryset.filter(created_at__gte=date_from)
        if date_to:
            queryset = queryset.filter(created_at__lte=date_to)
        if reporter_filter:
            queryset = queryset.filter(reporter__username__icontains=reporter_filter)

        return queryset.order_by('-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_query'] = self.request.GET.get('search', '')
        context['status_filter'] = self.request.GET.get('status', '')
        context['date_from'] = self.request.GET.get('date_from', '')
        context['date_to'] = self.request.GET.get('date_to', '')
        context['reporter_filter'] = self.request.GET.get('reporter', '')
        return context

    def post(self, request, *args, **kwargs):
        report_id = request.POST.get('report_id')
        action = request.POST.get('action')
        report = get_object_or_404(Report, id=report_id)
        if action == 'resolve':
            report.status = 'resolved'
            report.save()
            Notification.objects.create(
                user=report.reporter,
                message=f"Votre signalement concernant '{report.product.name if report.product else report.user.username}' a été résolu.",
                notification_type='report_resolved'
            )
            send_mail(
                'Signalement résolu',
                f'Bonjour {report.reporter.username},\nVotre signalement concernant "{report.product.name if report.product else report.user.username}" a été résolu.\nCordialement,\nL\'équipe LuxeShop',
                'from@example.com',
                [report.reporter.email],
                fail_silently=True,
            )
            messages.success(request, f"Signalement {report.id} résolu.")
        elif action == 'reject':
            report.status = 'rejected'
            report.save()
            Notification.objects.create(
                user=report.reporter,
                message=f"Votre signalement concernant '{report.product.name if report.product else report.user.username}' a été rejeté.",
                notification_type='report_rejected'
            )
            send_mail(
                'Signalement rejeté',
                f'Bonjour {report.reporter.username},\nVotre signalement concernant "{report.product.name if report.product else report.user.username}" a été rejeté.\nCordialement,\nL\'équipe LuxeShop',
                'from@example.com',
                [report.reporter.email],
                fail_silently=True,
            )
            messages.success(request, f"Signalement {report.id} rejeté.")
        elif action == 'notify_user':
            notification_message = request.POST.get('notification_message', '')
            if notification_message and report.user:
                Notification.objects.create(
                    user=report.user,
                    message=notification_message,
                    notification_type='custom_notification'
                )
                send_mail(
                    'Notification personnalisée',
                    f'Bonjour,\n{notification_message}\nCordialement,\nL\'équipe LuxeShop',
                    'from@example.com',
                    [report.user.email],
                    fail_silently=True,
                )
                messages.success(request, f"Utilisateur notifié pour le signalement {report.id}.")
        return redirect('admin_panel:report_list')

class ReportDetailView(LoginRequiredMixin, AdminAccessMixin, DetailView):
    model = Report
    template_name = 'admin_panel/report/detail.html'
    context_object_name = 'report'

    def get(self, request, *args, **kwargs):
        response = super().get(request, *args, **kwargs)
        print(f"Report dans get: {self.object}")
        return response

    def post(self, request, *args, **kwargs):
        report = self.get_object()
        print(f"Report dans post: {report}")
        action = request.POST.get('action')
        if action == 'notify_seller':
            if report.product and report.product.seller:
                Notification.objects.create(
                    user=report.product.seller,
                    message=f"Votre produit '{report.product.name}' a été signalé pour : {report.reason}",
                    notification_type='report_received',
                    related_object_id=report.id
                )
                messages.success(request, f"Vendeur notifié pour le signalement {report.id}.")
            elif report.user:
                Notification.objects.create(
                    user=report.user,
                    message=f"Votre compte a été signalé pour : {report.reason}",
                    notification_type='report_received',
                    related_object_id=report.id
                )
                messages.success(request, f"Utilisateur notifié pour le signalement {report.id}.")
        elif action == 'delete_product':
            if report.product:
                product_name = report.product.name
                report.product.delete()
                Notification.objects.create(
                    user=report.product.seller,
                    message=f"Votre produit '{product_name}' a été supprimé suite à un signalement.",
                    notification_type='product_deleted',
                    related_object_id=report.id
                )
                messages.success(request, f"Produit {product_name} supprimé pour le signalement {report.id}.")
        elif action == 'mark_as_resolved':
            report.status = 'resolved'
            report.save()
            Notification.objects.create(
                user=report.reporter,
                message=f"Votre signalement concernant '{report.product.name if report.product else report.user.username}' a été résolu.",
                notification_type='report_resolved'
            )
            messages.success(request, f"Signalement {report.id} marqué comme résolu.")
        elif action == 'deactivate_seller':
            seller = report.product.seller if report.product else report.user
            if seller and seller.is_active:
                seller.is_active = False
                seller.save()
                Notification.objects.create(
                    user=seller,
                    message="Votre compte a été désactivé par un administrateur suite à un signalement.",
                    notification_type='account_deactivation_manual',
                    related_object_id=report.id
                )
                UserModeration.objects.create(
                    user=seller,
                    moderator=request.user,
                    action='ban',
                    reason=f"Désactivation manuelle via signalement {report.id} pour : {report.reason}"
                )
                messages.success(request, f"Compte de {seller.username} désactivé pour le signalement {report.id}.")
        return redirect(reverse('admin_panel:report_detail', args=[report.id]) if report.id else reverse('admin_panel:report_list'))

def trigger_notification(request):
    from .models import Report
    User = get_user_model()
    user = User.objects.first()
    product = Product.objects.first()
    report = Report.objects.create(product=product, reporter=user, reason='Test', description='Test notification')
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f'user_{user.id}',  # Utilise le group_name spécifique à l'utilisateur
        {
            'type': 'send_notification',
            'message': f'Nouveau signalement #{report.id} par {user.username} pour {product.name}',
            'notification_type': 'report_created',
            'related_object_id': report.id,
        }
    )
    messages.success(request, f"Notification test créée pour le signalement #{report.id}.")
    return redirect(reverse('admin_panel:report_list'))

def export_users_csv(request):
    users = User.objects.all().values('id', 'username', 'email', 'is_active', 'is_staff', 'date_joined')
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="users_export.csv"'
    writer = csv.writer(response)
    writer.writerow(['ID', 'Username', 'Email', 'Is Active', 'Is Staff', 'Date Joined'])
    for user in users:
        writer.writerow([user['id'], user['username'], user['email'], user['is_active'], user['is_staff'], user['date_joined']])
    return response

def export_moderations_csv(request):
    moderations = ProductModeration.objects.select_related('product', 'moderator').all().values(
        'id', 'product__name', 'status', 'reason', 'moderator__username', 'created_at'
    )
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="moderations_export.csv"'
    writer = csv.writer(response)
    writer.writerow(['ID', 'Product Name', 'Status', 'Reason', 'Moderator', 'Created At'])
    for mod in moderations:
        writer.writerow([mod['id'], mod['product__name'], mod['status'], mod['reason'] or '', mod['moderator__username'] or '', mod['created_at']])
    return response

def export_reports_csv(request):
    reports = Report.objects.select_related('reporter', 'product').all().values(
        'id', 'product__name', 'reporter__username', 'status', 'description', 'created_at'
    )
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="reports_export.csv"'
    writer = csv.writer(response)
    writer.writerow(['ID', 'Product Name', 'Reporter', 'Status', 'Description', 'Created At'])
    for report in reports:
        writer.writerow([report['id'], report['product__name'], report['reporter__username'], report['status'], report['description'] or '', report['created_at']])
    return response

@login_required
def review_list(request):
    reviews = Review.objects.all().select_related('product', 'user')  # Tous les reviews pour l'admin
    return render(request, 'admin_panel/review_list.html', {'reviews': reviews})

@login_required
def review_action(request, pk):
    review = get_object_or_404(Review, pk=pk)
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'approve':
            review.is_approved = True
            messages.success(request, "L'avis a été approuvé.")
        elif action == 'reject':
            review.is_approved = False
            messages.success(request, "L'avis a été rejeté.")
        review.save()
    return redirect('admin_panel:review_list')


from django.shortcuts import render
from delivery.models import Delivery

def delivery_list(request):
    deliveries = Delivery.objects.all()
    return render(request, 'admin_panel/delivery_list.html', {'deliveries': deliveries})