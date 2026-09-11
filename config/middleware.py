from django.conf import settings

_DEFAULT_CSP = (
    "default-src 'self'; "
    "script-src 'self' cdn.jsdelivr.net; "
    "style-src 'self' cdn.jsdelivr.net; "
    "font-src 'self'; "
    "img-src 'self' data: cdn.simpleicons.org; "
    "connect-src 'self'; "
    "frame-ancestors 'none'; "
    "base-uri 'self'; "
    "form-action 'self'; "
    "object-src 'none';"
)


class SecurityHeadersMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self.csp = getattr(settings, "MONETA_CSP", _DEFAULT_CSP)

    def __call__(self, request):
        response = self.get_response(request)
        if self.csp:
            response.setdefault("Content-Security-Policy", self.csp)
        return response
