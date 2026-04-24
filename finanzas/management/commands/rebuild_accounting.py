from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from finanzas.accounting import rebuild_account_balances, sync_invoice_journal, sync_transaction_journal
from finanzas.models import FinancialTransaction, Invoice


class Command(BaseCommand):
    help = "Recalcula balances y asientos automaticos para usuarios."

    def add_arguments(self, parser):
        parser.add_argument("--username", help="Usuario especifico para recalcular")

    def handle(self, *args, **options):
        User = get_user_model()
        if options.get("username"):
            users = User.objects.filter(username=options["username"])
        else:
            users = User.objects.all()

        total_users = 0
        for user in users:
            total_users += 1
            txs = FinancialTransaction.objects.filter(user=user)
            for tx in txs:
                sync_transaction_journal(tx)
            invoices = Invoice.objects.filter(user=user)
            for inv in invoices:
                sync_invoice_journal(inv)
            rebuild_account_balances(user)
            self.stdout.write(self.style.SUCCESS(f"Recalculado usuario {user.username}: {txs.count()} movimientos, {invoices.count()} facturas"))

        if total_users == 0:
            self.stdout.write(self.style.WARNING("No se encontraron usuarios para recalcular."))
