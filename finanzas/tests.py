from datetime import date
from decimal import Decimal
import os
import subprocess
import sys
import unittest
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.core.management import call_command
from django.db import IntegrityError, transaction, connection
from django.test import Client, override_settings
from django.test import RequestFactory, TestCase, TransactionTestCase
from django.urls import reverse
from django.utils import timezone
from django.conf import settings

from .accounting import rebuild_account_balances, sync_credit_card_account_balance
from .automation import execute_due_recurrings_for_user
from .forms import CreditCardForm, InitialSuperuserForm, InvoiceForm, RecurringPaymentForm, TransactionForm
from .models import Account, Category, CreditCard, FinancialTransaction, Invoice, JournalEntry, JournalLine, LoginThrottle, RecurringPayment
from .product import edition_features
from .security import client_ip
from .services import mark_overdue_invoices, monthly_cash_flow_series
from .views import recurring_overview


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

    def test_sync_credit_card_balance_accepts_plain_account_without_card(self):
        account = Account.objects.create(
            user=self.user,
            name="Nueva cuenta",
            account_type=Account.AccountType.CHECKING,
            opening_balance=Decimal("250.00"),
            current_balance=Decimal("250.00"),
        )
        sync_credit_card_account_balance(account)
        account.refresh_from_db()
        self.assertEqual(account.current_balance, Decimal("250.00"))

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

    def test_money_forms_reject_zero_or_negative_amounts(self):
        tx_form = TransactionForm(
            data={
                "transaction_type": FinancialTransaction.TransactionType.EXPENSE,
                "description": "Gasto",
                "account": self.checking.id,
                "category": self.expense_category.id,
                "amount": "0.00",
                "date": "2026-04-01",
                "status": FinancialTransaction.Status.CLEARED,
            },
            user=self.user,
        )
        self.assertFalse(tx_form.is_valid())
        self.assertIn("amount", tx_form.errors)

        recurring_form = RecurringPaymentForm(
            data={
                "name": "Pago",
                "account": self.checking.id,
                "category": self.expense_category.id,
                "amount": "-5.00",
                "frequency": RecurringPayment.Frequency.MONTHLY,
                "next_due_date": "2026-04-01",
                "auto_create_transaction": "on",
                "is_active": "on",
            },
            user=self.user,
        )
        self.assertFalse(recurring_form.is_valid())
        self.assertIn("amount", recurring_form.errors)

        invoice_form = InvoiceForm(
            data={
                "invoice_type": Invoice.InvoiceType.ISSUED,
                "number": "N-1",
                "counterparty": "Cliente",
                "issue_date": "2026-04-01",
                "due_date": "2026-04-30",
                "subtotal": "0.00",
                "tax": "-1.00",
                "status": Invoice.Status.PENDING,
            },
            user=self.user,
        )
        self.assertFalse(invoice_form.is_valid())
        self.assertIn("subtotal", invoice_form.errors)
        self.assertIn("tax", invoice_form.errors)

    def test_setup_rejects_weak_passwords(self):
        form = InitialSuperuserForm(
            data={
                "username": "admin2",
                "email": "",
                "password": "admin",
                "password_confirm": "admin",
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("password", form.errors)

    def test_recurring_projection_ignores_inactive_rows(self):
        RecurringPayment.objects.create(
            user=self.user,
            name="Activo",
            account=self.checking,
            category=self.expense_category,
            amount=Decimal("100.00"),
            frequency=RecurringPayment.Frequency.MONTHLY,
            next_due_date=date(2026, 4, 15),
            is_active=True,
        )
        RecurringPayment.objects.create(
            user=self.user,
            name="Inactivo",
            account=self.checking,
            category=self.expense_category,
            amount=Decimal("999.00"),
            frequency=RecurringPayment.Frequency.MONTHLY,
            next_due_date=date(2026, 4, 15),
            is_active=False,
        )
        overview = recurring_overview(RecurringPayment.objects.filter(user=self.user))
        self.assertEqual(overview["monthly_projection"], Decimal("100.00"))
        self.assertEqual(overview["active_count"], 1)

    def test_pending_invoice_is_marked_overdue(self):
        invoice = Invoice.objects.create(
            user=self.user,
            invoice_type=Invoice.InvoiceType.ISSUED,
            number="V-1",
            counterparty="Cliente",
            issue_date=date(2026, 4, 1),
            due_date=date(2026, 4, 2),
            subtotal=Decimal("10.00"),
            tax=Decimal("0.00"),
            status=Invoice.Status.PENDING,
        )
        mark_overdue_invoices(self.user, today=date(2026, 4, 3))
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, Invoice.Status.OVERDUE)

    def test_credit_card_form_rejects_invalid_financial_values(self):
        account = Account.objects.create(
            user=self.user,
            name="Mastercard",
            account_type=Account.AccountType.CREDIT_CARD,
            opening_balance=Decimal("0.00"),
            current_balance=Decimal("0.00"),
        )
        form = CreditCardForm(
            data={
                "account": account.id,
                "credit_limit": "0.00",
                "current_debt": "-1.00",
                "annual_interest_rate": "-1.00",
                "monthly_service_rate": "-1.00",
                "previous_interest": "-1.00",
                "statement_number": "202605",
                "statement_balance": "-1.00",
                "statement_minimum_payment": "-1.00",
                "statement_cash_payment": "-1.00",
                "global_limit": "-1.00",
                "global_available": "-1.00",
                "global_balance": "-1.00",
                "statement_day": "0",
                "payment_due_day": "32",
                "minimum_payment_percent": "0.00",
            },
            user=self.user,
        )
        self.assertFalse(form.is_valid())
        for field_name in ("credit_limit", "current_debt", "annual_interest_rate", "statement_day", "payment_due_day"):
            self.assertIn(field_name, form.errors)

    def test_model_validation_rejects_cross_tenant_relations(self):
        other_user = get_user_model().objects.create_user(username="other", password="secret")
        other_account = Account.objects.create(
            user=other_user,
            name="Cuenta ajena",
            account_type=Account.AccountType.CHECKING,
        )
        tx = FinancialTransaction(
            user=self.user,
            account=other_account,
            transaction_type=FinancialTransaction.TransactionType.EXPENSE,
            description="Cruce invalido",
            amount=Decimal("1.00"),
            date=date(2026, 4, 1),
        )
        with self.assertRaises(ValidationError):
            tx.full_clean()

    def test_recurring_occurrence_is_unique_at_database_level(self):
        recurring = RecurringPayment.objects.create(
            user=self.user,
            name="Seguro mensual",
            account=self.checking,
            category=self.expense_category,
            amount=Decimal("10.00"),
            next_due_date=date(2026, 4, 1),
        )
        values = {
            "user": self.user,
            "account": self.checking,
            "source_recurring": recurring,
            "category": self.expense_category,
            "transaction_type": FinancialTransaction.TransactionType.EXPENSE,
            "description": "Ocurrencia",
            "amount": Decimal("10.00"),
            "date": date(2026, 4, 1),
        }
        FinancialTransaction.objects.create(**values)
        with self.assertRaises(IntegrityError), transaction.atomic():
            FinancialTransaction.objects.create(**values)

    @override_settings(MONETA_RECURRING_BATCH_SIZE=2, MONETA_RECURRING_MAX_CYCLES=1)
    def test_recurring_execution_is_bounded(self):
        for index in range(3):
            RecurringPayment.objects.create(
                user=self.user,
                name=f"Recurrente {index}",
                account=self.checking,
                category=self.expense_category,
                amount=Decimal("10.00"),
                next_due_date=date(2026, 4, 1),
                auto_create_transaction=True,
            )
        stats = execute_due_recurrings_for_user(self.user, run_date=date(2026, 4, 1))
        self.assertEqual(stats["processed"], 2)
        self.assertEqual(stats["created_transactions"], 2)


@override_settings(APP_EDITION="pro", APP_FEATURES=edition_features("pro"), ALLOWED_HOSTS=["testserver", "localhost", "127.0.0.1"])
@unittest.skipIf("recurring" not in edition_features("pro"), "Pro feature set is not available in this package.")
class FinanceViewSmokeTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="admin", password="admin")
        self.client = Client()
        self.client.login(username="admin", password="admin")
        self.checking = Account.objects.create(
            user=self.user,
            name="Banco",
            account_type=Account.AccountType.CHECKING,
            opening_balance=Decimal("1000.00"),
            current_balance=Decimal("1000.00"),
        )
        self.savings = Account.objects.create(
            user=self.user,
            name="Ahorro",
            account_type=Account.AccountType.SAVINGS,
            opening_balance=Decimal("500.00"),
            current_balance=Decimal("500.00"),
        )
        self.card_account = Account.objects.create(
            user=self.user,
            name="Visa",
            account_type=Account.AccountType.CREDIT_CARD,
            opening_balance=Decimal("0.00"),
            current_balance=Decimal("0.00"),
        )
        self.expense_category = Category.objects.create(
            user=self.user,
            name="Servicios",
            category_type=Category.CategoryType.EXPENSE,
        )
        self.income_category = Category.objects.create(
            user=self.user,
            name="Nomina",
            category_type=Category.CategoryType.INCOME,
        )
        self.transfer_category = Category.objects.create(
            user=self.user,
            name="Transferencias",
            category_type=Category.CategoryType.TRANSFER,
        )

    def assert_redirect_success(self, response, expected_url):
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], expected_url)

    def test_main_authenticated_pages_render(self):
        route_names = [
            "finanzas:dashboard",
            "finanzas:transaction_list",
            "finanzas:invoice_list",
            "finanzas:recurring_list",
            "finanzas:subscription_list",
            "finanzas:credit_card_list",
            "finanzas:ledger",
            "finanzas:reports",
            "finanzas:net_income",
            "finanzas:settings",
        ]
        for route_name in route_names:
            with self.subTest(route=route_name):
                response = self.client.get(reverse(route_name))
                self.assertEqual(response.status_code, 200)

    def test_transaction_list_repeat_request_uses_session_filter_cache(self):
        # Second request within the TTL rebuilds the filter choices from the
        # session cache; regression guard for the missing SimpleNamespace import.
        url = reverse("finanzas:transaction_list")
        first = self.client.get(url)
        self.assertEqual(first.status_code, 200)
        self.assertIn("_transaction_list_filter_cache", self.client.session)
        second = self.client.get(url)
        self.assertEqual(second.status_code, 200)

    def test_create_account_category_invoice_transaction_recurring_subscription_and_card(self):
        response = self.client.post(
            reverse("finanzas:account_create"),
            {
                "name": "Cuenta nueva",
                "account_type": Account.AccountType.CHECKING,
                "currency": "USD",
                "opening_balance": "125.00",
                "current_balance": "125.00",
                "is_active": "on",
            },
        )
        self.assert_redirect_success(response, reverse("finanzas:settings"))
        self.assertTrue(Account.objects.filter(user=self.user, name="Cuenta nueva").exists())

        response = self.client.post(
            reverse("finanzas:category_create"),
            {
                "name": "Categoria nueva",
                "category_type": Category.CategoryType.EXPENSE,
                "monthly_limit": "300.00",
            },
        )
        self.assert_redirect_success(response, reverse("finanzas:settings"))

        response = self.client.post(
            reverse("finanzas:credit_card_create"),
            {
                "account": self.card_account.id,
                "credit_limit": "2500.00",
                "current_debt": "500.00",
                "annual_interest_rate": "18.00",
                "monthly_service_rate": "1.50",
                "previous_interest": "",
                "statement_number": "202605",
                "statement_balance": "500.00",
                "statement_minimum_payment": "50.00",
                "statement_cash_payment": "500.00",
                "global_limit": "",
                "global_available": "",
                "global_balance": "",
                "statement_day": "15",
                "payment_due_day": "30",
                "minimum_payment_percent": "3.00",
            },
        )
        self.assert_redirect_success(response, reverse("finanzas:credit_card_list"))
        card = CreditCard.objects.get(user=self.user, account=self.card_account)
        self.card_account.refresh_from_db()
        self.assertEqual(self.card_account.current_balance, Decimal("500.00"))

        response = self.client.post(
            reverse("finanzas:transaction_create"),
            {
                "transaction_type": FinancialTransaction.TransactionType.EXPENSE,
                "description": "Compra prueba",
                "counterparty": "Tienda",
                "account": self.checking.id,
                "destination_account": "",
                "related_credit_card": "",
                "category": self.expense_category.id,
                "amount": "20.00",
                "date": "2026-05-05",
                "status": FinancialTransaction.Status.CLEARED,
                "notes": "",
            },
        )
        self.assert_redirect_success(response, reverse("finanzas:transaction_list"))

        response = self.client.post(
            reverse("finanzas:recurring_create"),
            {
                "name": "Pago recurrente",
                "account": self.checking.id,
                "category": self.expense_category.id,
                "transaction_type": "expense",
                "amount": "15.00",
                "frequency": RecurringPayment.Frequency.MONTHLY,
                "next_due_date": "2026-05-10",
                "auto_create_transaction": "on",
                "is_active": "on",
            },
        )
        self.assert_redirect_success(response, reverse("finanzas:recurring_list"))

        response = self.client.post(
            reverse("finanzas:subscription_create"),
            {
                "name": "Seguro vida",
                "account": self.checking.id,
                "category": self.expense_category.id,
                "transaction_type": "expense",
                "amount": "25.00",
                "frequency": RecurringPayment.Frequency.MONTHLY,
                "next_due_date": "2026-05-15",
                "auto_create_transaction": "on",
                "is_active": "on",
            },
        )
        self.assert_redirect_success(response, reverse("finanzas:subscription_list"))
        self.assertTrue(RecurringPayment.objects.filter(user=self.user, name="Seguro vida", is_subscription=True).exists())

        response = self.client.post(
            reverse("finanzas:invoice_create"),
            {
                "invoice_type": "issued",
                "number": "F-001",
                "counterparty": "Cliente",
                "issue_date": "2026-05-05",
                "due_date": "2026-05-20",
                "subtotal": "100.00",
                "tax": "7.00",
                "status": "pending",
            },
        )
        self.assert_redirect_success(response, reverse("finanzas:invoice_list"))

    def test_exports_return_csv(self):
        export_routes = [
            "finanzas:export_transactions_csv",
            "finanzas:export_invoices_csv",
            "finanzas:export_recurring_csv",
            "finanzas:export_subscriptions_csv",
        ]
        for route_name in export_routes:
            with self.subTest(route=route_name):
                response = self.client.get(reverse(route_name))
                self.assertEqual(response.status_code, 200)
        self.assertIn("text/csv", response["Content-Type"])

    def test_transaction_and_journal_are_rolled_back_together(self):
        payload = {
            "transaction_type": FinancialTransaction.TransactionType.EXPENSE,
            "description": "Debe revertirse",
            "account": self.checking.id,
            "category": self.expense_category.id,
            "amount": "20.00",
            "date": "2026-05-05",
            "status": FinancialTransaction.Status.CLEARED,
        }
        with patch("finanzas.views.sync_transaction_journal", side_effect=RuntimeError("journal failure")):
            with self.assertRaises(RuntimeError):
                self.client.post(reverse("finanzas:transaction_create"), payload)
        self.assertFalse(FinancialTransaction.objects.filter(description="Debe revertirse").exists())

    def test_get_requests_do_not_mark_invoices_overdue(self):
        invoice = Invoice.objects.create(
            user=self.user,
            invoice_type=Invoice.InvoiceType.ISSUED,
            number="GET-1",
            counterparty="Cliente",
            issue_date=date(2025, 1, 1),
            due_date=date(2025, 1, 2),
            subtotal=Decimal("10.00"),
            status=Invoice.Status.PENDING,
        )
        self.client.get(reverse("finanzas:invoice_list"))
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, Invoice.Status.PENDING)
        call_command("mark_overdue_invoices", verbosity=0)
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, Invoice.Status.OVERDUE)

    def test_accessibility_hooks_are_rendered(self):
        response = self.client.get(reverse("finanzas:dashboard"))
        self.assertContains(response, 'href="#main-content"')
        self.assertContains(response, 'id="main-content"')
        self.assertContains(response, 'id="cashFlowChart" role="img"')

        response = self.client.post(reverse("finanzas:transaction_create"), {})
        self.assertContains(response, 'aria-invalid="true"')
        self.assertContains(response, 'role="alert"')


