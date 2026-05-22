from django.apps import AppConfig

from .security import client_ip

_LOGIN_MAX_ATTEMPTS = 10
_LOGIN_LOCKOUT_SECONDS = 900  # 15 minutes


def _on_login_failed(sender, credentials, request, **kwargs):
    if request is None:
        return
    from django.core.cache import cache
    ip = client_ip(request)
    attempts_key = f"moneta_login_attempts_{ip}"
    attempts = cache.get(attempts_key, 0) + 1
    if attempts >= _LOGIN_MAX_ATTEMPTS:
        cache.set(f"moneta_login_lock_{ip}", True, _LOGIN_LOCKOUT_SECONDS)
        cache.delete(attempts_key)
    else:
        cache.set(attempts_key, attempts, _LOGIN_LOCKOUT_SECONDS)


class FinanzasConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "finanzas"
    verbose_name = "Finanzas personales"

    def ready(self):
        from django.contrib.auth.signals import user_login_failed
        user_login_failed.connect(_on_login_failed, dispatch_uid="finanzas.login_failed_lockout")
