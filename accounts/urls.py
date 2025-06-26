from django.urls import path, include
from . import views

app_name = 'accounts'  # Ajout du namespace pour éviter les conflits

urlpatterns = [
    path('', include('allauth.urls')),  # Inclut toutes les URLs de django-allauth
    path('profile/', views.profile, name='profile'),
    path('add_address/', views.add_address, name='add_address'),
    path('seller/<str:username>/', views.seller_profile, name='seller_profile'),
    path('update-profile-picture/', views.update_profile_picture, name='update_profile_picture'),  # Nouvelle URL
    path('delete-account/', views.delete_account, name='delete_account'),  # Assurez-vous que cette ligne est présente
]