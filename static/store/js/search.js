document.addEventListener('DOMContentLoaded', function () {
    const searchInput = document.querySelector('input[name="q"]');
    const suggestionsContainer = document.createElement('div');
    suggestionsContainer.className = 'autocomplete-suggestions';
    searchInput.parentNode.appendChild(suggestionsContainer);

    searchInput.addEventListener('input', function () {
        const query = this.value.trim();
        if (query.length < 2) {
            suggestionsContainer.innerHTML = '';
            return;
        }

        fetch(`/store/autocomplete/?q=${encodeURIComponent(query)}`)
            .then(response => response.json())
            .then(data => {
                suggestionsContainer.innerHTML = '';
                data.suggestions.forEach(suggestion => {
                    const div = document.createElement('div');
                    div.className = 'suggestion-item';
                    div.textContent = `${suggestion.name} (${suggestion.brand})`;
                    div.addEventListener('click', () => {
                        searchInput.value = suggestion.name;
                        suggestionsContainer.innerHTML = '';
                        searchInput.form.submit();
                    });
                    suggestionsContainer.appendChild(div);
                });
            })
            .catch(error => console.error('Error fetching suggestions:', error));
    });

    // Masquer les suggestions si on clique ailleurs
    document.addEventListener('click', function (e) {
        if (!suggestionsContainer.contains(e.target) && e.target !== searchInput) {
            suggestionsContainer.innerHTML = '';
        }
    });
});