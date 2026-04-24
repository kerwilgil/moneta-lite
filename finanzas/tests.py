from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from .accounting import rebuild_account_balances
from .forms import RecurringPaymentForm, TransactionForm
from .models import Account, Category, CreditCard, FinancialTransaction, RecurringPayment


class FinanceLogicTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="tester", password="secret")
        self.checking = Account.objects.create(
            user=self.user,
            name="Banco",
            account_type=Account.AccountType.CHECKING,
            opening_balance=Decimal("1000.00"),
            current_balance=Decimal("1000.00"),
        )
        self.investment = Account.objects.create(
            user=self.user,
            name="Broker",
            account_type=Account.AccountType.INVESTMENT,
            opening_balance=Decimal("5000.00"),
            current_balance=Decimal("5500.00"),
        )
        self.expense_category = Category.objects.create(
            user=self.user,
            name="Seguros",
            category_type=Category.CategoryType.EXPENSE,
        )
        self.income_category = Category.objects.create(
            user=self.user,
            name="Nomina",
            category_type=Category.CategoryType.INCOME,
        )

    def test_rebuild_resets_transaction_accounts_but_preserves_manual_investments(self):
        tx = FinancialTransaction.objects.create(
            user=self.user,
            account=self.checking,
            category=self.expense_category,
            transaction_type=FinancialTransaction.TransactionType.EXPENSE,
            description="Compra",
            amount=Decimal("100.00"),
            date=date(2026, 4, 1),
        )
        rebuild_account_balances(self.user)
        self.checking.refresh_from_db()
        self.investment.refresh_from_db()
        self.assertEqual(self.checking.current_balance, Decimal("900.00"))
        self.assertEqual(self.investment.current_balance, Decimal("5500.00"))

        tx.delete()
        rebuild_account_balances(self.user)
        self.checking.refresh_from_db()
        self.assertEqual(self.checking.current_balance, Decimal("1000.00"))

    def test_credit_card_statement_values_drive_display_calculations(self):
        account = Account.objects.create(
            user=self.user,
            name="Visa",
            account_type=Account.AccountType.CREDIT_CARD,
            opening_balance=Decimal("11000.00"),
            current_balance=Decimal("11000.00"),
        )
        card = CreditCard.objects.create(
            user=self.user,
            account=account,
            credit_limit=Decimal("25000.00"),
            current_debt=Decimal("11000.00"),
            annual_interest_rate=Decimal("18.00"),
            monthly_service_rate=Decimal("1.53"),
            statement_balance=Decimal("11522.30"),
            statement_minimum_payment=Decimal("357.00"),
            global_limit=Decimal("24700.00"),
            global_available=Decimal("8003.25"),
            global_balance=Decimal("16469.67"),
        )
        self.assertEqual(card.available_credit, Decimal("8003.25"))
        self.assertEqual(card.minimum_payment, Decimal("357.00"))
        self.assertEqual(card.utilization_percent, Decimal("66.68"))
        self.assertEqual(card.monthly_interest_amount, Decimal("176.29"))
        self.assertEqual(card.monthly_feci_amount, Decimal("9.60"))

    def test_transaction_category_must_match_transaction_type(self):
        form = TransactionForm(
            data={
                "transaction_type": FinancialTransaction.TransactionType.EXPENSE,
                "description": "Gasto",
                "account": self.checking.id,
                "category": self.income_category.id,
                "amount": "50.00",
                "date": "2026-04-01",
                "status": FinancialTransaction.Status.CLEARED,
            },
            user=self.user,
        )
        self.assertFalse(form.is_valid())
        self.assertIn("category", form.errors)

    def test_recurring_payment_only_accepts_expense_categories(self):
        form = RecurringPaymentForm(
            data={
                "name": "Poliza",
                "account": self.checking.id,
                "category": self.income_category.id,
                "amount": "25.00",
                "frequency": RecurringPayment.Frequency.MONTHLY,
                "next_due_date": "2026-04-01",
                "auto_create_transaction": "on",
                "is_active": "on",
            },
            user=self.user,
        )
        self.assertFalse(form.is_valid())
        self.assertIn("category", form.errors)
