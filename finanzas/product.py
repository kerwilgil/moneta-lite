"""Edition and feature-gate helpers for Moneta packages."""

from functools import wraps

from django.conf import settings
from django.contrib import messages
from django.shortcuts import redirect


EDITION_LABELS = {
    "demo": "Demo",
    "lite": "Lite",
    "pro": "Pro",
    "personal": "Personal",
}

EDITION_FEATURES = {
    "demo": {
        "reports",
        "transactions",
        "invoices",
        "recurring",
        "subscriptions",
        "credit_cards",
        "ledger",
        "net_income",
        "settings",
        "admin_link",
        "exports_basic",
        "exports_advanced",
    },
    "pro": {
        "reports",
        "transactions",
        "invoices",
        "recurring",
        "subscriptions",
        "credit_cards",
        "ledger",
        "net_income",
        "settings",
        "admin_link",
        "exports_basic",
        "exports_advanced",
    },
    "personal": {
        "reports",
        "transactions",
        "invoices",
        "recurring",
        "subscriptions",
        "credit_cards",
        "ledger",
        "net_income",
        "settings",
        "admin_link",
        "exports_basic",
        "exports_advanced",
    },
    "lite": {
        "reports",
        "transactions",
        "invoices",
        "subscriptions",
        "credit_cards",
        "settings",
        "admin_link",
        "exports_basic",
    },
}


def normalize_edition(value):
    """Normalize an environment edition name to a supported edition key."""
    edition = (value or "demo").strip().lower()
    return edition if edition in EDITION_FEATURES else "demo"


def edition_features(value):
    """Return the enabled feature set for an edition key."""
    return set(EDITION_FEATURES[normalize_edition(value)])


def edition_label(value):
    """Return a display label for an edition key."""
    return EDITION_LABELS.get(normalize_edition(value), "Demo")


def feature_enabled(name):
    """Check whether the current settings enable a feature."""
    return name in set(getattr(settings, "APP_FEATURES", set()))


def edition_payload():
    """Build template context metadata for the active edition."""
    edition = normalize_edition(getattr(settings, "APP_EDITION", "demo"))
    return {
        "key": edition,
        "label": edition_label(edition),
        "is_demo": edition == "demo",
        "is_lite": edition == "lite",
        "is_pro": edition == "pro",
        "is_personal": edition == "personal",
    }


def require_feature(name):
    """Decorator that redirects users away from disabled edition features."""
    def decorator(view_func):
        @wraps(view_func)
        def wrapped(request, *args, **kwargs):
            if feature_enabled(name):
                return view_func(request, *args, **kwargs)

            english = (getattr(request, "LANGUAGE_CODE", "") or "").lower().startswith("en")
            if english:
                messages.error(request, "This module is available only in the Pro edition.")
            else:
                messages.error(request, "Este modulo esta disponible solo en la edicion Pro.")
            return redirect("finanzas:dashboard")

        return wrapped

    return decorator
