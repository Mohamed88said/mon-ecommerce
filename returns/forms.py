from django import forms
from returns.models import ReturnRequest
from store.models import Order
from django.utils import timezone
from datetime import timedelta

class ReturnRequestForm(forms.ModelForm):
    class Meta:
        model = ReturnRequest
        fields = ['reason', 'image']
        widgets = {
            'reason': forms.Textarea(attrs={'rows': 4, 'placeholder': 'Veuillez expliquer la raison du retour'}),
            'image': forms.FileInput(attrs={'accept': 'image/*'}),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        self.fields['image'].required = False  # Rendre l'image facultative

    def clean_reason(self):
        reason = self.cleaned_data.get('reason')
        if reason and len(reason) > 1000:
            raise forms.ValidationError("La raison du retour ne peut pas dépasser 1000 caractères.")
        return reason

    def clean_image(self):
        image = self.cleaned_data.get('image')
        if image:
            if image.size > 5 * 1024 * 1024:  # 5MB max
                raise forms.ValidationError("L'image ne doit pas dépasser 5 Mo.")
            valid_extensions = ['.jpg', '.jpeg', '.png', '.gif']
            ext = image.name.lower()[-4:]
            if ext not in valid_extensions:
                raise forms.ValidationError("Seuls les formats JPG, JPEG, PNG et GIF sont acceptés.")
        return image

    def clean(self):
        cleaned_data = super().clean()
        instance = self.instance
        if not self.user:
            raise forms.ValidationError("Utilisateur requis pour soumettre une demande de retour.")
        order = instance.order
        if not order:
            raise forms.ValidationError("Commande non spécifiée.")
        if order.status != 'delivered':
            raise forms.ValidationError("Les retours ne sont autorisés que pour les commandes livrées.")
        if order.created_at + timedelta(days=30) < timezone.now():
            raise forms.ValidationError("La période de retour de 30 jours est expirée.")
        if ReturnRequest.objects.filter(order=order, user=self.user).exists():
            raise forms.ValidationError("Une demande de retour existe déjà pour cette commande.")
        return cleaned_data

class ReturnReviewForm(forms.ModelForm):
    class Meta:
        model = ReturnRequest
        fields = ['status', 'rejection_reason']
        widgets = {
            'status': forms.Select(choices=[
                ('PENDING', 'En attente'),
                ('APPROVED', 'Approuvé'),
                ('REJECTED', 'Rejeté'),
            ]),
            'rejection_reason': forms.Textarea(attrs={'rows': 4, 'placeholder': 'Raison du refus (si applicable)'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        status = cleaned_data.get('status')
        rejection_reason = cleaned_data.get('rejection_reason')
        if status == 'REJECTED' and not rejection_reason:
            raise forms.ValidationError("Une raison de refus est requise pour rejeter une demande.")
        if status != 'REJECTED':
            cleaned_data['rejection_reason'] = ''  # Effacer la raison si non rejeté
        return cleaned_data