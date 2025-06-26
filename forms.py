from django import forms
from django.utils import timezone
from django.core.exceptions import ValidationError
from .models import Product, Order, Category, Review, Address, ShippingOption, SellerProfile, ProductRequest
from admin_panel.models import Report
from captcha.fields import ReCaptchaField

class ProductForm(forms.ModelForm):
    category = forms.CharField(max_length=100, required=False, label="Catégorie")
    captcha = ReCaptchaField()
    size = forms.ChoiceField(choices=Product.SIZE_CHOICES, required=False, label="Taille")
    brand = forms.CharField(max_length=100, required=False, label="Marque")
    color = forms.CharField(max_length=50, required=False, label="Couleur")
    material = forms.CharField(max_length=100, required=False, label="Matériau")
    discount_percentage = forms.DecimalField(
        max_digits=5,
        decimal_places=2,
        min_value=0,
        max_value=100,
        required=False,
        label="Pourcentage de réduction",
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'ex. 20 pour 20%'})
    )

    class Meta:
        model = Product
        fields = ['category', 'name', 'description', 'price', 'stock', 'image1', 'image2', 'image3', 'size', 'brand', 'color', 'material', 'discount_percentage']
        exclude = ['seller']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control'}),
            'price': forms.NumberInput(attrs={'class': 'form-control'}),
            'stock': forms.NumberInput(attrs={'class': 'form-control'}),
            'image1': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'image2': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'image3': forms.ClearableFileInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk and self.instance.category:
            self.fields['category'].initial = self.instance.category.name
        for field in ['size', 'brand', 'color', 'material', 'discount_percentage']:
            self.fields[field].widget.attrs.update({'class': 'form-control'})

    def clean_category(self):
        category_name = self.cleaned_data.get('category')
        if category_name:
            category, _ = Category.objects.get_or_create(
                name=category_name,
                defaults={'slug': category_name.lower().replace(' ', '-')})
            return category
        return None

    def clean_price(self):
        price = self.cleaned_data.get('price')
        if price is not None and price <= 0:
            raise forms.ValidationError("Le prix doit être supérieur à 0.")
        return price

    def clean_stock(self):
        stock = self.cleaned_data.get('stock')
        if stock is not None and stock < 0:
            raise forms.ValidationError("Le stock ne peut pas être négatif.")
        return stock

    def clean_discount_percentage(self):
        discount_percentage = self.cleaned_data.get('discount_percentage')
        if discount_percentage is not None and (discount_percentage < 0 or discount_percentage > 100):
            raise forms.ValidationError("Le pourcentage de réduction doit être entre 0 et 100.")
        return discount_percentage

    def save(self, **kwargs):
        commit = kwargs.pop('commit', True)
        instance = super().save(commit=False)
        instance.category = self.cleaned_data.get('category')
        instance.size = self.cleaned_data.get('size') if self.cleaned_data.get('size') else None
        instance.brand = self.cleaned_data.get('brand') if self.cleaned_data.get('brand') else None
        instance.color = self.cleaned_data.get('color') if self.cleaned_data.get('color') else None
        instance.material = self.cleaned_data.get('material') if self.cleaned_data.get('material') else None
        instance.discount_percentage = self.cleaned_data.get('discount_percentage') or 0
        if commit:
            instance.save()
        return instance

class OrderStatusForm(forms.ModelForm):
    class Meta:
        model = Order
        fields = ['status']
        widgets = {
            'status': forms.Select(attrs={'class': 'form-control form-select-sm status-select'}, choices=Order.STATUS_CHOICES),
        }

