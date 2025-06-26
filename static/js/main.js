document.addEventListener('DOMContentLoaded', function() {
    // Menu burger
    const menuToggle = document.querySelector('.navbar-toggler');
    const navbarCollapse = document.querySelector('.navbar-collapse');

    if (menuToggle && navbarCollapse) {
        menuToggle.addEventListener('click', function() {
            navbarCollapse.classList.toggle('show');
        });

        document.addEventListener('click', function(event) {
            if (!navbarCollapse.contains(event.target) && !menuToggle.contains(event.target) && navbarCollapse.classList.contains('show')) {
                navbarCollapse.classList.remove('show');
            }
        });
    }

    // Initialisation des tooltips Bootstrap
    const tooltipTriggerList = document.querySelectorAll('[data-bs-toggle="tooltip"]');
    tooltipTriggerList.forEach(tooltipTriggerEl => {
        new bootstrap.Tooltip(tooltipTriggerEl);
    });

    // Animation au scroll avec GSAP
    gsap.registerPlugin(ScrollTrigger);
    const productCards = document.querySelectorAll('.product-card');
    productCards.forEach(card => {
        gsap.from(card, {
            opacity: 0,
            y: 50,
            duration: 0.5,
            scrollTrigger: {
                trigger: card,
                start: 'top 80%',
                toggleActions: 'play none none none'
            }
        });
    });

    // Effet de parallaxe pour la bannière
    const banner = document.querySelector('.hero-banner');
    if (banner) {
        gsap.to(banner, {
            y: 50,
            scrollTrigger: {
                trigger: banner,
                scrub: true
            }
        });
    }

    // Gestion des notifications
    const notificationBadge = document.querySelector('.pulse');
    if (notificationBadge) {
        setInterval(() => {
            notificationBadge.style.transform = 'scale(1.1)';
            setTimeout(() => {
                notificationBadge.style.transform = 'scale(1)';
            }, 300);
        }, 3000);
    }

    // Prévisualisation des images
    document.addEventListener('change', function(e) {
        if (e.target.type === 'file') {
            const file = e.target.files[0];
            if (file) {
                const reader = new FileReader();
                const previewId = e.target.id + '-preview';
                const preview = document.getElementById(previewId);

                reader.onload = function(e) {
                    if (preview) {
                        const img = preview.querySelector('img');
                        if (img) {
                            img.src = e.target.result;
                            img.style.display = 'block';
                            gsap.from(img, {
                                opacity: 0,
                                scale: 0.8,
                                duration: 0.5,
                                ease: 'back.out(1.7)'
                            });
                        }
                    }
                };
                reader.readAsDataURL(file);
            }
        }
    });

    // Animation pour ajout au panier
    const addToCartButtons = document.querySelectorAll('.add-to-cart');
    addToCartButtons.forEach(button => {
        button.addEventListener('click', function() {
            const originalText = this.innerHTML;
            this.innerHTML = '<i class="fas fa-check"></i> Ajouté !';
            this.classList.add('btn-success');

            setTimeout(() => {
                this.innerHTML = originalText;
                this.classList.remove('btn-success');
            }, 2000);

            const cartIcon = document.querySelector('.fa-shopping-cart');
            if (cartIcon) {
                gsap.to(cartIcon, {
                    y: -5,
                    duration: 0.2,
                    yoyo: true,
                    repeat: 1
                });
            }
        });
    });

    // Gestion du carrousel produit
    const productCarousel = document.getElementById('productCarousel');
    if (productCarousel) {
        const carousel = new bootstrap.Carousel(productCarousel, {
            interval: false,
            wrap: true
        });

        const carouselImages = document.querySelectorAll('.carousel-item img');
        carouselImages.forEach(img => {
            img.addEventListener('click', function() {
                const modal = new bootstrap.Modal(document.getElementById('imageModal'));
                const modalImage = document.getElementById('modalImage');
                if (modalImage) {
                    modalImage.src = this.src;
                }
                modal.show();
            });
        });
    }

    // Animation pour le carrousel de recommandations
    const recommendedCarousel = document.getElementById('recommendedCarousel');
    if (recommendedCarousel) {
        const carousel = new bootstrap.Carousel(recommendedCarousel, {
            interval: 5000,
            wrap: true
        });

        const carouselItems = recommendedCarousel.querySelectorAll('.carousel-item');
        carouselItems.forEach(item => {
            gsap.from(item, {
                opacity: 0,
                x: 50,
                duration: 0.5,
                scrollTrigger: {
                    trigger: item,
                    start: 'top 80%',
                    toggleActions: 'play none none none'
                }
            });
        });
    }

    // Smooth scroll pour les ancres
    const anchorLinks = document.querySelectorAll('a[href^="#"]');
    anchorLinks.forEach(anchor => {
        anchor.addEventListener('click', function(e) {
            e.preventDefault();
            const target = document.querySelector(this.getAttribute('href'));
            if (target) {
                window.scrollTo({
                    top: target.offsetTop - 80,
                    behavior: 'smooth'
                });
            }
        });
    });
});

// Fonction getCookie déplacée ici pour être accessible globalement
function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

const csrftoken = getCookie('csrftoken');