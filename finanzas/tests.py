from datetime import date
from decimal import Decimal
import unittest
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.test import Client, override_settings
from django.test import RequestFactory, TestCase
from django.urls import reverse

from .accounting import rebuild_account_balances, sync_credit_card_account_balance
from .automation import execute_due_recurrings_for_user
from .forms import CreditCardForm, InitialSuperuserForm, InvoiceForm, RecurringPaymentForm, TransactionForm
from .models import Account, Category, CreditCard, FinancialTransaction, Invoice, LoginThrottle, RecurringPayment
from .product import edition_features
from .security import client_ip
from .services import mark_overdue_invoices
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