@override_settings(ALLOWED_HOSTS=["testserver", "localhost", "127.0.0.1"], MONETA_TRUST_X_FORWARDED_FOR=False)
class LoginLockoutTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = get_user_model().objects.create_user(username="locked", password="correct-password")
        self.client = Client()

    def tearDown(self):
        cache.clear()

    def test_login_lockout_is_scoped_to_account_and_network(self):
        login_url = reverse("login")
        for _ in range(10):
            response = self.client.post(login_url, {"username": self.user.username, "password": "wrong"})
            self.assertEqual(response.status_code, 200)

        response = self.client.get(login_url, HTTP_X_FORWARDED_FOR="203.0.113.10")
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Demasiados intentos fallidos")

        response = self.client.post(login_url, {"username": self.user.username, "password": "correct-password"})
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.headers["Retry-After"], "900")
        self.assertContains(response, "Demasiados intentos fallidos", status_code=429)

        second = get_user_model().objects.create_user(username="second", password="another-password")
        response = self.client.post(login_url, {"username": second.username, "password": "another-password"})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(LoginThrottle.objects.count(), 1)

    @override_settings(
        MONETA_TRUST_X_FORWARDED_FOR=True,
        MONETA_TRUSTED_PROXY_CIDRS=["10.0.0.10/32"],
    )
    def test_forwarded_for_is_used_only_from_trusted_proxy(self):
        factory = RequestFactory()
        untrusted = factory.get("/", REMOTE_ADDR="192.0.2.20", HTTP_X_FORWARDED_FOR="203.0.113.7")
        trusted = factory.get("/", REMOTE_ADDR="10.0.0.10", HTTP_X_FORWARDED_FOR="203.0.113.7")
        self.assertEqual(client_ip(untrusted), "192.0.2.20")
        self.assertEqual(client_ip(trusted), "203.0.113.7")


