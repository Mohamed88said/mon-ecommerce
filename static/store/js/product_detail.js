console.log('Script product_detail.js chargé');

document.addEventListener('DOMContentLoaded', function() {
    const productCarousel = new bootstrap.Carousel('#productCarousel-{{ product.id }}', { interval: 3000, pause: 'hover', wrap: true });
    const recommendedCarousel = document.getElementById('recommendedCarousel');
    if (recommendedCarousel) {
        new bootstrap.Carousel(recommendedCarousel, { interval: 5000, wrap: true });
    }

    function switchImage(index, productId) {
        const carousel = new bootstrap.Carousel(`#productCarousel-${productId}`);
        carousel.to(index);
        document.querySelectorAll(`#productCarousel-${productId} .thumbnail`).forEach((thumb, i) => {
            thumb.classList.toggle('active', i === index);
        });
    }

    function showImage(src) {
        const modal = new bootstrap.Modal(document.getElementById('imageModal'));
        document.getElementById('modalImage').src = src;
        modal.show();
        productCarousel.pause();
        document.getElementById('imageModal').addEventListener('hidden.bs.modal', function () {
            productCarousel.cycle();
            document.body.classList.remove('modal-open');
            const backdrop = document.querySelector('.modal-backdrop');
            if (backdrop) backdrop.remove();
        }, { once: true });
    }

    document.querySelectorAll('.rating-input input').forEach(star => {
        star.addEventListener('change', function() {
            const rating = this.value;
            document.querySelectorAll('.rating-star').forEach((label, i) => {
                const icon = label.querySelector('i');
                if (i >= 5 - rating) {
                    icon.classList.remove('far');
                    icon.classList.add('fas');
                } else {
                    icon.classList.remove('fas');
                    icon.classList.add('far');
                }
            });
        });
    });

    document.querySelectorAll('.add-to-cart-detail').forEach(button => {
        button.addEventListener('click', function(e) {
            e.preventDefault();
            const productId = this.getAttribute('data-product-id');
            const csrfToken = getCookie('csrftoken');
            fetch(`/cart/add/${productId}/`, {
                method: 'POST',
                headers: { 'X-CSRFToken': csrfToken, 'Content-Type': 'application/x-www-form-urlencoded' },
                credentials: 'same-origin'
            })
            .then(response => response.redirected ? window.location.href = response.url : response.json())
            .then(data => {
                if (data && data.success) {
                    const icon = this.querySelector('i');
                    const originalText = this.innerHTML;
                    this.innerHTML = '<i class="fas fa-check me-2"></i>Ajouté !';
                    this.classList.remove('btn-primary');
                    this.classList.add('btn-success');
                    setTimeout(() => {
                        this.innerHTML = originalText;
                        this.classList.remove('btn-success');
                        this.classList.add('btn-primary');
                    }, 2000);
                    const cartCount = document.querySelector('.cart-count');
                    if (cartCount) cartCount.textContent = parseInt(cartCount.textContent) + 1;
                } else if (data && data.error) alert(data.error);
            })
            .catch(error => { console.error('Erreur:', error); alert('Une erreur est survenue lors de l\'ajout au panier'); });
        });
    });

    document.querySelectorAll('.toggle-favorite').forEach(button => {
        button.addEventListener('click', function(e) {
            e.preventDefault();
            console.log('Bouton toggle-favorite cliqué pour productId:', this.getAttribute('data-product-id')); // Débogage
            const productId = this.getAttribute('data-product-id');
            const isFavorite = this.getAttribute('data-is-favorite') === 'true';
            const csrfToken = getCookie('csrftoken');
            const icon = this.querySelector('i');
            const textSpan = this.querySelector('span');
            
            fetch(`/products/${productId}/toggle-favorite/`, {
                method: 'POST',
                headers: { 'X-CSRFToken': csrfToken, 'Content-Type': 'application/x-www-form-urlencoded', 'X-Requested-With': 'XMLHttpRequest' },
                credentials: 'same-origin'
            })
            .then(response => {
                console.log('Réponse fetch:', response.status, response.statusText); // Débogage
                if (!response.ok) throw new Error('Erreur réseau');
                return response.json();
            })
            .then(data => {
                console.log('Données reçues:', data); // Débogage
                if (data.status === 'success') {
                    if (data.action === 'added') {
                        icon.classList.add('text-danger');
                        textSpan.textContent = 'Retirer';
                        if (typeof Toastify !== 'undefined') {
                            Toastify({
                                text: "Produit ajouté aux favoris",
                                duration: 3000,
                                close: true,
                                gravity: "top",
                                position: "right",
                                backgroundColor: "#28a745",
                            }).showToast();
                        } else {
                            alert("Produit ajouté aux favoris");
                        }
                    } else {
                        icon.classList.remove('text-danger');
                        textSpan.textContent = 'Ajouter';
                        if (typeof Toastify !== 'undefined') {
                            Toastify({
                                text: "Produit retiré des favoris",
                                duration: 3000,
                                close: true,
                                gravity: "top",
                                position: "right",
                                backgroundColor: "#dc3545",
                            }).showToast();
                        } else {
                            alert("Produit retiré des favoris");
                        }
                    }
                    const favoriteCountElement = document.querySelector('.favorite-count');
                    if (favoriteCountElement) favoriteCountElement.textContent = data.favorite_count;
                    this.setAttribute('data-is-favorite', data.action === 'added' ? 'true' : 'false');
                }
            })
            .catch(error => { console.error('Erreur:', error); alert('Une erreur est survenue lors de la mise à jour des favoris'); });
        });
    });
});