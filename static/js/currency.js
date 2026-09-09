(() => {
    const storageKey = "moneta-currency";
    const defaultCurrency = "USD";
    const picker = document.getElementById("currencyMode");

    if (!picker) {
        return;
    }

    const available = Array.from(picker.options).map((option) => option.value);
    const stored = localStorage.getItem(storageKey);
    const initial = available.includes(stored) ? stored : defaultCurrency;

    picker.value = initial;
    document.documentElement.dataset.currency = initial;

    // Expose formatting function globally
    window.MonetaCurrency = {
        format: (value, currency, locale) => {
            const curr = currency || document.documentElement.dataset.currency || defaultCurrency;
            const loc = locale || document.documentElement.lang || 'es-PA';
            try {
                return new Intl.NumberFormat(loc, {
                    style: 'currency',
                    currency: curr,
                    minimumFractionDigits: 2,
                    maximumFractionDigits: 2
                }).format(value);
            } catch (e) {
                return '$' + Number(value).toFixed(2);
            }
        },
        formatPlain: (value, currency, locale) => {
            const curr = currency || document.documentElement.dataset.currency || defaultCurrency;
            const loc = locale || document.documentElement.lang || 'es-PA';
            try {
                return new Intl.NumberFormat(loc, {
                    style: 'currency',
                    currency: curr,
                    minimumFractionDigits: 2,
                    maximumFractionDigits: 2
                }).format(value);
            } catch (e) {
                return '$' + Number(value).toFixed(2);
            }
        }
    };

    picker.value = initial;
    document.documentElement.dataset.currency = initial;

    picker.addEventListener("change", () => {
        const selected = picker.value || defaultCurrency;
        localStorage.setItem(storageKey, selected);
        document.documentElement.dataset.currency = selected;
        window.dispatchEvent(
            new CustomEvent("moneta-currency-change", {
                detail: { currency: selected },
            }),
        );
    });
})();
