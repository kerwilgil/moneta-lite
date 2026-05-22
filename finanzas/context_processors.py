from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache

from .product import edition_payload, feature_enabled

_SETUP_CACHE_KEY = "moneta_setup_allowed"


def product_context(request):
    User = get_user_model()
    setup_allowed = cache.get(_SETUP_CACHE_KEY)
    if setup_allowed is None:
        setup_allowed = not User.objects.exists()
        # Short TTL while no users exist so setup completes quickly; long TTL once users exist.
        cache.set(_SETUP_CACHE_KEY, setup_allowed, timeout=120 if setup_allowed else 86400)
    return {
        "product": {
            "name": getattr(settings, "APP_NAME", "Moneta"),
            "description_es": getattr(
                settings,
                "APP_DESCRIPTION_ES",
                "Moneta - finanzas personales, contabilidad y flujo de caja.",
            ),
            "description_en": getattr(
                settings,
                "APP_DESCRIPTION_EN",
                "Moneta - personal finance, accounting and cash flow.",
            ),
            "favicon": getattr(settings, "APP_FAVICON", "img/moneta_favicon.png"),
            "og_image": getattr(settings, "APP_OG_IMAGE", "img/moneta_logo.png"),
            "logo_light": getattr(settings, "APP_LOGO_LIGHT", "img/moneta_icon_light.png"),
            "logo_dark": getattr(settings, "APP_LOGO_DARK", "img/moneta_icon_dark.png"),
            "login_title_es": getattr(settings, "APP_LOGIN_TITLE_ES", "Ingresar"),
            "login_title_en": getattr(settings, "APP_LOGIN_TITLE_EN", "Sign in"),
            "login_description_es": getattr(
                settings,
                "APP_LOGIN_DESCRIPTION_ES",
                "Registra tus finanzas, deuda y capital desde un solo panel.",
            ),
            "login_description_en": getattr(
                settings,
                "APP_LOGIN_DESCRIPTION_EN",
                "Track finance, debt and capital from a single workspace.",
            ),
        },
        "edition": edition_payload(),
        "features": {
            "reports": feature_enabled("reports"),
            "transactions": feature_enabled("transactions"),
            "invoices": feature_enabled("invoices"),
            "recurring": feature_enabled("recurring"),
            "subscriptions": feature_enabled("subscriptions"),
            "credit_cards": feature_enabled("credit_cards"),
            "ledger": feature_enabled("ledger"),
            "net_income": feature_enabled("net_income"),
            "settings": feature_enabled("settings"),
            "admin_link": feature_enabled("admin_link"),
            "exports_basic": feature_enabled("exports_basic"),
            "exports_advanced": feature_enabled("exports_advanced"),
        },
        "setup_allowed": setup_allowed,
    }
