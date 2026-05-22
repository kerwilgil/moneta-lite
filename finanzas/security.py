"""Security helpers shared by authentication views and signals."""

from django.conf import settings


def client_ip(request):
    """Return the client IP used for login lockout decisions.

    X-Forwarded-For is ignored unless explicitly trusted. Direct clients can
    spoof that header, so reverse-proxy deployments must opt in with
    MONETA_TRUST_X_FORWARDED_FOR=1.
    """
    if getattr(settings, "MONETA_TRUST_X_FORWARDED_FOR", False):
        forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
        if forwarded:
            return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "unknown")