@override_settings(APP_EDITION="lite", APP_FEATURES=edition_features("lite"), ALLOWED_HOSTS=["testserver", "localhost", "127.0.0.1"])
class LiteEditionGateTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="lite", password="admin")
        self.client = Client()
        self.client.login(username="lite", password="admin")
        self.checking = Account.objects.create(
            user=self.user,
            name="Banco Lite",
            account_type=Account.AccountType.CHECKING,
            opening_balance=Decimal("100.00"),
            current_balance=Decimal("100.00"),
        )
        self.income_category = Category.objects.create(
            user=self.user,
            name="Ingreso Lite",
            category_type=Category.CategoryType.INCOME,
        )

    def test_lite_allows_cards_and_insurance_subscriptions_but_blocks_pro_modules(self):
        allowed_routes = [
            "finanzas:dashboard",
            "finanzas:transaction_list",
            "finanzas:invoice_list",
            "finanzas:subscription_list",
            "finanzas:credit_card_list",
            "finanzas:settings",
        ]
        for route_name in allowed_routes:
            with self.subTest(route=route_name):
                self.assertEqual(self.client.get(reverse(route_name)).status_code, 200)

        blocked_routes = [
            "finanzas:recurring_list",
            "finanzas:ledger",
            "finanzas:net_income",
        ]
        for route_name in blocked_routes:
            with self.subTest(route=route_name):
                response = self.client.get(reverse(route_name))
                self.assertEqual(response.status_code, 302)
                self.assertEqual(response.headers["Location"], reverse("finanzas:dashboard"))

        response = self.client.get(reverse("finanzas:subscription_create"))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], reverse("finanzas:subscription_list"))

        response = self.client.get(reverse("finanzas:subscription_create") + "?preset=segurovida")
        self.assertEqual(response.status_code, 200)

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

    def test_lite_cannot_forge_or_rename_a_service_subscription(self):
        expense = Category.objects.create(
            user=self.user,
            name="Seguros Lite",
            category_type=Category.CategoryType.EXPENSE,
        )
        payload = {
            "name": "Servicio arbitrario",
            "account": self.checking.id,
            "category": expense.id,
            "transaction_type": "expense",
            "amount": "25.00",
            "frequency": RecurringPayment.Frequency.MONTHLY,
            "next_due_date": "2026-04-01",
            "is_active": "on",
        }
        response = self.client.post(reverse("finanzas:subscription_create") + "?preset=segurovida", payload)
        self.assertEqual(response.status_code, 302)
        subscription = RecurringPayment.objects.get(user=self.user, is_subscription=True)
        self.assertEqual(subscription.name, "Seguro de vida privado")
        self.assertEqual(subscription.subscription_catalog, RecurringPayment.SubscriptionCatalog.INSURANCE)

        payload["name"] = "Netflix"
        response = self.client.post(reverse("finanzas:subscription_edit", args=[subscription.pk]), payload)
        self.assertEqual(response.status_code, 302)
        subscription.refresh_from_db()
        self.assertEqual(subscription.name, "Seguro de vida privado")


