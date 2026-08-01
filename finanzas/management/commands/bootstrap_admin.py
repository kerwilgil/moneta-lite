import getpass
import os
import sys

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from finanzas.models import SetupState


class Command(BaseCommand):
    help = "Crea o actualiza un administrador sin exponer su clave en la linea de comandos."

    def add_arguments(self, parser):
        parser.add_argument("--username", default="admin")
        parser.add_argument("--email", default="admin@local.test")
        parser.add_argument(
            "--password-env",
            default="MONETA_ADMIN_PASSWORD",
            help="Variable de entorno que contiene la clave (por defecto MONETA_ADMIN_PASSWORD).",
        )

    def handle(self, *args, **options):
        username = options["username"]
        email = options["email"]
        password_env = options["password_env"]
        password = os.getenv(password_env, "")
        if not password:
            if not sys.stdin.isatty():
                raise CommandError(f"Define {password_env}; las claves no se aceptan como argumento CLI.")
            password = getpass.getpass("Clave del administrador: ")
            if password != getpass.getpass("Confirmar clave: "):
                raise CommandError("Las claves no coinciden.")

        User = get_user_model()
        candidate = User(username=username, email=email)
        try:
            validate_password(password, user=candidate)
        except ValidationError as exc:
            raise CommandError(" ".join(exc.messages)) from exc

        with transaction.atomic():
            user, created = User.objects.select_for_update().get_or_create(
                username=username,
                defaults={"email": email, "is_staff": True, "is_superuser": True},
            )
            user.email = email
            user.is_staff = True
            user.is_superuser = True
            user.set_password(password)
            user.save()
            SetupState.objects.update_or_create(pk=1, defaults={"consumed_at": timezone.now()})

        action = "creado" if created else "actualizado"
        self.stdout.write(self.style.SUCCESS(f"Administrador {action}: {username}"))
