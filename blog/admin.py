# blog/admin.py
from django.contrib import admin
from .models import BlogCategory, Post, Comment
from marketing.admin import admin_site  # Importe admin_site depuis marketing

@admin.register(BlogCategory, site=admin_site)
class BlogCategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'created_at']
    prepopulated_fields = {'slug': ('name',)}

@admin.register(Post, site=admin_site)
class PostAdmin(admin.ModelAdmin):
    list_display = ['title', 'author', 'category', 'published_at', 'is_published']
    list_filter = ['is_published', 'category', 'author']
    search_fields = ['title', 'content']
    prepopulated_fields = {'slug': ('title',)}
    filter_horizontal = ('products',)

@admin.register(Comment, site=admin_site)
class CommentAdmin(admin.ModelAdmin):
    list_display = ['post', 'author', 'created_at', 'is_approved']
    list_filter = ['is_approved', 'post']
    actions = ['approve_comments']

    def approve_comments(self, request, queryset):
        queryset.update(is_approved=True)
    approve_comments.short_description = "Approuver les commentaires sélectionnés"