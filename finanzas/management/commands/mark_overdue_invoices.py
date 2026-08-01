from django.core.management.base import BaseCommand

from finanzas.services import mark_overdue_invoices


class Command(BaseCommand):
    help = "Marca facturas pendientes vencidas. Ejecutar mediante tarea programada, no durante peticiones GET."

    def handle(self, *args, **options):
        updated = mark_overdue_invoices()
        self.stdout.write(self.style.SUCCESS(f"Facturas marcadas como vencidas: {updated}"))
