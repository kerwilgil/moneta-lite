(() => {
    const toggle = document.getElementById("mobileNavToggle");
    const backdrop = document.getElementById("sidebarBackdrop");
    const sidebar = document.getElementById("app-sidebar");
    if (!toggle) return;

    const focusableSelector = "a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex='-1'])";
    const isMobile = () => window.matchMedia("(max-width: 1100px)").matches;

    const open = () => {
        document.body.dataset.sidebar = "open";
        toggle.setAttribute("aria-expanded", "true");
        if (isMobile()) {
            window.requestAnimationFrame(() => sidebar?.querySelector(focusableSelector)?.focus());
        }
    };
    const close = (restoreFocus = true) => {
        document.body.removeAttribute("data-sidebar");
        toggle.setAttribute("aria-expanded", "false");
        if (restoreFocus && isMobile()) toggle.focus();
    };

    toggle.addEventListener("click", () => {
        document.body.dataset.sidebar === "open" ? close() : open();
    });
    backdrop?.addEventListener("click", () => close());
    document.addEventListener("keydown", (e) => {
        if (e.key === "Escape" && document.body.dataset.sidebar === "open") {
            close();
            return;
        }
        if (e.key !== "Tab" || document.body.dataset.sidebar !== "open" || !isMobile() || !sidebar) return;
        const focusable = [...sidebar.querySelectorAll(focusableSelector)];
        if (!focusable.length) return;
        const first = focusable[0];
        const last = focusable[focusable.length - 1];
        if (e.shiftKey && document.activeElement === first) {
            e.preventDefault();
            last.focus();
        } else if (!e.shiftKey && document.activeElement === last) {
            e.preventDefault();
            first.focus();
        }
    });
    document.querySelectorAll(".sidebar .nav-link").forEach((link) => {
        link.addEventListener("click", () => {
            if (isMobile()) close(false);
        });
    });
})();
