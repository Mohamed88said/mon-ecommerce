document.addEventListener('change', function(e) {
    if (e.target.type === 'file') {
        const file = e.target.files[0];
        if (file) {
            const reader = new FileReader();
            reader.onload = function(e) {
                const preview = document.getElementById(e.target.id + '-preview');
                if (preview) {
                    const img = preview.querySelector('img');
                    if (img) {
                        img.src = e.target.result;
                        img.style.display = 'block';
                        gsap.from(img, { opacity: 0, scale: 0.8, duration: 0.5, ease: "back.out(1.7)" });
                    }
                }
            };
            reader.readAsDataURL(file);
        }
    }
});