"""Edition and feature-gate helpers for Moneta packages."""

from functools import wraps

from django.conf import settings
from django.contrib import messages
from django.shortcuts import redirect


LITE_FEATURES = frozenset({
    "reports", "transactions", "invoices", "subscriptions", "credit_cards",
    "settings", "admin_link", "exports_basic",
})


def feature_enabled(name):
    """Check whether the current settings enable a feature."""
    return name in LITE_FEATURES and name in settings.APP_FEATURES


def edition_payload():
    return {"key": "lite", "label": "Lite"}


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