class ReviewForm(forms.ModelForm):
    class Meta:
        model = Review
        fields = ['rating', 'comment']
        widgets = {
            'rating': forms.Select(attrs={'class': 'form-control'}),
            'comment': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

class AddressForm(forms.ModelForm):
    class Meta:
        model = Address
        fields = ['full_name', 'street_address', 'city', 'postal_code', 'country', 'phone_number', 'is_default']
        widgets = {
            'full_name': forms.TextInput(attrs={'class': 'form-control'}),
            'street_address': forms.TextInput(attrs={'class': 'form-control'}),
            'city': forms.TextInput(attrs={'class': 'form-control'}),
            'postal_code': forms.TextInput(attrs={'class': 'form-control'}),
            'country': forms.TextInput(attrs={'class': 'form-control'}),
            'phone_number': forms.TextInput(attrs={'class': 'form-control'}),
            'is_default': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

class ShippingOptionForm(forms.ModelForm):
    class Meta:
        model = ShippingOption
        fields = ['name', 'cost', 'estimated_days', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'cost': forms.NumberInput(attrs={'class': 'form-control'}),
            'estimated_days': forms.NumberInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

class ShippingMethodForm(forms.Form):
    shipping_option = forms.ModelChoiceField(
        queryset=ShippingOption.objects.filter(is_active=True),
        empty_label="Sélectionnez une méthode de livraison",
        widget=forms.RadioSelect,
        label="Méthode de livraison"
    )

class SellerProfileForm(forms.ModelForm):
    class Meta:
        model = SellerProfile
        fields = ['first_name', 'last_name', 'description', 'business_name', 'business_address', 'contact_phone', 'profile_picture']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'business_name': forms.TextInput(attrs={'class': 'form-control'}),
            'business_address': forms.TextInput(attrs={'class': 'form-control'}),
            'contact_phone': forms.TextInput(attrs={'class': 'form-control'}),
            'profile_picture': forms.ClearableFileInput(attrs={'class': 'form-control'}),
        }

class ProductRequestForm(forms.ModelForm):
    email = forms.EmailField(
        required=False,
        help_text="Entrez votre email si vous n'êtes pas connecté.",
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Votre email'})
    )
    message = forms.CharField(
        required=False,
        help_text="Ajoutez des détails sur votre demande (ex. quantité souhaitée, date limite).",
        widget=forms.Textarea(attrs={'class': 'form-control', 'placeholder': 'Ex. Bonjour, je souhaite 5 unités de ce produit d’ici mardi.', 'rows': 4})
    )
    desired_quantity = forms.IntegerField(
        required=False,
        min_value=1,
        help_text="Indiquez la quantité souhaitée.",
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Quantité souhaitée', 'min': 1})
    )
    desired_date = forms.DateField(
        required=False,
        help_text="Indiquez la date à laquelle vous souhaitez le produit.",
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
    )
    captcha = ReCaptchaField()

    class Meta:
        model = ProductRequest
        fields = ['email', 'message', 'desired_quantity', 'desired_date']

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        if user and user.is_authenticated:
            self.fields['email'].widget = forms.HiddenInput()
            self.fields['email'].required = False
        else:
            self.fields['email'].required = True

    def clean(self):
        cleaned_data = super().clean()
        email = cleaned_data.get('email')
        if not self.user or not self.user.is_authenticated:
            if not email:
                raise forms.ValidationError("L'email est requis si vous n'êtes pas connecté.")
        return cleaned_data

class ApplyDiscountForm(forms.Form):
    products = forms.ModelMultipleChoiceField(
        queryset=Product.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        label="Produits à mettre en promotion",
        required=False
    )
    percentage = forms.DecimalField(
        max_digits=5,
        decimal_places=2,
        min_value=0,
        max_value=100,
        label="Pourcentage de réduction (%)",
        error_messages={'max_value': "Le pourcentage ne peut pas dépasser 100.", 'min_value': "Le pourcentage doit être positif."}
    )
    start_date = forms.DateTimeField(
        label="Date de début",
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local'})
    )
    end_date = forms.DateTimeField(
        label="Date de fin",
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local'})
    )

    def __init__(self, *args, seller=None, single_product=None, **kwargs):
        super().__init__(*args, **kwargs)
        if seller:
            if single_product:
                self.fields['products'].queryset = Product.objects.filter(id=single_product.id, seller=seller, is_sold=False, sold_out=False)
                self.fields['products'].initial = [single_product]
                self.fields['products'].widget = forms.HiddenInput()
            else:
                self.fields['products'].queryset = Product.objects.filter(seller=seller, is_sold=False, sold_out=False)

    def clean_start_date(self):
        start_date = self.cleaned_data.get('start_date')
        if start_date:
            if timezone.is_aware(start_date):
                start_date = timezone.make_naive(start_date, timezone.get_default_timezone())
            start_date = timezone.make_aware(start_date, timezone.get_default_timezone())
            now = timezone.now()
            if start_date < now:
                raise forms.ValidationError("La date de début ne peut pas être dans le passé.")
        return start_date

    def clean_end_date(self):
        end_date = self.cleaned_data.get('end_date')
        if end_date:
            if timezone.is_aware(end_date):
                end_date = timezone.make_naive(end_date, timezone.get_default_timezone())
            end_date = timezone.make_aware(end_date, timezone.get_default_timezone())
        return end_date

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        if start_date and end_date and end_date <= start_date:
            raise forms.ValidationError("La date de fin doit être postérieure à la date de début.")
        return cleaned_data

class ReportForm(forms.ModelForm):
    class Meta:
        model = Report
        fields = ['reason', 'description']
        widgets = {
            'reason': forms.Select(choices=[
                ('inappropriate_content', 'Contenu inapproprié'),
                ('fraud', 'Fraude'),
                ('spam', 'Spam'),
                ('other', 'Autre'),
            ]),
            'description': forms.Textarea(attrs={'rows': 4, 'placeholder': 'Décrivez le problème en détail...'}),
        }

    def __init__(self, *args, user=None, product=None, **kwargs):
        self.user = user
        self.product = product
        super().__init__(*args, **kwargs)

    def save(self, commit=True):
        report = super().save(commit=False)
        report.reporter = self.user
        if self.product:
            report.product = self.product
        if commit:
            report.save()
        return report