# accounts/admin.py
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser, Profile
from marketing.admin import admin_site  # Importe admin_site depuis marketing

class CustomUserAdmin(UserAdmin):
    model = CustomUser
    list_display = ['username', 'email', 'user_type', 'is_staff', 'is_active']
    list_filter = ['user_type', 'is_staff', 'is_active']
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Informations personnelles', {'fields': ('email', 'user_type')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Dates importantes', {'fields': ('last_login', 'date_joined')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'email', 'user_type', 'password1', 'password2'),
        }),
    )
    search_fields = ['username', 'email']
    ordering = ['username']

class ProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'address', 'phone']
    search_fields = ['user__username', 'user__email']

admin_site.register(CustomUser, CustomUserAdmin)
admin_site.register(Profile, ProfileAdmin)