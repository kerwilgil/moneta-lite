from django.apps import AppConfig


def _on_login_failed(sender, credentials, request, **kwargs):
    if request is None:
        return
    from .security import record_login_failure

    record_login_failure(request, credentials.get("username", ""))


def _on_login_succeeded(sender, request, user, **kwargs):
    from .security import clear_login_failures

    clear_login_failures(request, user.get_username())


class FinanzasConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "finanzas"
    verbose_name = "Finanzas personales"

    def ready(self):
        from django.contrib.auth.signals import user_logged_in, user_login_failed

        user_login_failed.connect(_on_login_failed, dispatch_uid="finanzas.login_failed_lockout")
        user_logged_in.connect(_on_login_succeeded, dispatch_uid="finanzas.login_succeeded_lockout")
