(() => {
    const showServiceFallback = (image) => {
        image.style.display = "none";
        const fallback = image.nextElementSibling;
        if (fallback?.classList.contains("service-logo-fallback") || fallback?.classList.contains("service-icon")) {
            fallback.style.display = "inline-flex";
        }
    };

    const showBrandFallback = (image) => {
        const container = image.closest(".brand-mark");
        if (!container) return;
        container.querySelectorAll(".brand-logo").forEach((logo) => {
            logo.style.display = "none";
        });
        const fallback = container.querySelector(".brand-mark-fallback");
        if (fallback) fallback.style.display = "grid";
    };

    document.querySelectorAll("img.service-logo").forEach((image) => {
        image.addEventListener("error", () => showServiceFallback(image), { once: true });
    });

    document.querySelectorAll("img.brand-logo").forEach((image) => {
        image.addEventListener("error", () => showBrandFallback(image), { once: true });
    });
})();