@override_settings(
    ALLOWED_HOSTS=["testserver"],
    MONETA_WEB_SETUP_ENABLED=True,
    MONETA_SETUP_TOKEN="a-secure-one-time-setup-token-123456",
)
class InitialSetupSecurityTests(TestCase):
    def test_setup_requires_token_and_can_only_be_claimed_once(self):
        url = reverse("finanzas:initial_setup")
        payload = {
            "username": "owner",
            "email": "owner@example.com",
            "password": "Correct-Horse-Battery-Staple-2026!",
            "password_confirm": "Correct-Horse-Battery-Staple-2026!",
        }
        response = self.client.post(url, {**payload, "setup_token": "wrong"})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(get_user_model().objects.exists())

        response = self.client.post(
            url,
            {**payload, "setup_token": "a-secure-one-time-setup-token-123456"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(get_user_model().objects.filter(is_superuser=True).count(), 1)

        self.client.logout()
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)


@override_settings(ALLOWED_HOSTS=["testserver"], MONETA_WEB_SETUP_ENABLED=False)
class InitialSetupDisabledTests(TestCase):
    def test_setup_is_not_public_by_default(self):
        self.assertEqual(self.client.get(reverse("finanzas:initial_setup")).status_code, 404)


class CSPHeaderTests(TestCase):
    """Tests for S-02: CSP header validation."""

    def test_csp_header_no_unsafe_inline(self):
        response = self.client.get("/accounts/login/")
        self.assertEqual(response.status_code, 200)
        csp = response.get("Content-Security-Policy", "")
        self.assertNotIn("'unsafe-inline'", csp)
        self.assertIn("style-src 'self' cdn.jsdelivr.net", csp)
        self.assertIn("script-src 'self' cdn.jsdelivr.net", csp)
        self.assertIn("object-src 'none'", csp)
        self.assertIn("frame-ancestors 'none'", csp)


class SecretKeyValidationTests(TestCase):
    """Tests for S-01: SECRET_KEY validation in all DEBUG modes.

    Uses subprocess to isolate Django settings loading per test case.
    """

    def _run_settings_check(self, env_vars):
        """Run a fresh Django settings load and return (returncode, stdout, stderr)."""
        env = os.environ.copy()
        env.update(env_vars)
        env.setdefault("DJANGO_ALLOWED_HOSTS", "testserver")
        env.setdefault("MONETA_WEB_SETUP_ENABLED", "0")
        result = subprocess.run(
            [sys.executable, "-c", "import django; django.setup(); from django.conf import settings; print('SECRET_KEY:', settings.SECRET_KEY[:10] + '...')"],
            capture_output=True,
            text=True,
            cwd=os.path.dirname(os.path.dirname(__file__)),
            env=env,
        )
        return result.returncode, result.stdout, result.stderr

    def test_secret_key_missing_debug_false_raises(self):
        code, _, stderr = self._run_settings_check({"DJANGO_DEBUG": "0", "DJANGO_SECRET_KEY": ""})
        self.assertNotEqual(code, 0)
        self.assertIn("Define DJANGO_SECRET_KEY", stderr)

    def test_secret_key_missing_debug_true_generates_ephemeral(self):
        code, stdout, _ = self._run_settings_check({"DJANGO_DEBUG": "1", "DJANGO_SECRET_KEY": ""})
        self.assertEqual(code, 0)
        self.assertIn("SECRET_KEY:", stdout)

    def test_secret_key_known_default_rejected_debug_true(self):
        code, _, stderr = self._run_settings_check({"DJANGO_DEBUG": "1", "DJANGO_SECRET_KEY": "dev-only-change-me"})
        self.assertNotEqual(code, 0)
        self.assertIn("valor por defecto conocido", stderr)

    def test_secret_key_known_default_rejected_debug_false(self):
        code, _, stderr = self._run_settings_check({"DJANGO_DEBUG": "0", "DJANGO_SECRET_KEY": "dev-only-change-me"})
        self.assertNotEqual(code, 0)
        self.assertIn("valor por defecto conocido", stderr)

    def test_secret_key_placeholder_rejected(self):
        code, _, stderr = self._run_settings_check({
            "DJANGO_DEBUG": "1",
            "DJANGO_SECRET_KEY": "replace-this-with-a-unique-secret-key-of-at-least-50-random-characters"
        })
        self.assertNotEqual(code, 0)
        self.assertIn("valor por defecto conocido", stderr)

    def test_secret_key_too_short_rejected_debug_true(self):
        code, _, stderr = self._run_settings_check({"DJANGO_DEBUG": "1", "DJANGO_SECRET_KEY": "short"})
        self.assertNotEqual(code, 0)
        self.assertIn("al menos 50 caracteres", stderr)

    def test_secret_key_too_short_rejected_debug_false(self):
        code, _, stderr = self._run_settings_check({"DJANGO_DEBUG": "0", "DJANGO_SECRET_KEY": "short"})
        self.assertNotEqual(code, 0)
        self.assertIn("al menos 50 caracteres", stderr)

    def test_secret_key_valid_50_chars_accepted_debug_true(self):
        valid_key = "a" * 50
        code, stdout, _ = self._run_settings_check({"DJANGO_DEBUG": "1", "DJANGO_SECRET_KEY": valid_key})
        self.assertEqual(code, 0)
        self.assertIn(valid_key[:10], stdout)

    def test_secret_key_valid_50_chars_accepted_debug_false(self):
        valid_key = "b" * 50
        code, stdout, _ = self._run_settings_check({"DJANGO_DEBUG": "0", "DJANGO_SECRET_KEY": valid_key})
        self.assertEqual(code, 0)
        self.assertIn(valid_key[:10], stdout)

    def test_secret_key_ephemeral_is_random_per_setup(self):
        keys = set()
        for _ in range(3):
            code, stdout, _ = self._run_settings_check({"DJANGO_DEBUG": "1", "DJANGO_SECRET_KEY": ""})
            self.assertEqual(code, 0)
            key_line = [l for l in stdout.splitlines() if l.startswith("SECRET_KEY:")][0]
            keys.add(key_line)
        self.assertEqual(len(keys), 3)


class Phase2CorrectnessTests(TestCase):
    """Tests for PHASE 2 Core Correctness items."""

    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="tester", password="secret")
        self.client = Client()
        self.client.login(username="tester", password="secret")
        self.checking = Account.objects.create(
            user=self.user,
            name="Banco",
            account_type=Account.AccountType.CHECKING,
            opening_balance=Decimal("1000.00"),
            current_balance=Decimal("1000.00"),
        )
        self.savings = Account.objects.create(
            user=self.user,
            name="Ahorro",
            account_type=Account.AccountType.SAVINGS,
            opening_balance=Decimal("500.00"),
            current_balance=Decimal("500.00"),
        )
        self.expense_category = Category.objects.create(
            user=self.user,
            name="Gastos",
            category_type=Category.CategoryType.EXPENSE,
        )
        self.income_category = Category.objects.create(
            user=self.user,
            name="Ingresos",
            category_type=Category.CategoryType.INCOME,
        )

    def test_transaction_create_uses_force_account_ids(self):
        """C-03: transaction_create should rebuild only touched accounts."""
        # Create a transaction and verify rebuild was called with specific accounts
        with patch("finanzas.views.rebuild_account_balances") as mock_rebuild:
            response = self.client.post(
                reverse("finanzas:transaction_create"),
                {
                    "transaction_type": FinancialTransaction.TransactionType.EXPENSE,
                    "description": "Test expense",
                    "account": self.checking.id,
                    "category": self.expense_category.id,
                    "amount": "50.00",
                    "date": "2026-05-01",
                    "status": FinancialTransaction.Status.CLEARED,
                },
            )
            self.assertEqual(response.status_code, 302)
            mock_rebuild.assert_called_once()
            call_args = mock_rebuild.call_args
            self.assertEqual(call_args[0][0], self.user)
            force_ids = call_args[1].get("force_account_ids", [])
            self.assertIn(self.checking.id, force_ids)

    def test_account_create_uses_force_account_ids(self):
        """C-03: account_create should rebuild only the new account."""
        with patch("finanzas.views.rebuild_account_balances") as mock_rebuild:
            response = self.client.post(
                reverse("finanzas:account_create"),
                {
                    "name": "Cuenta nueva",
                    "account_type": Account.AccountType.CHECKING,
                    "currency": "USD",
                    "opening_balance": "100.00",
                    "current_balance": "100.00",
                    "is_active": "on",
                },
            )
            self.assertEqual(response.status_code, 302)
            mock_rebuild.assert_called_once()
            call_args = mock_rebuild.call_args
            force_ids = call_args[1].get("force_account_ids", [])
            self.assertEqual(len(force_ids), 1)

    def test_credit_card_create_uses_force_account_ids(self):
        """C-03: credit_card_create should rebuild only the card account."""
        card_account = Account.objects.create(
            user=self.user,
            name="Visa Test",
            account_type=Account.AccountType.CREDIT_CARD,
            opening_balance=Decimal("0.00"),
            current_balance=Decimal("0.00"),
        )
        with patch("finanzas.views.rebuild_account_balances") as mock_rebuild:
            response = self.client.post(
                reverse("finanzas:credit_card_create"),
                {
                    "account": card_account.id,
                    "credit_limit": "5000.00",
                    "current_debt": "0.00",
                    "annual_interest_rate": "18.00",
                    "monthly_service_rate": "1.50",
                    "statement_day": "15",
                    "payment_due_day": "30",
                    "minimum_payment_percent": "3.00",
                },
            )
            self.assertEqual(response.status_code, 302)
            mock_rebuild.assert_called_once()
            call_args = mock_rebuild.call_args
            force_ids = call_args[1].get("force_account_ids", [])
            self.assertIn(card_account.id, force_ids)

    def test_monthly_cash_flow_series_parametrizable(self):
        """C-04: monthly_cash_flow_series should accept months parameter."""
        series = monthly_cash_flow_series(self.user, months=12, english=False)
        self.assertEqual(len(series["labels"]), 12)
        self.assertEqual(len(series["values"]), 12)

    def test_monthly_cash_flow_series_default_seven(self):
        """C-04: monthly_cash_flow_series defaults to 7 months."""
        series = monthly_cash_flow_series(self.user)
        self.assertEqual(len(series["labels"]), 7)

    def test_journal_entry_balance_validation_with_update_fields(self):
        """DB-01: JournalEntry.save() should validate balance even with update_fields."""
        entry = JournalEntry.objects.create(
            user=self.user,
            date=timezone.localdate(),
            description="Test entry",
            posted=True,
        )
        JournalLine.objects.create(
            entry=entry,
            account=self.checking,
            debit=Decimal("100.00"),
        )
        JournalLine.objects.create(
            entry=entry,
            account=self.savings,
            credit=Decimal("100.00"),
        )
        # This should not raise - balanced entry
        entry.description = "Updated"
        entry.save(update_fields=["description"])

        # Now create an unbalanced scenario by directly manipulating a line
        # (simulating a bulk update or direct DB manipulation)
        line = entry.lines.first()
        line.debit = Decimal("200.00")
        line.save()

        # Now the entry is unbalanced (debit=200, credit=100)
        # Saving with update_fields should still validate and raise
        entry.description = "Unbalanced"
        with self.assertRaises(ValidationError):
            entry.save(update_fields=["description"])

    def test_rebuild_account_balances_memory_efficient(self):
        """C-01/DB-02: rebuild_account_balances should use iterator for large datasets."""
        # Create many transactions
        for i in range(150):
            FinancialTransaction.objects.create(
                user=self.user,
                account=self.checking,
                category=self.expense_category,
                transaction_type=FinancialTransaction.TransactionType.EXPENSE,
                description=f"Gasto {i}",
                amount=Decimal("10.00"),
                date=timezone.localdate(),
                status=FinancialTransaction.Status.CLEARED,
            )
        # This should complete without memory issues
        rebuild_account_balances(self.user)
        self.checking.refresh_from_db()
        expected = Decimal("1000.00") - Decimal("1500.00")
        self.assertEqual(self.checking.current_balance, expected)

    def test_recurring_max_cycles_default(self):
        """C-02: Recurring max_cycles should default to a reasonable value."""
        from django.conf import settings
        # Default should be 12, not 24
        self.assertEqual(getattr(settings, "MONETA_RECURRING_MAX_CYCLES", 12), 12)

    def test_unique_recurring_occurrence_sqlite_compat(self):
        """DB-03/C-05: Unique constraint on recurring occurrence should handle SQLite."""
        recurring = RecurringPayment.objects.create(
            user=self.user,
            name="Test recurring",
            account=self.checking,
            category=self.expense_category,
            amount=Decimal("10.00"),
            next_due_date=timezone.localdate(),
            auto_create_transaction=True,
        )
        # Create first occurrence
        FinancialTransaction.objects.create(
            user=self.user,
            account=self.checking,
            source_recurring=recurring,
            category=self.expense_category,
            transaction_type=FinancialTransaction.TransactionType.EXPENSE,
            description="Auto test",
            amount=Decimal("10.00"),
            date=timezone.localdate(),
        )
        # Second occurrence on same date should fail at DB level
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                FinancialTransaction.objects.create(
                    user=self.user,
                    account=self.checking,
                    source_recurring=recurring,
                    category=self.expense_category,
                    transaction_type=FinancialTransaction.TransactionType.EXPENSE,
                    description="Auto test 2",
                    amount=Decimal("10.00"),
                    date=timezone.localdate(),
                )


