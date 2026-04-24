from decimal import Decimal

from django.contrib.auth import get_user_model
from django.conf import settings
from django.core.management.base import CommandError
from django.core.management.base import BaseCommand
from django.utils import timezone

from finanzas.models import Account, Category, CreditCard, FinancialTransaction, Invoice, JournalEntry, JournalLine, RecurringPayment


class Command(BaseCommand):
    help = "Crea datos de ejemplo para probar el dashboard."

    def add_arguments(self, parser):
        parser.add_argument("--allow-production", action="store_true")

    def handle(self, *args, **options):
        if not settings.DEBUG and not options["allow_production"]:
            raise CommandError("seed_demo esta bloqueado con DJANGO_DEBUG=0. Usa --allow-production solo si entiendes el riesgo.")

        User = get_user_model()
        user, created = User.objects.get_or_create(
            username="demo",
            defaults={"email": "demo@local.test", "is_staff": True, "is_superuser": True},
        )
        if created:
            user.set_password("demo12345")
            user.save(update_fields=["password"])
        elif not user.is_staff or not user.is_superuser:
            user.is_staff = True
            user.is_superuser = True
            user.save(update_fields=["is_staff", "is_superuser"])

        categories = {
            "Sueldo": Category.CategoryType.INCOME,
            "Comida": Category.CategoryType.EXPENSE,
            "Transporte": Category.CategoryType.EXPENSE,
            "Software": Category.CategoryType.EXPENSE,
            "Tarjeta": Category.CategoryType.EXPENSE,
        }
        category_objs = {}
        for name, category_type in categories.items():
            category_objs[name], _ = Category.objects.get_or_create(
                user=user,
                name=name,
                category_type=category_type,
            )

        bank, _ = Account.objects.get_or_create(
            user=user,
            name="Banco principal",
            defaults={
                "account_type": Account.AccountType.BANK,
                "currency": "USD",
                "opening_balance": Decimal("2500.00"),
                "current_balance": Decimal("2500.00"),
            },
        )
        savings, _ = Account.objects.get_or_create(
            user=user,
            name="Ahorro",
            defaults={
                "account_type": Account.AccountType.SAVINGS,
                "currency": "USD",
                "opening_balance": Decimal("5800.00"),
                "current_balance": Decimal("5800.00"),
            },
        )
        card_account, _ = Account.objects.get_or_create(
            user=user,
            name="Visa personal",
            defaults={
                "account_type": Account.AccountType.CREDIT_CARD,
                "currency": "USD",
                "opening_balance": Decimal("0.00"),
                "current_balance": Decimal("1350.00"),
            },
        )
        CreditCard.objects.get_or_create(
            user=user,
            account=card_account,
            defaults={
                "credit_limit": Decimal("3000.00"),
                "current_debt": Decimal("1350.00"),
                "annual_interest_rate": Decimal("24.00"),
                "statement_day": 15,
                "payment_due_day": 30,
                "minimum_payment_percent": Decimal("3.00"),
            },
        )

        today = timezone.localdate()
        demo_transactions = [
            ("Sueldo quincenal", FinancialTransaction.TransactionType.INCOME, bank, category_objs["Sueldo"], Decimal("1800.00")),
            ("Supermercado", FinancialTransaction.TransactionType.EXPENSE, bank, category_objs["Comida"], Decimal("185.40")),
            ("Transporte semanal", FinancialTransaction.TransactionType.EXPENSE, bank, category_objs["Transporte"], Decimal("42.00")),
            ("Licencia de software", FinancialTransaction.TransactionType.EXPENSE, card_account, category_objs["Software"], Decimal("29.99")),
            ("Pago a tarjeta Visa", FinancialTransaction.TransactionType.CARD_PAYMENT, bank, category_objs["Tarjeta"], Decimal("250.00")),
        ]
        for description, tx_type, account, category, amount in demo_transactions:
            FinancialTransaction.objects.get_or_create(
                user=user,
                description=description,
                date=today,
                defaults={
                    "transaction_type": tx_type,
                    "account": account,
                    "category": category,
                    "amount": amount,
                    "status": FinancialTransaction.Status.CLEARED,
                },
            )

        RecurringPayment.objects.get_or_create(
            user=user,
            name="Internet residencial",
            defaults={
                "account": bank,
                "category": category_objs["Software"],
                "amount": Decimal("55.00"),
                "frequency": RecurringPayment.Frequency.MONTHLY,
                "next_due_date": today.replace(day=min(today.day, 28)),
                "is_subscription": False,
            },
        )
        RecurringPayment.objects.get_or_create(
            user=user,
            name="Streaming familiar",
            defaults={
                "account": card_account,
                "category": category_objs["Software"],
                "amount": Decimal("14.99"),
                "frequency": RecurringPayment.Frequency.MONTHLY,
                "next_due_date": today.replace(day=min(today.day, 28)),
                "is_subscription": True,
            },
        )

        Invoice.objects.get_or_create(
            user=user,
            number="FAC-0001",
            invoice_type=Invoice.InvoiceType.RECEIVED,
            defaults={
                "counterparty": "Proveedor de internet",
                "issue_date": today,
                "due_date": today.replace(day=min(today.day + 5, 28)),
                "subtotal": Decimal("55.00"),
                "tax": Decimal("0.00"),
                "status": Invoice.Status.PENDING,
            },
        )
        Invoice.objects.get_or_create(
            user=user,
            number="FAC-0002",
            invoice_type=Invoice.InvoiceType.ISSUED,
            defaults={
                "counterparty": "Cliente demo",
                "issue_date": today,
                "due_date": today.replace(day=min(today.day + 10, 28)),
                "subtotal": Decimal("450.00"),
                "tax": Decimal("31.50"),
                "status": Invoice.Status.PAID,
            },
        )

        entry, _ = JournalEntry.objects.get_or_create(
            user=user,
            description="Registro inicial de capital",
            date=today,
            defaults={"source": "seed_demo", "posted": True},
        )
        if not entry.lines.exists():
            capital_account, _ = Account.objects.get_or_create(
                user=user,
                name="Capital personal",
                defaults={
                    "account_type": Account.AccountType.CAPITAL,
                    "currency": "USD",
                    "opening_balance": Decimal("0.00"),
                    "current_balance": Decimal("8300.00"),
                },
            )
            JournalLine.objects.create(entry=entry, account=bank, memo="Banco principal", debit=Decimal("2500.00"))
            JournalLine.objects.create(entry=entry, account=savings, memo="Ahorro", debit=Decimal("5800.00"))
            JournalLine.objects.create(entry=entry, account=capital_account, memo="Capital inicial", credit=Decimal("8300.00"))

        self.stdout.write(self.style.SUCCESS("Datos demo creados. Usuario: demo / Clave: demo12345"))
