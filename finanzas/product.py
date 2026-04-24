from functools import wraps

from django.conf import settings
from django.contrib import messages
from django.shortcuts import redirect


EDITION_LABELS = {
    "lite": "Lite",
}

EDITION_FEATURES = {
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
    return "lite"


def edition_features(value):
    return set(EDITION_FEATURES[normalize_edition(value)])


def edition_label(value):
    return EDITION_LABELS.get(normalize_edition(value), "Lite")


def feature_enabled(name):
    return name in set(getattr(settings, "APP_FEATURES", set()))


def edition_payload():
    edition = normalize_edition(getattr(settings, "APP_EDITION", "lite"))
    return {
        "key": edition,
        "label": edition_label(edition),
        "is_demo": False,
        "is_lite": edition == "lite",
        "is_pro": False,
        "is_personal": False,
    }


def require_feature(name):
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