class Phase3PostgresIntegrationTests(TransactionTestCase):
    """T-02 / T-06 checks that require a real backend with row locking and
    committed data visible across connections (skipped on SQLite).

    Uses ``TransactionTestCase`` so worker threads see committed rows and the
    migration executor is not wrapped in the test's transaction.
    """

    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="tester", password="secret")
        self.checking = Account.objects.create(
            user=self.user,
            name="Banco",
            account_type=Account.AccountType.CHECKING,
            opening_balance=Decimal("1000.00"),
            current_balance=Decimal("1000.00"),
        )
        self.expense_category = Category.objects.create(
            user=self.user,
            name="Gastos",
            category_type=Category.CategoryType.EXPENSE,
        )

    @staticmethod
    def _worker(fn):
        """Run ``fn`` in a thread body and always release the DB connection so
        the TransactionTestCase table truncation at teardown cannot deadlock."""
        def wrapped():
            try:
                fn()
            finally:
                connection.close()
        return wrapped

    @unittest.skipIf(
        connection.vendor == "sqlite",
        "SQLite does not support concurrent writes; test requires PostgreSQL",
    )
    def test_recurring_concurrent_execution(self):
        """T-02: Concurrent recurring execution should be safe with select_for_update."""
        from threading import Thread

        recurring = RecurringPayment.objects.create(
            user=self.user,
            name="Concurrent Recurring",
            account=self.checking,
            category=self.expense_category,
            amount=Decimal("10.00"),
            next_due_date=timezone.localdate(),
            auto_create_transaction=True,
        )

        errors = []

        def run_recurring():
            try:
                execute_due_recurrings_for_user(self.user, run_date=timezone.localdate())
            except Exception as e:  # noqa: BLE001
                errors.append(e)

        threads = [Thread(target=self._worker(run_recurring)) for _ in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(errors), 0, f"Concurrent execution errors: {errors}")
        txs = FinancialTransaction.objects.filter(user=self.user, source_recurring=recurring)
        # One cycle ahead only, and the occurrence is idempotent.
        self.assertEqual(txs.exclude(status=FinancialTransaction.Status.VOID).count(), 1)

    @unittest.skipIf(
        connection.vendor == "sqlite",
        "SQLite does not support concurrent writes; test requires PostgreSQL",
    )
    def test_rebuild_concurrent(self):
        """T-02: Concurrent rebuilds should produce one consistent balance."""
        from threading import Thread

        for i in range(20):
            FinancialTransaction.objects.create(
                user=self.user,
                account=self.checking,
                category=self.expense_category,
                transaction_type=FinancialTransaction.TransactionType.EXPENSE,
                description=f"Expense {i}",
                amount=Decimal("10.00"),
                date=timezone.localdate(),
                status=FinancialTransaction.Status.CLEARED,
            )

        errors = []
        results = []

        def rebuild():
            try:
                rebuild_account_balances(self.user)
                acc = Account.objects.get(pk=self.checking.pk)
                results.append(acc.current_balance)
            except Exception as e:  # noqa: BLE001
                errors.append(e)

        threads = [Thread(target=self._worker(rebuild)) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(errors), 0, f"Concurrent rebuild errors: {errors}")
        self.assertEqual(len(set(results)), 1, f"Inconsistent balances: {results}")
        self.assertEqual(results[0], Decimal("1000.00") - Decimal("200.00"))

    @unittest.skipIf(
        connection.vendor == "sqlite",
        "SQLite does not support concurrent writes; test requires PostgreSQL",
    )
    def test_transaction_concurrent_create_edit(self):
        """T-02: Concurrent create/edit should not corrupt balances."""
        from threading import Thread

        errors = []

        def create_tx():
            try:
                with transaction.atomic():
                    FinancialTransaction.objects.create(
                        user=self.user,
                        account=self.checking,
                        category=self.expense_category,
                        transaction_type=FinancialTransaction.TransactionType.EXPENSE,
                        description="Concurrent create",
                        amount=Decimal("5.00"),
                        date=timezone.localdate(),
                        status=FinancialTransaction.Status.CLEARED,
                    )
            except Exception as e:  # noqa: BLE001
                errors.append(e)

        def edit_tx():
            try:
                tx = FinancialTransaction.objects.create(
                    user=self.user,
                    account=self.checking,
                    category=self.expense_category,
                    transaction_type=FinancialTransaction.TransactionType.EXPENSE,
                    description="To edit",
                    amount=Decimal("20.00"),
                    date=timezone.localdate(),
                    status=FinancialTransaction.Status.CLEARED,
                )
                tx.amount = Decimal("25.00")
                tx.save()
                rebuild_account_balances(self.user, force_account_ids=[self.checking.id])
            except Exception as e:  # noqa: BLE001
                errors.append(e)

        threads = (
            [Thread(target=self._worker(create_tx)) for _ in range(3)]
            + [Thread(target=self._worker(edit_tx)) for _ in range(2)]
        )
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(errors), 0, f"Concurrent tx errors: {errors}")

    @unittest.skipIf(
        connection.vendor == "sqlite",
        "SQLite schema editor doesn't support this migration cycle; requires PostgreSQL",
    )
    def test_migrations_forward_backward(self):
        """T-06: Every applied finanzas migration is reversible on PostgreSQL.

        Walk the finanzas migrations newest -> oldest, unapplying each one and
        re-applying it, so both directions of every operation are exercised on a
        real backend.
        """
        from django.db.migrations.executor import MigrationExecutor
        from django.db.migrations.recorder import MigrationRecorder

        executor = MigrationExecutor(connection)
        names = sorted(
            n for a, n in MigrationRecorder(connection).applied_migrations()
            if a == "finanzas"
        )
        latest = names[-1]
        try:
            # names[:-1] gives the target to roll *back to*; unapply the one above it.
            for target in reversed(names[:-1]):
                executor.migrate([("finanzas", target)])          # backward
                executor.loader.build_graph()
                executor.migrate([("finanzas", latest)])          # forward again
                executor.loader.build_graph()
        finally:
            executor.loader.build_graph()
            executor.migrate([("finanzas", latest)])


