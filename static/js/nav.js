(() => {
    const toggle = document.getElementById("mobileNavToggle");
    const backdrop = document.getElementById("sidebarBackdrop");
    if (!toggle) return;

    const open = () => {
        document.body.dataset.sidebar = "open";
        toggle.setAttribute("aria-expanded", "true");
    };
    const close = () => {
        document.body.removeAttribute("data-sidebar");
        toggle.setAttribute("aria-expanded", "false");
    };

    toggle.addEventListener("click", () => {
        document.body.dataset.sidebar === "open" ? close() : open();
    });
    backdrop?.addEventListener("click", close);
    document.addEventListener("keydown", (e) => {
        if (e.key === "Escape" && document.body.dataset.sidebar === "open") close();
    });
    document.querySelectorAll(".sidebar .nav-link").forEach((link) => {
        link.addEventListener("click", () => {
            if (window.matchMedia("(max-width: 1100px)").matches) close();
        });
    });
})();
