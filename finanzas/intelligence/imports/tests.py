"""Import Queue test suite (Phase 6)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from finanzas.models import Account, Category, FinancialTransaction
from finanzas.intelligence.imports import services
from finanzas.intelligence.imports.models import (
    ImportBatch,
    TransactionDraft,
    normalize_external_id,
)


def _mkuser(name):
    return get_user_model().objects.create_user(username=name, password="secret12345")


class ImportQueueBase(TestCase):
    def setUp(self):
        self.user = _mkuser("alice")
        self.other = _mkuser("bob")
        self.acc = Account.objects.create(
            user=self.user, name="Banco", account_type=Account.AccountType.CHECKING,
            opening_balance=Decimal("1000.00"), current_balance=Decimal("1000.00"),
        )
        self.acc2 = Account.objects.create(
            user=self.user, name="Ahorro", account_type=Account.AccountType.SAVINGS,
            opening_balance=Decimal("0.00"), current_balance=Decimal("0.00"),
        )
        self.other_acc = Account.objects.create(
            user=self.other, name="BobBanco", account_type=Account.AccountType.CHECKING,
            opening_balance=Decimal("0.00"), current_balance=Decimal("0.00"),
        )
        self.cat = Category.objects.create(
            user=self.user, name="Comida", category_type=Category.CategoryType.EXPENSE,
        )
        self.other_cat = Category.objects.create(
            user=self.other, name="BobCat", category_type=Category.CategoryType.EXPENSE,
        )

    def _draft(self, **kw):
        params = dict(
            source="gmail", description="Cafe", amount="4.50", currency="usd",
            transaction_date="2026-03-01", transaction_type="expense",
            account=self.acc.pk,
        )
        params.update(kw)
        return services.create_transaction_draft(self.user, **params)


# --------------------------------------------------------------------------- #
class CreationTests(ImportQueueBase):
    def test_create_import_batch_idempotent(self):
        b1 = services.create_import_batch(self.user, source="gmail",
                                          external_batch_id="B-1")
        b2 = services.create_import_batch(self.user, source="gmail",
                                          external_batch_id="B-1")
        self.assertEqual(b1.pk, b2.pk)
        self.assertEqual(ImportBatch.objects.filter(user=self.user).count(), 1)

    def test_create_draft_coerces_decimal_currency_date(self):
        d = self._draft(amount="4.5", currency="usd", transaction_date="2026-03-01")
        self.assertEqual(d.amount, Decimal("4.50"))
        self.assertEqual(d.currency, "USD")
        self.assertEqual(d.transaction_date, date(2026, 3, 1))
        self.assertEqual(d.status, TransactionDraft.Status.PENDING)
        self.assertTrue(d.fingerprint)

    def test_create_draft_rejects_bad_amounts(self):
        for bad in ("nan", "inf", "-5", "0", "abc"):
            with self.assertRaises(services.ValidationFailed):
                self._draft(amount=bad, external_id=f"x{bad}")

    def test_create_draft_rejects_bad_currency_and_date(self):
        with self.assertRaises(services.ValidationFailed):
            self._draft(currency="US")
        with self.assertRaises(services.ValidationFailed):
            self._draft(transaction_date="2026-13-40")


# --------------------------------------------------------------------------- #
class OwnershipTests(ImportQueueBase):
    def test_cannot_use_other_users_account(self):
        with self.assertRaises(services.OwnershipError):
            self._draft(account=self.other_acc.pk)

    def test_cannot_use_other_users_category(self):
        with self.assertRaises(services.OwnershipError):
            self._draft(suggested_category=self.other_cat.pk)

    def test_cannot_use_other_users_batch(self):
        bob_batch = services.create_import_batch(self.other, source="gmail")
        with self.assertRaises(services.OwnershipError):
            self._draft(batch=bob_batch.pk)

    def test_other_user_cannot_read_edit_reject_approve_draft_via_ui(self):
        d = self._draft()
        self.client.force_login(self.other)
        # list only shows own drafts
        resp = self.client.get(reverse("imports:import_queue"))
        self.assertNotContains(resp, "Cafe")
        # edit / approve / reject 404 for non-owner
        self.assertEqual(self.client.get(reverse("imports:draft_edit", args=[d.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse("imports:draft_approve", args=[d.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse("imports:draft_reject", args=[d.pk])).status_code, 404)
        d.refresh_from_db()
        self.assertEqual(d.status, TransactionDraft.Status.PENDING)

    def test_approve_rejects_cross_user_override_account(self):
        d = self._draft()
        with self.assertRaises(services.OwnershipError):
            services.approve_draft(d, reviewer=self.user, account=self.other_acc.pk)


# --------------------------------------------------------------------------- #
class ExactDedupTests(ImportQueueBase):
    def test_same_external_id_same_source_is_duplicate(self):
        d1 = self._draft(external_id="TXN-1")
        d2 = self._draft(external_id="TXN-1", description="otra cosa", amount="9.99")
        self.assertEqual(d2.status, TransactionDraft.Status.DUPLICATE)
        self.assertEqual(d2.duplicate_of_id, d1.pk)

    def test_same_external_id_different_source_not_duplicate(self):
        self._draft(external_id="TXN-1", source="gmail")
        d2 = self._draft(external_id="TXN-1", source="csv")
        self.assertEqual(d2.status, TransactionDraft.Status.PENDING)

    def test_on_duplicate_raise_and_skip(self):
        d1 = self._draft(external_id="TXN-2")
        with self.assertRaises(services.DuplicateDraft):
            self._draft(external_id="TXN-2", on_duplicate="raise")
        same = self._draft(external_id="TXN-2", on_duplicate="skip")
        self.assertEqual(same.pk, d1.pk)


# --------------------------------------------------------------------------- #
class FingerprintTests(ImportQueueBase):
    def test_same_normalized_data_is_duplicate(self):
        d1 = self._draft(merchant="  Star Bucks ", description="Cafe Latte")
        d2 = self._draft(merchant="star bucks", description="  cafe   latte ")
        self.assertEqual(d1.fingerprint, d2.fingerprint)
        self.assertEqual(d2.status, TransactionDraft.Status.DUPLICATE)

    def test_different_source_changes_fingerprint(self):
        d1 = self._draft(source="gmail")
        d2 = self._draft(source="csv")
        self.assertNotEqual(d1.fingerprint, d2.fingerprint)
        self.assertEqual(d2.status, TransactionDraft.Status.PENDING)

    def test_different_currency_changes_fingerprint(self):
        d1 = self._draft(currency="usd")
        d2 = self._draft(currency="eur")
        self.assertNotEqual(d1.fingerprint, d2.fingerprint)
        self.assertEqual(d2.status, TransactionDraft.Status.PENDING)

    def test_different_amount_date_type_change_fingerprint(self):
        base = self._draft()
        self.assertNotEqual(base.fingerprint, self._draft(amount="4.51").fingerprint)
        self.assertNotEqual(base.fingerprint, self._draft(transaction_date="2026-03-02").fingerprint)
        self.assertNotEqual(base.fingerprint, self._draft(transaction_type="income").fingerprint)

    def test_100_usd_and_100_eur_never_collide(self):
        usd = self._draft(amount="100.00", currency="usd", merchant="Shop", description="x")
        eur = self._draft(amount="100.00", currency="eur", merchant="Shop", description="x")
        self.assertNotEqual(usd.fingerprint, eur.fingerprint)


# --------------------------------------------------------------------------- #
class ExternalIdTests(ImportQueueBase):
    def test_normalize_helper(self):
        self.assertIsNone(normalize_external_id(None))
        self.assertIsNone(normalize_external_id(""))
        self.assertIsNone(normalize_external_id("   "))
        self.assertEqual(normalize_external_id("  abc123 "), "abc123")

    def test_blank_and_whitespace_do_not_collide(self):
        # distinct fingerprints so only external_id logic is under test
        a = self._draft(external_id=None, merchant="A", description="a1")
        b = self._draft(external_id="", merchant="B", description="b2")
        c = self._draft(external_id="   ", merchant="C", description="c3")
        for d in (a, b, c):
            self.assertEqual(d.status, TransactionDraft.Status.PENDING)
            self.assertEqual(d.external_id, "")

    def test_real_external_id_dedups(self):
        self._draft(external_id="R-1", merchant="A", description="a1")
        dup = self._draft(external_id="R-1", merchant="B", description="b2")
        self.assertEqual(dup.status, TransactionDraft.Status.DUPLICATE)


# --------------------------------------------------------------------------- #
class ApprovalTests(ImportQueueBase):
    def test_pending_to_approved_creates_single_transaction(self):
        d = self._draft(amount="4.50", transaction_type="expense",
                        suggested_category=self.cat.pk)
        tx = services.approve_draft(d, reviewer=self.user)
        d.refresh_from_db()
        self.assertEqual(d.status, TransactionDraft.Status.APPROVED)
        self.assertEqual(d.transaction_id, tx.pk)
        self.assertEqual(d.reviewed_by, self.user)
        self.assertIsNotNone(d.reviewed_at)
        self.assertEqual(FinancialTransaction.objects.filter(user=self.user).count(), 1)
        self.assertEqual(tx.category_id, self.cat.pk)
        self.acc.refresh_from_db()
        self.assertEqual(self.acc.current_balance, Decimal("995.50"))
        self.assertTrue(tx.journal_entry_id)

    def test_transfer_rebuilds_both_accounts(self):
        d = self._draft(transaction_type="transfer", amount="200.00",
                        destination_account=self.acc2.pk)
        services.approve_draft(d, reviewer=self.user)
        self.acc.refresh_from_db()
        self.acc2.refresh_from_db()
        self.assertEqual(self.acc.current_balance, Decimal("800.00"))
        self.assertEqual(self.acc2.current_balance, Decimal("200.00"))

    def test_idempotent_second_approve_no_double_effect(self):
        d = self._draft(amount="4.50")
        tx1 = services.approve_draft(d, reviewer=self.user)
        tx2 = services.approve_draft(d, reviewer=self.user)
        self.assertEqual(tx1.pk, tx2.pk)
        self.assertEqual(FinancialTransaction.objects.count(), 1)
        self.acc.refresh_from_db()
        self.assertEqual(self.acc.current_balance, Decimal("995.50"))

    def test_rollback_leaves_no_partial_state(self):
        d = self._draft(amount="4.50")
        with mock.patch(
            "finanzas.intelligence.imports.services.sync_transaction_journal",
            side_effect=RuntimeError("boom"),
        ):
            with self.assertRaises(RuntimeError):
                services.approve_draft(d, reviewer=self.user)
        d.refresh_from_db()
        self.acc.refresh_from_db()
        self.assertEqual(d.status, TransactionDraft.Status.PENDING)
        self.assertIsNone(d.transaction_id)
        self.assertEqual(FinancialTransaction.objects.count(), 0)
        self.assertEqual(self.acc.current_balance, Decimal("1000.00"))

    def test_approve_via_ui(self):
        d = self._draft(amount="4.50")
        self.client.force_login(self.user)
        resp = self.client.post(reverse("imports:draft_approve", args=[d.pk]))
        self.assertEqual(resp.status_code, 302)
        d.refresh_from_db()
        self.assertEqual(d.status, TransactionDraft.Status.APPROVED)


# --------------------------------------------------------------------------- #
class RejectionDuplicateTransitionTests(ImportQueueBase):
    def test_reject_has_no_financial_effect(self):
        d = self._draft()
        services.reject_draft(d, reviewer=self.user, reason="spam")
        d.refresh_from_db()
        self.assertEqual(d.status, TransactionDraft.Status.REJECTED)
        self.assertEqual(FinancialTransaction.objects.count(), 0)
        self.acc.refresh_from_db()
        self.assertEqual(self.acc.current_balance, Decimal("1000.00"))

    def test_mark_duplicate_has_no_financial_effect(self):
        d1 = self._draft(merchant="A", description="a1")
        d2 = self._draft(merchant="B", description="b2")
        services.mark_draft_duplicate(d2, d1, reviewer=self.user)
        d2.refresh_from_db()
        self.assertEqual(d2.status, TransactionDraft.Status.DUPLICATE)
        self.assertEqual(d2.duplicate_of_id, d1.pk)
        self.assertEqual(FinancialTransaction.objects.count(), 0)

    def test_invalid_transitions(self):
        d = self._draft()
        services.reject_draft(d, reviewer=self.user)
        with self.assertRaises(services.InvalidTransition):
            services.approve_draft(d, reviewer=self.user)
        with self.assertRaises(services.InvalidTransition):
            services.update_draft(d, reviewer=self.user, description="nope")

        d2 = self._draft(merchant="Z", description="z1")
        services.approve_draft(d2, reviewer=self.user)
        with self.assertRaises(services.InvalidTransition):
            services.reject_draft(d2, reviewer=self.user)

    def test_reject_is_idempotent(self):
        d = self._draft()
        services.reject_draft(d, reviewer=self.user)
        again = services.reject_draft(d, reviewer=self.user)
        self.assertEqual(again.status, TransactionDraft.Status.REJECTED)


# --------------------------------------------------------------------------- #
class RawMetadataTests(ImportQueueBase):
    def test_secret_keys_are_redacted(self):
        d = self._draft(raw_metadata={
            "Authorization": "Bearer sk-super-secret",
            "note": "ok", "nested": {"api_key": "abc", "fine": 1},
        })
        self.assertEqual(d.raw_metadata["Authorization"], "[REDACTED]")
        self.assertEqual(d.raw_metadata["nested"]["api_key"], "[REDACTED]")
        self.assertEqual(d.raw_metadata["nested"]["fine"], 1)
        self.assertEqual(d.raw_metadata["note"], "ok")

    def test_oversized_metadata_rejected(self):
        with self.assertRaises(services.ValidationFailed):
            self._draft(raw_metadata={"blob": "x" * 40000})

    def test_non_dict_metadata_rejected(self):
        with self.assertRaises(services.ValidationFailed):
            self._draft(raw_metadata=["not", "a", "dict"])

    def test_long_strings_truncated(self):
        d = self._draft(raw_metadata={"body": "y" * 5000})
        self.assertLessEqual(len(d.raw_metadata["body"]), 2000)
