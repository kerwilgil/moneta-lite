"""Import Queue models for Moneta v0.3.0.

The import flow is:

1. An external source (MCP agent, CSV, email parser, ...) creates an ``ImportBatch``.
2. The batch groups one or more ``TransactionDraft`` rows.
3. Deduplication runs (exact ``external_id`` match + fuzzy ``fingerprint``).
4. A human reviews the pending drafts in the Import Queue UI.
5. On approval the draft becomes a real ``FinancialTransaction`` through the
   central approval service (:mod:`finanzas.intelligence.imports.services`).

All financial mutation lives in the service layer, never on views and never in
the MCP layer.  These models only hold data + cheap deterministic helpers.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
import hashlib

from django.conf import settings
from django.db import models
from django.db.models import Q, UniqueConstraint
from django.utils import timezone

from finanzas.models import Account, Category, FinancialTransaction


AMOUNT_QUANT = Decimal("0.01")


def normalize_external_id(value):
    """Return a real external id or ``None``.

    ``None`` / ``""`` / whitespace-only all collapse to ``None`` so they never
    create artificial uniqueness collisions.
    """
    if value is None:
        return None
    if not isinstance(value, str):
        value = str(value)
    value = value.strip()
    return value or None


def canonical_amount(value):
    """Coerce to a canonical 2-decimal ``Decimal`` or raise ``ValueError``."""
    try:
        dec = value if isinstance(value, Decimal) else Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError(f"Monto invalido: {value!r}") from exc
    if not dec.is_finite():
        raise ValueError("El monto no puede ser NaN o infinito.")
    return dec.quantize(AMOUNT_QUANT)


class ImportBatch(models.Model):
    """A batch of imported transactions from a single source."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pendiente"
        PROCESSING = "processing", "Procesando"
        COMPLETED = "completed", "Completado"
        FAILED = "failed", "Fallido"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="import_batches",
    )
    source = models.CharField(
        max_length=50, help_text="Origin of the import (gmail, csv, chatgpt, ...)"
    )
    external_batch_id = models.CharField(
        max_length=100, blank=True, help_text="External identifier for idempotency"
    )
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING
    )
    item_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    metadata = models.JSONField(
        default=dict, blank=True, help_text="Additional source-specific data"
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "source"]),
            models.Index(fields=["user", "status"]),
        ]
        constraints = [
            UniqueConstraint(
                fields=["user", "source", "external_batch_id"],
                name="unique_import_batch_per_user_source",
                condition=Q(external_batch_id__gt=""),
            ),
        ]

    def __str__(self):
        return f"ImportBatch({self.source}: {self.item_count} items)"

    def recount(self):
        self.item_count = self.drafts.count()
        self.save(update_fields=["item_count", "updated_at"])


class TransactionDraft(models.Model):
    """A proposed financial transaction awaiting human review."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pendiente"
        APPROVED = "approved", "Aprobado"
        REJECTED = "rejected", "Rechazado"
        DUPLICATE = "duplicate", "Duplicado"
        ERROR = "error", "Error"

    TERMINAL_STATUSES = {Status.APPROVED, Status.REJECTED, Status.DUPLICATE}

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="transaction_drafts",
    )
    batch = models.ForeignKey(
        ImportBatch,
        on_delete=models.CASCADE,
        related_name="drafts",
        null=True,
        blank=True,
    )
    source = models.CharField(max_length=50)
    external_id = models.CharField(
        max_length=100,
        blank=True,
        help_text="External identifier for exact deduplication (normalized)",
    )

    # Proposed transaction payload
    merchant = models.CharField(max_length=200, blank=True)
    description = models.CharField(max_length=180)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    currency = models.CharField(max_length=3, default="USD")
    transaction_date = models.DateField(default=timezone.localdate)
    transaction_type = models.CharField(
        max_length=24, choices=FinancialTransaction.TransactionType.choices
    )

    suggested_category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="suggested_drafts",
    )
    confidence = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Confidence score 0.00-1.00 from AI/import",
    )

    account = models.ForeignKey(
        Account,
        on_delete=models.PROTECT,
        related_name="drafts_as_account",
    )
    destination_account = models.ForeignKey(
        Account,
        on_delete=models.PROTECT,
        related_name="drafts_as_destination",
        null=True,
        blank=True,
    )

    # Deduplication
    fingerprint = models.CharField(
        max_length=64, blank=True, help_text="SHA256 fingerprint for fuzzy deduplication"
    )
    duplicate_of = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="duplicates",
    )

    # Lifecycle
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING
    )
    raw_metadata = models.JSONField(
        default=dict, blank=True, help_text="Sanitized raw source data for audit/debug"
    )

    # Result linkage (populated on approval)
    transaction = models.ForeignKey(
        FinancialTransaction,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="source_draft",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_drafts",
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "status"]),
            models.Index(fields=["user", "source"]),
            models.Index(fields=["batch"]),
        ]
        constraints = [
            UniqueConstraint(
                fields=["user", "source", "external_id"],
                name="unique_draft_external_id",
                condition=Q(external_id__gt="") & Q(status="pending"),
            ),
            UniqueConstraint(
                fields=["user", "fingerprint"],
                name="unique_draft_fingerprint",
                condition=Q(fingerprint__gt="") & Q(status="pending"),
            ),
        ]

    def __str__(self):
        return f"Draft({self.description} - {self.amount})"

    # -- deterministic helpers -------------------------------------------------

    def compute_fingerprint(self):
        """Deterministic SHA-256 fuzzy-dedup fingerprint.

        Includes ``user``, ``source``, ``currency`` and a canonical
        ``transaction_type`` sign so that different sources / currencies /
        amounts / dates / directions never collapse together.
        """
        merchant = " ".join((self.merchant or "").split()).lower()
        description = " ".join((self.description or "").split()).lower()
        source = (self.source or "").strip().lower()
        currency = (self.currency or "").strip().upper()
        try:
            amount = canonical_amount(self.amount)
        except ValueError:
            amount = Decimal("0.00")
        sign = "-" if self.transaction_type in {
            FinancialTransaction.TransactionType.EXPENSE,
            FinancialTransaction.TransactionType.CARD_PAYMENT,
        } else "+"
        date_str = self.transaction_date.isoformat() if self.transaction_date else ""
        payload = "|".join([
            "v2",
            str(self.user_id or ""),
            source,
            merchant,
            description,
            f"{sign}{amount}",
            currency,
            date_str,
        ])
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def save(self, *args, **kwargs):
        # Normalize identity/dedup fields on every write.
        self.external_id = normalize_external_id(self.external_id) or ""
        if self.currency:
            self.currency = self.currency.strip().upper()
        if self.source:
            self.source = self.source.strip()
        if self.amount is not None:
            try:
                self.amount = canonical_amount(self.amount)
            except ValueError:
                pass
        if self.status == self.Status.PENDING:
            self.fingerprint = self.compute_fingerprint()
        super().save(*args, **kwargs)

    # -- thin lifecycle wrappers (delegate to the service layer) -------------

    def can_approve(self):
        return self.status == self.Status.PENDING

    def approve(self, user, **overrides):
        from finanzas.intelligence.imports import services

        return services.approve_draft(self, reviewer=user, **overrides)

    def reject(self, user, reason=""):
        from finanzas.intelligence.imports import services

        return services.reject_draft(self, reviewer=user, reason=reason)

    def mark_duplicate(self, existing_draft, reviewer=None):
        from finanzas.intelligence.imports import services

        return services.mark_draft_duplicate(
            self, existing_draft, reviewer=reviewer
        )
