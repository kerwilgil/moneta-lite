(() => {
    const showBrandFallback = (image) => {
        const container = image.closest(".brand-mark");
        if (!container) return;
        container.querySelectorAll(".brand-logo").forEach((logo) => {
            logo.style.display = "none";
        });
        const fallback = container.querySelector(".brand-mark-fallback");
        if (fallback) fallback.style.display = "grid";
    };

    document.querySelectorAll("img.brand-logo").forEach((image) => {
        image.addEventListener("error", () => showBrandFallback(image), { once: true });
    });
})();