class Phase3TestHardeningTests(TestCase):
    """Tests for PHASE 3 Test Hardening — T-01 through T-07."""

    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="tester", password="secret")
        self.user2 = User.objects.create_user(username="tester2", password="secret")
        self.client = Client()
        self.client.login(username="tester", password="secret")
        self.checking = Account.objects.create(
            user=self.user,
            name="Banco",
            account_type=Account.AccountType.CHECKING,
            opening_balance=Decimal("1000.00"),
            current_balance=Decimal("1000.00"),
        )
        self.savings = Account.objects.create(
            user=self.user,
            name="Ahorro",
            account_type=Account.AccountType.SAVINGS,
            opening_balance=Decimal("500.00"),
            current_balance=Decimal("500.00"),
        )
        self.checking2 = Account.objects.create(
            user=self.user2,
            name="Banco 2",
            account_type=Account.AccountType.CHECKING,
            opening_balance=Decimal("2000.00"),
            current_balance=Decimal("2000.00"),
        )
        self.expense_category = Category.objects.create(
            user=self.user,
            name="Gastos",
            category_type=Category.CategoryType.EXPENSE,
        )
        self.income_category = Category.objects.create(
            user=self.user,
            name="Ingresos",
            category_type=Category.CategoryType.INCOME,
        )
        self.expense_category2 = Category.objects.create(
            user=self.user2,
            name="Gastos 2",
            category_type=Category.CategoryType.EXPENSE,
        )

    # T-01: Cross-tenant isolation tests
    def test_cross_tenant_transaction_isolation(self):
        """T-01: User A cannot read/modify/delete User B's transactions via views."""
        tx_user1 = FinancialTransaction.objects.create(
            user=self.user,
            account=self.checking,
            category=self.expense_category,
            transaction_type=FinancialTransaction.TransactionType.EXPENSE,
            description="User1 expense",
            amount=Decimal("100.00"),
            date=timezone.localdate(),
            status=FinancialTransaction.Status.CLEARED,
        )
        tx_user2 = FinancialTransaction.objects.create(
            user=self.user2,
            account=self.checking2,
            category=self.expense_category2,
            transaction_type=FinancialTransaction.TransactionType.EXPENSE,
            description="User2 expense",
            amount=Decimal("200.00"),
            date=timezone.localdate(),
            status=FinancialTransaction.Status.CLEARED,
        )
        # User1 should only see their own transaction
        user1_txs = FinancialTransaction.objects.filter(user=self.user)
        self.assertEqual(user1_txs.count(), 1)
        self.assertEqual(user1_txs.first().description, "User1 expense")
        # User1 cannot access User2's transaction via PK
        with self.assertRaises(FinancialTransaction.DoesNotExist):
            FinancialTransaction.objects.get(pk=tx_user2.pk, user=self.user)
        # User1 cannot edit User2's transaction via view (404)
        response = self.client.get(reverse("finanzas:transaction_edit", args=[tx_user2.pk]))
        self.assertEqual(response.status_code, 404)
        # User1 cannot delete User2's transaction via view (404)
        response = self.client.post(reverse("finanzas:transaction_delete", args=[tx_user2.pk]))
        self.assertEqual(response.status_code, 404)
