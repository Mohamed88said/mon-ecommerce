from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html
from .models import UserModeration, ProductModeration, Report
from store.models import Notification, Product
from django.contrib import messages
from django.contrib.auth import get_user_model

User = get_user_model()

print("Chargement de admin_panel/admin.py")  # Débogage

@admin.register(UserModeration)
class UserModerationAdmin(admin.ModelAdmin):
    list_display = ('user', 'action', 'reason', 'created_at')
    search_fields = ('user__username', 'reason')
    list_filter = ('action', 'created_at')

@admin.register(ProductModeration)
class ProductModerationAdmin(admin.ModelAdmin):
    list_display = ('product', 'status', 'reason', 'created_at')
    search_fields = ('product__name', 'reason')
    list_filter = ('status', 'created_at')

# @admin.register(Report)
# class ReportAdmin(admin.ModelAdmin):
#     list_display = ('reporter', 'user', 'product', 'reason', 'status', 'created_at', 'get_detail_link')
#     search_fields = ('reporter__username', 'user__username', 'product__name', 'reason')
#     list_filter = ('status', 'created_at')
#     actions = ['mark_as_resolved', 'notify_seller', 'delete_product', 'deactivate_seller']
#     change_form_template = 'admin/admin_panel/report/detail.html'

#     def get_detail_link(self, obj):
#         """Affiche un lien vers la page de détail du signalement."""
#         try:
#             url = reverse('admin:admin_panel_report_change', args=[obj.id])
#             print(f"URL générée pour signalement {obj.id} : {url}")  # Débogage
#         except Exception as e:
#             print(f"Erreur de résolution d'URL pour signalement {obj.id} : {e}")
#             return '-'
#         return format_html('<a href="{}">Voir détails</a>', url)
#     get_detail_link.short_description = 'Détails'

#     def mark_as_resolved(self, request, queryset):
#         for report in queryset:
#             report.status = 'resolved'
#             report.save()
#             Notification.objects.create(
#                 user=report.reporter,
#                 message=f"Votre signalement concernant {report.reason} a été résolu.",
#                 notification_type='report_resolved',
#                 related_object_id=report.id
#             )
#         self.message_user(request, f"{queryset.count()} signalement(s) marqué(s) comme résolu(s).")
#     mark_as_resolved.short_description = "Marquer les signalements sélectionnés comme résolus"

#     def notify_seller(self, request, queryset):
#         for report in queryset:
#             if report.product and report.product.seller:
#                 Notification.objects.create(
#                     user=report.product.seller,
#                     message=f"Votre produit '{report.product.name}' a été signalé pour : {report.reason}",
#                     notification_type='report_received',
#                     related_object_id=report.id
#                 )
#             elif report.user:
#                 Notification.objects.create(
#                     user=report.user,
#                     message=f"Votre compte a été signalé pour : {report.reason}",
#                     notification_type='report_received',
#                     related_object_id=report.id
#                 )
#         self.message_user(request, f"{queryset.count()} vendeur(s) notifié(s).")
#     notify_seller.short_description = "Notifier le vendeur"

#     def delete_product(self, request, queryset):
#         deleted_count = 0
#         for report in queryset:
#             if report.product:
#                 product_name = report.product.name
#                 report.product.delete()
#                 deleted_count += 1
#                 Notification.objects.create(
#                     user=report.product.seller,
#                     message=f"Votre produit '{product_name}' a été supprimé suite à un signalement.",
#                     notification_type='product_deleted',
#                     related_object_id=report.id
#                 )
#         self.message_user(request, f"{deleted_count} produit(s) supprimé(s).")
#     delete_product.short_description = "Supprimer le produit signalé"

#     def deactivate_seller(self, request, queryset):
#         deactivated_count = 0
#         for report in queryset:
#             seller = None
#             if report.product and report.product.seller:
#                 seller = report.product.seller
#             elif report.user:
#                 seller = report.user
#             if seller and seller.is_active:
#                 seller.is_active = False
#                 seller.save()
#                 deactivated_count += 1
#                 Notification.objects.create(
#                     user=seller,
#                     message="Votre compte a été désactivé par un administrateur suite à un signalement.",
#                     notification_type='account_deactivation_manual',
#                     related_object_id=report.id
#                 )
#                 UserModeration.objects.create(
#                     user=seller,
#                     moderator=request.user,
#                     action='ban',
#                     reason=f"Désactivation manuelle via signalement {report.id} pour : {report.reason}"
#                 )
#         self.message_user(request, f"{deactivated_count} vendeur(s) désactivé(s).")
#     deactivate_seller.short_description = "Désactiver le vendeur"
    