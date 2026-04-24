(() => {
    const storageKey = "moneta-theme";
    const mediaQuery = window.matchMedia("(prefers-color-scheme: dark)");

    function resolveTheme(mode) {
        if (mode === "auto") {
            return mediaQuery.matches ? "dark" : "light";
        }
        return mode;
    }

    function applyTheme(mode) {
        const resolvedTheme = resolveTheme(mode);
        document.documentElement.dataset.theme = resolvedTheme;
        document.documentElement.dataset.themeMode = mode;
        window.dispatchEvent(
            new CustomEvent("moneta-theme-change", {
                detail: { mode, resolvedTheme },
            })
        );
    }

    const initialMode = localStorage.getItem(storageKey) || "auto";
    applyTheme(initialMode);

    const picker = document.getElementById("themeMode");
    if (picker) {
        picker.value = initialMode;
        picker.addEventListener("change", (event) => {
            const mode = event.target.value;
            localStorage.setItem(storageKey, mode);
            applyTheme(mode);
        });
    }

    mediaQuery.addEventListener("change", () => {
        const mode = localStorage.getItem(storageKey) || "auto";
        if (mode === "auto") {
            applyTheme(mode);
        }
    });
})();
