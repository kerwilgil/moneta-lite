"""Admin permissions must preserve the same tenant boundary as the UI."""
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse
from django.contrib import admin
from django.test import RequestFactory
from decimal import Decimal
from unittest.mock import patch
from finanzas.models import Account, Invoice, FinancialTransaction, JournalEntry


class StaffIsolationTests(TestCase):
    def setUp(self):
        self.staff = get_user_model().objects.create_user("staff", is_staff=True)
        self.other = get_user_model().objects.create_user("owner")
        self.staff.user_permissions.set(Permission.objects.filter(content_type__app_label="finanzas"))
        self.own = Account.objects.create(user=self.staff, name="Own bank", account_type="checking")
        self.foreign = Account.objects.create(user=self.other, name="Private bank", account_type="checking")
        self.invoice = Invoice.objects.create(user=self.other, number="PRIVATE-INVOICE",
                                              counterparty="Private customer", invoice_type="issued",
                                              issue_date="2026-01-01", due_date="2026-01-02",
                                              subtotal="10", tax="0")
        self.client.force_login(self.staff)

    def test_staff_cannot_list_other_users_accounts_or_invoices(self):
        self.assertNotContains(self.client.get(reverse("admin:finanzas_account_changelist")), "Private bank")
        self.assertNotContains(self.client.get(reverse("admin:finanzas_invoice_changelist")), "PRIVATE-INVOICE")

    def test_staff_cannot_open_or_delete_other_users_object(self):
        for action in ("change", "delete", "history"):
            response = self.client.get(reverse(f"admin:finanzas_account_{action}", args=[self.foreign.pk]))
            self.assertNotEqual(response.status_code, 200)

    def test_staff_foreign_keys_and_owner_are_scoped(self):
        response = self.client.get(reverse("admin:finanzas_financialtransaction_add"))
        form = response.context["adminform"].form
        self.assertNotIn("user", form.fields)
        self.assertEqual(list(form.fields["account"].queryset), [self.own])

    def test_forged_owner_and_foreign_account_cannot_be_posted(self):
        response = self.client.post(reverse("admin:finanzas_financialtransaction_add"), {
            "user": self.other.pk, "account": self.foreign.pk,
            "transaction_type": "expense", "description": "Forged", "amount": "10",
            "date": "2026-01-01", "status": "cleared", "_save": "Save",
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn("account", response.context["adminform"].form.errors)
        self.assertFalse(FinancialTransaction.objects.exists())

    def test_admin_save_edit_and_bulk_delete_keep_core_consistent(self):
        request = RequestFactory().post("/admin/")
        request.user = self.staff
        model_admin = admin.site._registry[FinancialTransaction]
        tx = FinancialTransaction(account=self.own, transaction_type="expense",
                                  description="Synthetic expense", amount=Decimal("10"),
                                  status="cleared")
        model_admin.save_model(request, tx, None, False)
        self.own.refresh_from_db()
        self.assertEqual(tx.user_id, self.staff.pk)
        self.assertEqual(self.own.current_balance, Decimal("-10"))
        self.assertTrue(tx.journal_entry.is_balanced)
        tx.amount = Decimal("20")
        model_admin.save_model(request, tx, None, True)
        self.own.refresh_from_db()
        self.assertEqual(self.own.current_balance, Decimal("-20"))
        model_admin.delete_queryset(request, model_admin.get_queryset(request))
        self.own.refresh_from_db()
        self.assertEqual(self.own.current_balance, Decimal("0"))
        self.assertFalse(FinancialTransaction.objects.exists())
        self.assertFalse(JournalEntry.objects.exists())

    def test_admin_financial_failure_rolls_back(self):
        request = RequestFactory().post("/admin/")
        request.user = self.staff
        tx = FinancialTransaction(account=self.own, transaction_type="expense",
                                  description="Synthetic failure", amount=Decimal("10"),
                                  status="cleared")
        with patch("finanzas.admin.rebuild_account_balances", side_effect=TimeoutError):
            with self.assertRaises(TimeoutError):
                admin.site._registry[FinancialTransaction].save_model(request, tx, None, False)
        self.assertFalse(FinancialTransaction.objects.exists())
        self.assertFalse(JournalEntry.objects.exists())

    def test_transaction_forms_get_does_not_create_system_accounts(self):
        tx = FinancialTransaction.objects.create(user=self.staff, account=self.own,
                                                transaction_type="expense", description="Draft",
                                                amount="1", status="pending")
        before = Account.objects.count()
        for name, args in (("transaction_create", []), ("transaction_edit", [tx.pk])):
            self.assertEqual(self.client.get(reverse(f"finanzas:{name}", args=args)).status_code, 200)
        self.assertEqual(Account.objects.count(), before)
