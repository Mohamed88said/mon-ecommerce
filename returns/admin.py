from django.contrib import admin
from .models import ReturnRequest, Refund
from marketing.admin import admin_site  # Importer admin_site depuis marketing

@admin.register(ReturnRequest)
class ReturnRequestAdmin(admin.ModelAdmin):
    list_display = ('id', 'order', 'user', 'status', 'created_at', 'updated_at')
    list_filter = ('status', 'created_at')
    search_fields = ('order__id', 'user__username', 'reason')
    readonly_fields = ('created_at', 'updated_at')

@admin.register(Refund)
class RefundAdmin(admin.ModelAdmin):
    list_display = ('id', 'return_request', 'amount', 'method', 'created_at', 'updated_at')
    list_filter = ('method', 'created_at')
    search_fields = ('return_request__id', 'method')
    readonly_fields = ('created_at', 'updated_at')

# Enregistrer avec admin_site au lieu de admin.site
admin_site.register(ReturnRequest, ReturnRequestAdmin)
admin_site.register(Refund, RefundAdmin)