(() => {
    const storedTheme = localStorage.getItem("moneta-theme") || "auto";
    const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
    const resolvedTheme = storedTheme === "auto" ? (prefersDark ? "dark" : "light") : storedTheme;
    document.documentElement.dataset.theme = resolvedTheme;
    document.documentElement.dataset.themeMode = storedTheme;
})();
