from django.contrib.auth import get_user_model
from django.conf import settings
from django.core.management.base import CommandError
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Crea o actualiza un usuario administrador inicial."

    def add_arguments(self, parser):
        parser.add_argument("--username", default="admin")
        parser.add_argument("--password", default="admin")
        parser.add_argument("--email", default="admin@local.test")

    def handle(self, *args, **options):
        username = options["username"]
        password = options["password"]
        email = options["email"]
        if not settings.DEBUG and password == "admin":
            raise CommandError("No uses la clave por defecto admin en produccion. Pasa --password con una clave fuerte.")

        User = get_user_model()
        user, created = User.objects.get_or_create(
            username=username,
            defaults={"email": email, "is_staff": True, "is_superuser": True},
        )

        changed = False
        if user.email != email:
            user.email = email
            changed = True
        if not user.is_staff:
            user.is_staff = True
            changed = True
        if not user.is_superuser:
            user.is_superuser = True
            changed = True

        if not user.check_password(password):
            user.set_password(password)
            changed = True

        if changed:
            user.save()

        if created:
            from django.core.cache import cache

            from finanzas.context_processors import _SETUP_CACHE_KEY

            cache.delete(_SETUP_CACHE_KEY)
            self.stdout.write(self.style.SUCCESS(f"Administrador creado: {username}"))
        else:
            self.stdout.write(self.style.SUCCESS(f"Administrador actualizado: {username}"))
