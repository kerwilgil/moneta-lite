// Help Center client-side filter. Progressive enhancement: with JS disabled the
// full article list is still shown and links work.
(() => {
    const input = document.getElementById("helpSearch");
    const results = document.getElementById("helpResults");
    if (!input || !results) {
        return;
    }
    const items = Array.from(results.querySelectorAll("[data-help-item]"));
    const groups = Array.from(results.querySelectorAll("[data-help-group]"));
    const empty = results.querySelector("[data-help-empty]");
    const counter = document.querySelector("[data-help-count]");

    // Lower-case and drop combining marks (U+0300..U+036F) so "credito" also
    // matches "crédito", without an accented source literal.
    function normalize(value) {
        const decomposed = (value || "").toLowerCase().normalize("NFD");
        let out = "";
        for (let i = 0; i < decomposed.length; i += 1) {
            const code = decomposed.charCodeAt(i);
            if (code < 0x300 || code > 0x36f) {
                out += decomposed[i];
            }
        }
        return out;
    }

    function apply() {
        const q = normalize(input.value.trim());
        let visible = 0;
        items.forEach((item) => {
            const haystack = normalize(
                item.dataset.title + " " + item.dataset.keywords
            );
            const match = q === "" || haystack.indexOf(q) !== -1;
            item.hidden = !match;
            if (match) {
                visible += 1;
            }
        });
        groups.forEach((group) => {
            group.hidden = !group.querySelector("[data-help-item]:not([hidden])");
        });
        if (empty) {
            empty.hidden = visible !== 0;
        }
        if (counter) {
            counter.textContent = String(visible);
        }
    }

    input.addEventListener("input", apply);
    apply();
})();
