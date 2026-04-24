from datetime import date

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from finanzas.automation import execute_due_recurrings_for_user


class Command(BaseCommand):
    help = "Ejecuta movimientos automaticos vencidos de recurrentes y suscripciones."

    def add_arguments(self, parser):
        parser.add_argument("--username", help="Usuario especifico. Si se omite, procesa todos.")
        parser.add_argument(
            "--scope",
            choices=["all", "recurring", "subscription"],
            default="all",
            help="Filtra si se procesan recurrentes, suscripciones o ambos.",
        )
        parser.add_argument(
            "--run-date",
            help="Fecha de proceso en formato YYYY-MM-DD. Si se omite usa la fecha local.",
        )

    def handle(self, *args, **options):
        run_date = date.fromisoformat(options["run_date"]) if options.get("run_date") else None
        scope = options["scope"]
        is_subscription = None
        if scope == "recurring":
            is_subscription = False
        elif scope == "subscription":
            is_subscription = True

        User = get_user_model()
        if options.get("username"):
            users = User.objects.filter(username=options["username"])
        else:
            users = User.objects.all()

        processed_users = 0
        for user in users:
            processed_users += 1
            stats = execute_due_recurrings_for_user(user, run_date=run_date, is_subscription=is_subscription)
            self.stdout.write(
                self.style.SUCCESS(
                    (
                        f"{user.username}: procesados={stats['processed']}, "
                        f"creados={stats['created_transactions']}, "
                        f"omitidos={stats['skipped_transactions']}, "
                        f"errores={stats['errors']}"
                    )
                )
            )

        if processed_users == 0:
            self.stdout.write(self.style.WARNING("No se encontraron usuarios para procesar."))
