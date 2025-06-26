from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.contrib import messages
from .forms import ProfileForm, AddressForm
from .models import Profile, Address, CustomUser
from store.models import Product  # Assumer que Product est dans store.models

def user_login(request):
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            return redirect('home')
    else:
        form = AuthenticationForm()
    return render(request, 'accounts/login.html', {'form': form})

@login_required
def profile(request):
    profile, created = Profile.objects.get_or_create(user=request.user)
    if request.method == 'POST':
        profile_form = ProfileForm(request.POST, request.FILES, instance=profile)
        if profile_form.is_valid():
            profile_form.save()
            messages.success(request, "Informations mises à jour avec succès !")
            return redirect('accounts:profile')
        else:
            messages.error(request, "Erreur lors de la mise à jour des informations.")
    else:
        profile_form = ProfileForm(instance=profile)
    addresses = Address.objects.filter(profile=profile)
    return render(request, 'accounts/profile.html', {'profile_form': profile_form, 'addresses': addresses})

@login_required
def add_address(request):
    if request.method == 'POST':
        address_form = AddressForm(request.POST)
        if address_form.is_valid():
            address = address_form.save(commit=False)
            address.profile = request.user.profile
            address.save()
            messages.success(request, "Adresse ajoutée avec succès !")
            return redirect('accounts:profile')
        else:
            messages.error(request, "Erreur lors de l'ajout de l'adresse.")
    else:
        address_form = AddressForm()
    return render(request, 'accounts/profile.html', {'address_form': address_form})

@login_required
def update_profile_picture(request):
    if request.method == 'POST':
        profile = request.user.profile
        if 'profile_picture' in request.FILES:
            profile.profile_picture = request.FILES['profile_picture']
            profile.save()
            messages.success(request, "Photo de profil mise à jour avec succès !")
        else:
            messages.error(request, "Veuillez sélectionner une image.")
        return redirect('accounts:profile')
    return redirect('accounts:profile')

@login_required
def seller_profile(request, username):
    seller = CustomUser.objects.get(username=username)
    if seller.user_type != 'seller':
        return redirect('home')
    profile = seller.profile
    products = Product.objects.filter(seller=seller)
    return render(request, 'accounts/seller_profile.html', {'profile': profile, 'products': products})

def user_logout(request):
    logout(request)
    return redirect('home')


@login_required
def delete_account(request):
    if request.method == 'POST':
        user = request.user
        profile = user.profile
        # Supprimer les adresses associées
        Address.objects.filter(profile=profile).delete()
        # Supprimer les produits (si vendeur)
        if user.user_type == 'seller':
            Product.objects.filter(seller=user).delete()
        # Supprimer le profil et l'utilisateur
        profile.delete()
        user.delete()
        messages.success(request, "Votre compte a été supprimé avec succès.")
        return redirect('home')
    return redirect('accounts:profile')  # Affichage sécurisé, mais la suppression ne se fait que via POST