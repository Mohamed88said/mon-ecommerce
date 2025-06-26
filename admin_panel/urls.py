from django.urls import path
from . import views

app_name = 'admin_panel'

urlpatterns = [
    path('', views.AdminDashboardView.as_view(), name='admin_dashboard'),
    path('users/', views.UserListView.as_view(), name='user_list'),
    path('products/', views.ProductListView.as_view(), name='product_list'),
    path('products/<int:pk>/edit/', views.ProductUpdateView.as_view(), name='product_edit'),
    path('products/moderation/', views.ProductModerationView.as_view(), name='product_moderation'),
    path('products/moderation/<int:moderation_id>/approve/', views.ApproveModerationView.as_view(), name='approve_moderation'),
    path('products/moderation/<int:moderation_id>/reject/', views.RejectModerationView.as_view(), name='reject_moderation'),
    path('reports/', views.ReportListView.as_view(), name='report_list'),
    path('reports/<int:pk>/', views.ReportDetailView.as_view(), name='report_detail'),
    path('export/users/', views.export_users_csv, name='export_users'),
    path('export/moderations/', views.export_moderations_csv, name='export_moderations'),
    path('export/reports/', views.export_reports_csv, name='export_reports'),
    path('trigger_notification/', views.trigger_notification, name='trigger_notification'),
    path('reviews/', views.review_list, name='review_list'),
    path('reviews/<int:pk>/action/', views.review_action, name='review_action'),
    path('deliveries/', views.delivery_list, name='delivery_list'), 
]