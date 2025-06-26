from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.http import HttpResponseForbidden
from .models import BlogCategory, Post, Comment
from .forms import CommentForm, PostForm
from store.models import Product

def post_list(request):
    posts = Post.objects.filter(is_published=True).order_by('-published_at')
    paginator = Paginator(posts, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    categories = BlogCategory.objects.all()
    return render(request, 'blog/post_list.html', {
        'page_obj': page_obj,
        'categories': categories,
    })

def post_detail(request, slug):
    post = get_object_or_404(Post, slug=slug, is_published=True)
    comments = post.comments.filter(is_approved=True)
    pending_comments = post.comments.filter(is_approved=False) if (request.user.is_staff or request.user == post.author) else []
    related_products = post.products.filter(is_sold=False, sold_out=False, stock__gt=0)

    if request.method == 'POST' and request.user.is_authenticated:
        comment_form = CommentForm(request.POST)
        if comment_form.is_valid():
            comment = comment_form.save(commit=False)
            comment.post = post
            comment.author = request.user
            comment.save()
            messages.success(request, "Votre commentaire a été soumis et est en attente de modération.")
            return redirect('blog:post_detail', slug=slug)
        else:
            messages.error(request, "Erreur dans le formulaire. Veuillez vérifier votre commentaire.")
    else:
        comment_form = CommentForm()

    return render(request, 'blog/post_detail.html', {
        'post': post,
        'comments': comments,
        'pending_comments': pending_comments,
        'comment_form': comment_form,
        'related_products': related_products,
    })

def category_posts(request, category_slug):
    category = get_object_or_404(BlogCategory, slug=category_slug)
    posts = Post.objects.filter(category=category, is_published=True).order_by('-published_at')
    paginator = Paginator(posts, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    categories = BlogCategory.objects.all()
    return render(request, 'blog/post_list.html', {
        'page_obj': page_obj,
        'categories': categories,
        'selected_category': category,
    })

@login_required
def approve_comment(request, comment_id):
    comment = get_object_or_404(Comment, id=comment_id)
    if request.user.is_staff or request.user == comment.post.author:
        comment.is_approved = True
        comment.save()
        messages.success(request, "Commentaire approuvé avec succès.")
    else:
        messages.error(request, "Vous n'êtes pas autorisé à approuver ce commentaire.")
    return redirect('blog:post_detail', slug=comment.post.slug)

@login_required
def create_post(request):
    if request.user.user_type != 'seller':
        return HttpResponseForbidden("Seuls les vendeurs peuvent créer des articles.")
    
    if request.method == 'POST':
        form = PostForm(request.POST, request.FILES, user=request.user)
        if form.is_valid():
            post = form.save(commit=False)
            post.author = request.user
            post.save()
            form.save_m2m()  # Sauvegarde les relations ManyToMany
            messages.success(request, "Article créé avec succès !")
            return redirect('blog:post_detail', slug=post.slug)
        else:
            messages.error(request, "Erreur dans le formulaire. Vérifiez les champs.")
    else:
        form = PostForm(user=request.user)

    return render(request, 'blog/post_form.html', {'form': form})