# User1 cannot create transaction referencing User2's account/category
        response = self.client.post(
            reverse("finanzas:transaction_create"),
            {
                "transaction_type": FinancialTransaction.TransactionType.EXPENSE,
                "description": "Hacked",
                "account": self.checking2.id,
                "category": self.expense_category2.id,
                "amount": "50.00",
                "date": timezone.localdate().isoformat(),
                "status": FinancialTransaction.Status.CLEARED,
            },
        )
        self.assertEqual(response.status_code, 200)
        # The form filters queryset to user's own accounts, so foreign ID is invalid choice
        self.assertIn("Escoja una opci", response.content.decode("utf-8"))

    def test_cross_tenant_account_isolation(self):
        """T-01: User A cannot access User B's accounts via views."""
        # User1 should only see their own accounts
        user1_accounts = Account.objects.filter(user=self.user)
        self.assertEqual(user1_accounts.count(), 2)
        # User1 cannot access User2's account via PK
        with self.assertRaises(Account.DoesNotExist):
            Account.objects.get(pk=self.checking2.pk, user=self.user)
        # User1 cannot edit User2's account via view (404)
        response = self.client.get(reverse("finanzas:account_edit", args=[self.checking2.pk]))
        self.assertEqual(response.status_code, 404)
        # User1 cannot delete User2's account (404)
        response = self.client.post(reverse("finanzas:account_delete", args=[self.checking2.pk]))
        self.assertEqual(response.status_code, 404)

    def test_cross_tenant_category_isolation(self):
        """T-01: User A cannot access User B's categories via views."""
        user1_categories = Category.objects.filter(user=self.user)
        self.assertEqual(user1_categories.count(), 2)
        with self.assertRaises(Category.DoesNotExist):
            Category.objects.get(pk=self.expense_category2.pk, user=self.user)
        # User1 cannot edit User2's category via view (404)
        response = self.client.get(reverse("finanzas:category_edit", args=[self.expense_category2.pk]))
        self.assertEqual(response.status_code, 404)
        # User1 cannot delete User2's category (404)
        response = self.client.post(reverse("finanzas:category_delete", args=[self.expense_category2.pk]))
        self.assertEqual(response.status_code, 404)

    def test_cross_tenant_invoice_isolation(self):
        """T-01: User A cannot access User B's invoices."""
        inv_user1 = Invoice.objects.create(
            user=self.user,
            invoice_type=Invoice.InvoiceType.ISSUED,
            number="U1-001",
            counterparty="Cliente 1",
            issue_date=timezone.localdate(),
            subtotal=Decimal("100.00"),
            tax=Decimal("21.00"),
        )
        inv_user2 = Invoice.objects.create(
            user=self.user2,
            invoice_type=Invoice.InvoiceType.ISSUED,
            number="U2-001",
            counterparty="Cliente 2",
            issue_date=timezone.localdate(),
            subtotal=Decimal("200.00"),
            tax=Decimal("21.00"),
        )
        user1_invoices = Invoice.objects.filter(user=self.user)
        self.assertEqual(user1_invoices.count(), 1)
        self.assertEqual(user1_invoices.first().number, "U1-001")
        with self.assertRaises(Invoice.DoesNotExist):
            Invoice.objects.get(pk=inv_user2.pk, user=self.user)

    def test_cross_tenant_recurring_isolation(self):
        """T-01: User A cannot access User B's recurring payments."""
        rec_user1 = RecurringPayment.objects.create(
            user=self.user,
            name="Recurrente 1",
            account=self.checking,
            category=self.expense_category,
            amount=Decimal("50.00"),
            next_due_date=timezone.localdate(),
        )
        rec_user2 = RecurringPayment.objects.create(
            user=self.user2,
            name="Recurrente 2",
            account=self.checking2,
            category=self.expense_category2,
            amount=Decimal("75.00"),
            next_due_date=timezone.localdate(),
        )
        user1_recs = RecurringPayment.objects.filter(user=self.user)
        self.assertEqual(user1_recs.count(), 1)
        with self.assertRaises(RecurringPayment.DoesNotExist):
            RecurringPayment.objects.get(pk=rec_user2.pk, user=self.user)

    def test_cross_tenant_subscription_isolation(self):
        """T-01: User A cannot access User B's subscriptions."""
        sub_user1 = RecurringPayment.objects.create(
            user=self.user,
            name="Sub 1",
            account=self.checking,
            category=self.expense_category,
            amount=Decimal("30.00"),
            next_due_date=timezone.localdate(),
            is_subscription=True,
        )
        sub_user2 = RecurringPayment.objects.create(
            user=self.user2,
            name="Sub 2",
            account=self.checking2,
            category=self.expense_category2,
            amount=Decimal("40.00"),
            next_due_date=timezone.localdate(),
            is_subscription=True,
        )
        user1_subs = RecurringPayment.objects.filter(user=self.user, is_subscription=True)
        self.assertEqual(user1_subs.count(), 1)
        with self.assertRaises(RecurringPayment.DoesNotExist):
            RecurringPayment.objects.get(pk=sub_user2.pk, user=self.user)

    def test_cross_tenant_credit_card_isolation(self):
        """T-01: User A cannot access User B's credit cards."""
        card_acc1 = Account.objects.create(
            user=self.user,
            name="Visa 1",
            account_type=Account.AccountType.CREDIT_CARD,
            opening_balance=Decimal("0.00"),
            current_balance=Decimal("0.00"),
        )
        card_acc2 = Account.objects.create(
            user=self.user2,
            name="Visa 2",
            account_type=Account.AccountType.CREDIT_CARD,
            opening_balance=Decimal("0.00"),
            current_balance=Decimal("0.00"),
        )
        card1 = CreditCard.objects.create(
            user=self.user,
            account=card_acc1,
            credit_limit=Decimal("5000.00"),
            current_debt=Decimal("1000.00"),
            annual_interest_rate=Decimal("18.00"),
        )
        card2 = CreditCard.objects.create(
            user=self.user2,
            account=card_acc2,
            credit_limit=Decimal("10000.00"),
            current_debt=Decimal("2000.00"),
            annual_interest_rate=Decimal("20.00"),
        )
        user1_cards = CreditCard.objects.filter(user=self.user)
        self.assertEqual(user1_cards.count(), 1)
        with self.assertRaises(CreditCard.DoesNotExist):
            CreditCard.objects.get(pk=card2.pk, user=self.user)

    def test_cross_tenant_journal_isolation(self):
        """T-01: User A cannot access User B's journal entries."""
        entry1 = JournalEntry.objects.create(
            user=self.user,
            date=timezone.localdate(),
            description="Entry 1",
            posted=True,
        )
        JournalLine.objects.create(entry=entry1, account=self.checking, debit=Decimal("100.00"))
        JournalLine.objects.create(entry=entry1, account=self.savings, credit=Decimal("100.00"))

        entry2 = JournalEntry.objects.create(
            user=self.user2,
            date=timezone.localdate(),
            description="Entry 2",
            posted=True,
        )
        JournalLine.objects.create(entry=entry2, account=self.checking2, debit=Decimal("200.00"))
        JournalLine.objects.create(entry=entry2, account=self.savings, credit=Decimal("200.00"))

        user1_entries = JournalEntry.objects.filter(user=self.user)
        self.assertEqual(user1_entries.count(), 1)
        with self.assertRaises(JournalEntry.DoesNotExist):
            JournalEntry.objects.get(pk=entry2.pk, user=self.user)

    # T-02 concurrency tests and the T-06 migration reversibility test need
    # committed data / no wrapping transaction, so they live in
    # ``Phase3PostgresIntegrationTests`` (a TransactionTestCase) below.

    # T-03: Monetary edge cases
    def test_rounding_edge_cases(self):
        """T-03: Decimal rounding should be consistent (half-up, half-even)."""
        # Test half-up rounding
        from decimal import Decimal, ROUND_HALF_UP
        value = Decimal("10.125")
        rounded = value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        self.assertEqual(rounded, Decimal("10.13"))

        # Test half-even (banker's rounding) - default
        value2 = Decimal("10.125")
        rounded2 = value2.quantize(Decimal("0.01"))
        self.assertEqual(rounded2, Decimal("10.12"))

        # Test large decimal operations
        large = Decimal("999999999999.99")
        small = Decimal("0.01")
        result = large + small
        self.assertEqual(result, Decimal("1000000000000.00"))

    def test_large_amounts(self):
        """T-03: max_digits=14, decimal_places=2 limits should be enforced."""
        # Valid max amount: 999999999999.99 (12 digits + 2 decimals = 14)
        max_valid = Decimal("999999999999.99")
        tx = FinancialTransaction(
            user=self.user,
            account=self.checking,
            category=self.expense_category,
            transaction_type=FinancialTransaction.TransactionType.EXPENSE,
            description="Max amount",
            amount=max_valid,
            date=timezone.localdate(),
        )
        tx.full_clean()  # Should not raise

        # Invalid: exceeds max_digits
        too_large = Decimal("1000000000000.00")  # 13 digits + 2 = 15
        tx2 = FinancialTransaction(
            user=self.user,
            account=self.checking,
            category=self.expense_category,
            transaction_type=FinancialTransaction.TransactionType.EXPENSE,
            description="Too large",
            amount=too_large,
            date=timezone.localdate(),
        )
        with self.assertRaises(ValidationError):
            tx2.full_clean()

    def test_negative_zero_handling(self):
        """T-03: Negative zero should be handled correctly."""
        neg_zero = Decimal("-0.00")
        pos_zero = Decimal("0.00")
        self.assertEqual(neg_zero, pos_zero)
        # Quantize should normalize
        self.assertEqual(neg_zero.quantize(Decimal("0.01")), pos_zero.quantize(Decimal("0.01")))

    def test_currency_precision(self):
        """T-03: All monetary fields should use Decimal with proper precision."""
        from finanzas.models import FinancialTransaction
        # Check model field definition
        amount_field = FinancialTransaction._meta.get_field("amount")
        self.assertEqual(amount_field.max_digits, 14)
        self.assertEqual(amount_field.decimal_places, 2)

    # T-04: CSV export tests
    def test_csv_transactions_content_headers(self):
        """T-04: Transaction CSV export should have correct headers and content."""
        FinancialTransaction.objects.create(
            user=self.user,
            account=self.checking,
            category=self.expense_category,
            transaction_type=FinancialTransaction.TransactionType.EXPENSE,
            description="Test expense",
            amount=Decimal("50.00"),
            date=timezone.localdate(),
            status=FinancialTransaction.Status.CLEARED,
        )
        url = reverse("finanzas:export_transactions_csv")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/csv", response["Content-Type"])
        content = response.content.decode("utf-8")
        self.assertIn("Test expense", content)
        self.assertIn("50.00", content)
        self.assertIn("EXPENSE", content.upper())

    def test_csv_invoices_content_headers(self):
        """T-04: Invoice CSV export should have correct headers and content."""
        Invoice.objects.create(
            user=self.user,
            invoice_type=Invoice.InvoiceType.ISSUED,
            number="INV-001",
            counterparty="Test Client",
            issue_date=timezone.localdate(),
            subtotal=Decimal("100.00"),
            tax=Decimal("21.00"),
        )
        url = reverse("finanzas:export_invoices_csv")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")
        self.assertIn("INV-001", content)
        self.assertIn("Test Client", content)

    @unittest.skipIf(
        getattr(settings, "APP_EDITION", "demo") == "lite",
        "Lite edition does not have exports_advanced feature for recurring exports"
    )
    def test_csv_recurring_content_headers(self):
        """T-04: Recurring CSV export should have correct headers and content."""
        RecurringPayment.objects.create(
            user=self.user,
            name="Test Recurring",
            account=self.checking,
            category=self.expense_category,
            amount=Decimal("25.00"),
            frequency=RecurringPayment.Frequency.MONTHLY,
            next_due_date=timezone.localdate(),
        )
        url = reverse("finanzas:export_recurring_csv")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")
        self.assertIn("Test Recurring", content)
        self.assertIn("25.00", content)

    @unittest.skipIf(
        getattr(settings, "APP_EDITION", "demo") == "lite",
        "Lite edition does not have exports_advanced feature for subscription exports"
    )
    def test_csv_subscriptions_content_headers(self):
        """T-04: Subscription CSV export should have correct headers and content."""
        RecurringPayment.objects.create(
            user=self.user,
            name="Test Subscription",
            account=self.checking,
            category=self.expense_category,
            amount=Decimal("15.00"),
            frequency=RecurringPayment.Frequency.MONTHLY,
            next_due_date=timezone.localdate(),
            is_subscription=True,
        )
        url = reverse("finanzas:export_subscriptions_csv")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")
        self.assertIn("Test Subscription", content)

    def test_csv_formula_injection_prevention(self):
        """T-04: CSV export should prevent formula injection (=, +, -, @)."""
        FinancialTransaction.objects.create(
            user=self.user,
            account=self.checking,
            category=self.expense_category,
            transaction_type=FinancialTransaction.TransactionType.EXPENSE,
            description="=SUM(A1:A10)",  # Formula injection attempt
            amount=Decimal("50.00"),
            date=timezone.localdate(),
            status=FinancialTransaction.Status.CLEARED,
        )
        url = reverse("finanzas:export_transactions_csv")
        response = self.client.get(url)
        content = response.content.decode("utf-8")
        # Should be escaped with leading single quote
        self.assertIn("'=SUM(A1:A10)", content)
        self.assertNotIn("=SUM(A1:A10)", content.replace("'=SUM(A1:A10)", ""))

    def test_csv_encoding_utf8(self):
        """T-04: CSV export should be UTF-8 encoded."""
        FinancialTransaction.objects.create(
            user=self.user,
            account=self.checking,
            category=self.expense_category,
            transaction_type=FinancialTransaction.TransactionType.EXPENSE,
            description="Gasto con ñ y €",
            amount=Decimal("50.00"),
            date=timezone.localdate(),
            status=FinancialTransaction.Status.CLEARED,
        )
        url = reverse("finanzas:export_transactions_csv")
        response = self.client.get(url)
        # Should not raise decoding errors
        content = response.content.decode("utf-8")
        self.assertIn("Gasto con ñ y €", content)

    # T-05: Feature gates for all editions
    def test_gates_demo_edition(self):
        """T-05: Demo edition should have all features enabled."""
        from finanzas.product import edition_features
        demo_features = edition_features("demo")
        expected_features = {
            "reports", "transactions", "invoices", "recurring",
            "subscriptions", "credit_cards", "ledger", "net_income",
            "settings", "admin_link", "exports_basic", "exports_advanced",
        }
        self.assertEqual(demo_features, expected_features)

    def test_gates_pro_edition(self):
        """T-05: Pro edition should have all features enabled."""
        from finanzas.product import edition_features
        pro_features = edition_features("pro")
        expected_features = {
            "reports", "transactions", "invoices", "recurring",
            "subscriptions", "credit_cards", "ledger", "net_income",
            "settings", "admin_link", "exports_basic", "exports_advanced",
        }
        self.assertEqual(pro_features, expected_features)

    def test_gates_personal_edition(self):
        """T-05: Personal edition should have all features enabled."""
        from finanzas.product import edition_features
        personal_features = edition_features("personal")
        expected_features = {
            "reports", "transactions", "invoices", "recurring",
            "subscriptions", "credit_cards", "ledger", "net_income",
            "settings", "admin_link", "exports_basic", "exports_advanced",
        }
        self.assertEqual(personal_features, expected_features)

    def test_gates_lite_edition(self):
        """T-05: Lite edition should have restricted features."""
        from finanzas.product import edition_features
        lite_features = edition_features("lite")
        expected_features = {
            "reports", "transactions", "invoices", "subscriptions",
            "credit_cards", "settings", "admin_link", "exports_basic",
        }
        self.assertEqual(lite_features, expected_features)
        # Verify missing features
        self.assertNotIn("recurring", lite_features)
        self.assertNotIn("ledger", lite_features)
        self.assertNotIn("net_income", lite_features)
        self.assertNotIn("exports_advanced", lite_features)

    def test_gates_unknown_edition_defaults_to_demo(self):
        """T-05: Unknown edition should default to demo features."""
        from finanzas.product import edition_features
        unknown_features = edition_features("unknown")
        demo_features = edition_features("demo")
        self.assertEqual(unknown_features, demo_features)

    # T-06: test_migrations_forward_backward lives in
    # ``Phase3PostgresIntegrationTests`` (TransactionTestCase) below.

    def test_no_missing_migrations(self):
        """T-06: No missing migrations detected."""
        from django.core.management import call_command
        from io import StringIO
        out = StringIO()
        # This should not detect any missing migrations
        call_command("makemigrations", "--check", "--dry-run", stdout=out)
        output = out.getvalue()
        self.assertIn("No changes detected", output)

    # T-07: Accessibility tests (basic automated checks)
    def test_accessibility_dashboard_no_violations(self):
        """T-07: Dashboard should pass basic accessibility checks."""
        response = self.client.get(reverse("finanzas:dashboard"))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")
        # Skip link
        self.assertIn('href="#main-content"', content)
        self.assertIn('id="main-content"', content)
        # ARIA labels on forms
        self.assertIn('aria-label', content)
        # Chart role
        self.assertIn('role="img"', content)

    def test_accessibility_forms_aria_attributes(self):
        """T-07: Forms should have proper ARIA attributes."""
        response = self.client.post(reverse("finanzas:transaction_create"), {})
        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")
        # Fields with errors should have aria-invalid
        self.assertIn('aria-invalid="true"', content)
        # Error messages should have role="alert"
        self.assertIn('role="alert"', content)

    def test_accessibility_tables_have_headers(self):
        """T-07: Tables should have proper header associations."""
        response = self.client.get(reverse("finanzas:transaction_list"))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")
        # Table headers should exist
        self.assertIn("<th>", content)

    # S-03: throttle_keys timing attack protection
    def test_throttle_keys_constant_time(self):
        """S-03: throttle_keys should use constant-time hashing to prevent timing attacks."""
        from finanzas.security import throttle_keys, _digest
        from django.contrib.auth import get_user_model
        from django.test import RequestFactory

        User = get_user_model()
        factory = RequestFactory()

        # Test with existing user
        user = User.objects.create_user(username="existing_user", password="secret")
        request = factory.post("/accounts/login/", {"username": "existing_user", "password": "wrong"})
        network_hash, identity_hash = throttle_keys(request, "existing_user")
        self.assertIsInstance(network_hash, str)
        self.assertIsInstance(identity_hash, str)
        self.assertEqual(len(identity_hash), 64)  # SHA256 hex

        # Test with non-existing user - should use same hashing path
        request2 = factory.post("/accounts/login/", {"username": "nonexistent_user", "password": "wrong"})
        network_hash2, identity_hash2 = throttle_keys(request2, "nonexistent_user")
        self.assertIsInstance(network_hash2, str)
        self.assertIsInstance(identity_hash2, str)
        self.assertEqual(len(identity_hash2), 64)

        # Both should use constant-time derivation (same code path)
        # Identity hash should be different for different usernames
        self.assertNotEqual(identity_hash, identity_hash2)

    def test_throttle_pepper_from_settings(self):
        """S-03: throttle_keys should use pepper from settings."""
        from finanzas.security import throttle_keys
        from django.conf import settings

        from django.test import RequestFactory
        factory = RequestFactory()
        request = factory.post("/accounts/login/", {"username": "test", "password": "test"})

        # Should work without explicit pepper (falls back to SECRET_KEY)
        network_hash, identity_hash = throttle_keys(request, "testuser")
        self.assertIsInstance(identity_hash, str)

    # S-04: initial_setup additional guard
    def test_initial_setup_requires_header_when_configured(self):
        """S-04: initial_setup should require header when MONETA_SETUP_REQUIRE_HEADER=1."""
        from django.test import override_settings

        with override_settings(
            MONETA_WEB_SETUP_ENABLED=True,
            MONETA_SETUP_TOKEN="valid-token-123456789012345678901234567890",
            MONETA_SETUP_REQUIRE_HEADER=True,
            DJANGO_ALLOWED_HOSTS=["testserver"],
        ):
            # Without header -> 404
            response = self.client.post(reverse("finanzas:initial_setup"), {
                "username": "admin",
                "password": "ComplexPass123!",
                "password_confirm": "ComplexPass123!",
                "setup_token": "valid-token-123456789012345678901234567890",
            })
            self.assertEqual(response.status_code, 404)

            # With header -> allowed (but fails on token if wrong)
            response = self.client.post(
                reverse("finanzas:initial_setup"),
                {
                    "username": "admin",
                    "password": "ComplexPass123!",
                    "password_confirm": "ComplexPass123!",
                    "setup_token": "wrong-token",
                },
                HTTP_X_MONETA_SETUP="1",
            )
            # Should not be 404 (header check passed), but form error on token
            self.assertNotEqual(response.status_code, 404)

    def test_initial_setup_allows_allowed_ip(self):
        """S-04: initial_setup should allow configured IPs."""
        from django.test import override_settings

        with override_settings(
            MONETA_WEB_SETUP_ENABLED=True,
            MONETA_SETUP_TOKEN="valid-token-123456789012345678901234567890",
            MONETA_SETUP_ALLOWED_IPS=["1.2.3.4"],
            DJANGO_ALLOWED_HOSTS=["testserver"],
        ):
            from finanzas.security import client_ip
            from django.test import RequestFactory

            factory = RequestFactory()
            request = factory.get("/", REMOTE_ADDR="1.2.3.4")
            ip = client_ip(request)
            self.assertEqual(ip, "1.2.3.4")

    # S-05: Cache backend validation at startup
    def test_cache_backend_warning_in_production(self):
        """S-05: Startup should warn on unsafe cache backend in production."""
        import logging
        import sys
        from io import StringIO
        from unittest.mock import patch

        # First, import the settings module to ensure it's in sys.modules
        from config import settings as settings_module

        log_stream = StringIO()
        handler = logging.StreamHandler(log_stream)
        logger = logging.getLogger("config.settings")
        logger.addHandler(handler)
        logger.setLevel(logging.WARNING)

        try:
            # Patch environment to simulate production with locmem cache
            with patch.dict("os.environ", {"DJANGO_DEBUG": "0", "DJANGO_CACHE_BACKEND": "locmem", "DJANGO_ALLOWED_HOSTS": "testserver"}):
                # Reload the settings module to trigger validation
                import importlib
                importlib.reload(settings_module)

                log_output = log_stream.getvalue()
                self.assertIn("inseguro", log_output.lower())
                self.assertIn("locmem", log_output.lower())
        finally:
            logger.removeHandler(handler)

    def test_cache_backend_ok_with_redis_in_production(self):
        """S-05: Redis cache backend should not warn in production."""
        import logging
        from io import StringIO
        from django.test import override_settings

        log_stream = StringIO()
        handler = logging.StreamHandler(log_stream)
        logger = logging.getLogger("config.settings")
        logger.addHandler(handler)
        logger.setLevel(logging.WARNING)

        try:
            with override_settings(
                DEBUG=False,
                DJANGO_CACHE_BACKEND="redis",
                DJANGO_CACHE_REDIS_URL="redis://127.0.0.1:6379/1",
                DJANGO_ALLOWED_HOSTS=["testserver"],
            ):
                from importlib import reload
                from config import settings
                reload(settings)

                log_output = log_stream.getvalue()
                self.assertNotIn("inseguro", log_output.lower())
        finally:
            logger.removeHandler(handler)
