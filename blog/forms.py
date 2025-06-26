from django import forms
from .models import Comment, Post, BlogCategory
from store.models import Product

class CommentForm(forms.ModelForm):
    class Meta:
        model = Comment
        fields = ['content']
        widgets = {
            'content': forms.Textarea(attrs={'rows': 4, 'placeholder': 'Ajoutez votre commentaire...', 'class': 'form-control'}),
        }

class PostForm(forms.ModelForm):
    products = forms.ModelMultipleChoiceField(
        queryset=Product.objects.none(),
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label="Produits associés"
    )

    class Meta:
        model = Post
        fields = ['title', 'slug', 'content', 'image', 'category', 'products', 'is_published']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Titre de l’article'}),
            'slug': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Slug (ex. mon-article)'}),
            'content': forms.Textarea(attrs={'rows': 6, 'class': 'form-control', 'placeholder': 'Contenu de l’article'}),
            'image': forms.FileInput(attrs={'class': 'form-control'}),
            'category': forms.Select(attrs={'class': 'form-control'}),
            'is_published': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user and user.user_type == 'seller':
            self.fields['products'].queryset = Product.objects.filter(seller=user, is_sold=False, sold_out=False, stock__gt=0)