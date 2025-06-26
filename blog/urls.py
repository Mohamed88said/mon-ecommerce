from django.urls import path
from . import views

app_name = 'blog'

urlpatterns = [
    path('', views.post_list, name='post_list'),
    path('post/<slug:slug>/', views.post_detail, name='post_detail'),
    path('category/<slug:category_slug>/', views.category_posts, name='category_posts'),
    path('comment/<int:comment_id>/approve/', views.approve_comment, name='approve_comment'),
    path('create/', views.create_post, name='create_post'),
]