"""Central Import Queue service layer.

Every state transition of a :class:`TransactionDraft` and every financial
mutation that originates from an import goes through this module.  Views and the
MCP layer are thin callers; they never touch ``FinancialTransaction`` or
accounting helpers directly.
"""

from __future__ import annotations

from decimal import Decimal
import datetime as _dt
import json

from django.core.exceptions import ValidationError
from django.db import transaction as db_transaction
from django.utils import timezone

from finanzas.accounting import rebuild_account_balances, sync_transaction_journal
from finanzas.models import Account, Category, FinancialTransaction
from finanzas.intelligence.imports.models import (
    ImportBatch,
    TransactionDraft,
    canonical_amount,
    normalize_external_id,
)


# --------------------------------------------------------------------------- #
# Errors
# --------------------------------------------------------------------------- #
class ImportError(Exception):
    """Base error for the import service."""


class OwnershipError(ImportError):
    """A referenced object does not belong to the acting user."""


class InvalidTransition(ImportError):
    """The requested lifecycle transition is not allowed from the current state."""


class DuplicateDraft(ImportError):
    """A matching draft already exists."""

    def __init__(self, existing):
        self.existing = existing
        super().__init__(f"Draft duplicado de #{existing.pk}")


class ValidationFailed(ImportError):
    """User-supplied data failed validation."""


# --------------------------------------------------------------------------- #
# raw_metadata sanitisation  (untrusted input)
# --------------------------------------------------------------------------- #
RAW_METADATA_MAX_BYTES = 16 * 1024
RAW_METADATA_MAX_DEPTH = 6
RAW_METADATA_MAX_STR = 2000
RAW_METADATA_MAX_KEYS = 100

_SECRET_KEY_HINTS = (
    "authorization", "auth", "password", "passwd", "secret", "api_key", "apikey",
    "api-key", "token", "access_token", "refresh_token", "bearer", "cookie",
    "set-cookie", "session", "client_secret", "private_key", "x-api-key",
)
_REDACTED = "[REDACTED]"


def sanitize_raw_metadata(value):
    """Return a safe JSON-serialisable dict for ``raw_metadata``.

    * must be a mapping (anything else -> ``{}``)
    * keys that look like credentials are redacted
    * strings are truncated, structures are depth/count limited
    * total serialised size is capped (raises :class:`ValidationFailed`)
    """
    if value in (None, ""):
        return {}
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (ValueError, TypeError):
            raise ValidationFailed("raw_metadata debe ser un objeto JSON valido.")
    if not isinstance(value, dict):
        raise ValidationFailed("raw_metadata debe ser un objeto (dict).")

    try:
        raw_size = len(json.dumps(value, default=str).encode("utf-8"))
    except (TypeError, ValueError):
        raise ValidationFailed("raw_metadata no es serializable a JSON.")
    if raw_size > RAW_METADATA_MAX_BYTES:
        raise ValidationFailed(
            f"raw_metadata excede el limite de {RAW_METADATA_MAX_BYTES} bytes."
        )

    def _clean(node, depth):
        if depth > RAW_METADATA_MAX_DEPTH:
            return _REDACTED
        if isinstance(node, dict):
            out = {}
            for i, (k, v) in enumerate(node.items()):
                if i >= RAW_METADATA_MAX_KEYS:
                    break
                key = str(k)
                if any(h in key.lower() for h in _SECRET_KEY_HINTS):
                    out[key] = _REDACTED
                else:
                    out[key] = _clean(v, depth + 1)
            return out
        if isinstance(node, (list, tuple)):
            return [_clean(x, depth + 1) for x in list(node)[:RAW_METADATA_MAX_KEYS]]
        if isinstance(node, str):
            return node[:RAW_METADATA_MAX_STR]
        if isinstance(node, (int, float, bool)) or node is None:
            return node
        return str(node)[:RAW_METADATA_MAX_STR]

    cleaned = _clean(value, 1)
    if len(json.dumps(cleaned, default=str).encode("utf-8")) > RAW_METADATA_MAX_BYTES:
        raise ValidationFailed(
            f"raw_metadata excede el limite de {RAW_METADATA_MAX_BYTES} bytes."
        )
    return cleaned


# --------------------------------------------------------------------------- #
# validation helpers
# --------------------------------------------------------------------------- #
_VALID_CURRENCIES = None


def _known_currencies():
    global _VALID_CURRENCIES
    if _VALID_CURRENCIES is None:
        codes = {"USD", "EUR", "GBP", "PAB", "MXN", "COP", "CAD", "BRL", "ARS",
                 "CLP", "PEN", "JPY", "CHF", "CNY", "AUD"}
        _VALID_CURRENCIES = codes
    return _VALID_CURRENCIES


def validate_currency(value):
    code = (value or "").strip().upper()
    if len(code) != 3 or not code.isalpha():
        raise ValidationFailed(f"Moneda invalida: {value!r}")
    return code


def validate_date(value):
    if isinstance(value, _dt.datetime):
        return value.date()
    if isinstance(value, _dt.date):
        return value
    if isinstance(value, str):
        try:
            return _dt.date.fromisoformat(value.strip())
        except ValueError:
            raise ValidationFailed(f"Fecha invalida: {value!r}")
    raise ValidationFailed(f"Fecha invalida: {value!r}")


def validate_amount(value):
    try:
        amount = canonical_amount(value)
    except ValueError as exc:
        raise ValidationFailed(str(exc)) from exc
    if amount <= 0:
        raise ValidationFailed("El monto debe ser mayor que cero.")
    if amount >= Decimal("10") ** 12:
        raise ValidationFailed("El monto excede el maximo permitido.")
    return amount


def validate_transaction_type(value):
    valid = {c for c, _ in FinancialTransaction.TransactionType.choices}
    if value not in valid:
        raise ValidationFailed(f"Tipo de movimiento invalido: {value!r}")
    return value


def validate_confidence(value):
    try:
        conf = Decimal(str(value if value is not None else "0"))
    except Exception:
        raise ValidationFailed(f"confidence invalido: {value!r}")
    if not conf.is_finite() or conf < 0 or conf > 1:
        raise ValidationFailed("confidence debe estar entre 0 y 1.")
    return conf.quantize(Decimal("0.01"))


def _owned(user, model, pk, label):
    if pk in (None, ""):
        return None
    obj = model.objects.filter(pk=pk).first()
    if obj is None or obj.user_id != user.id:
        raise OwnershipError(f"{label} no encontrada o no pertenece al usuario.")
    return obj


def _resolve_account(user, value, label):
    if value is None:
        return None
    if isinstance(value, Account):
        if value.user_id != user.id:
            raise OwnershipError(f"{label} no pertenece al usuario.")
        return value
    return _owned(user, Account, value, label)


def _resolve_category(user, value, label="Categoria"):
    if value is None:
        return None
    if isinstance(value, Category):
        if value.user_id != user.id:
            raise OwnershipError(f"{label} no pertenece al usuario.")
        return value
    return _owned(user, Category, value, label)


# --------------------------------------------------------------------------- #
# batches
# --------------------------------------------------------------------------- #
@db_transaction.atomic
def create_import_batch(user, *, source, external_batch_id=None, metadata=None):
    source = (source or "").strip()
    if not source:
        raise ValidationFailed("source es obligatorio.")
    ext = normalize_external_id(external_batch_id)
    if ext:
        existing = (
            ImportBatch.objects.select_for_update()
            .filter(user=user, source=source, external_batch_id=ext)
            .first()
        )
        if existing:
            return existing
    return ImportBatch.objects.create(
        user=user,
        source=source,
        external_batch_id=ext or "",
        metadata=sanitize_raw_metadata(metadata),
    )


# --------------------------------------------------------------------------- #
# dedup
# --------------------------------------------------------------------------- #
def find_duplicate(user, *, source, external_id, fingerprint, exclude_pk=None):
    """Return an existing non-rejected draft that matches, or ``None``."""
    ext = normalize_external_id(external_id)
    qs = TransactionDraft.objects.filter(user=user).exclude(
        status=TransactionDraft.Status.REJECTED
    )
    if exclude_pk:
        qs = qs.exclude(pk=exclude_pk)
    if ext:
        hit = qs.filter(source=(source or "").strip(), external_id=ext).first()
        if hit:
            return hit
    if fingerprint:
        hit = qs.filter(fingerprint=fingerprint).first()
        if hit:
            return hit
    return None


# --------------------------------------------------------------------------- #
# draft creation
# --------------------------------------------------------------------------- #
@db_transaction.atomic
def create_transaction_draft(
    user,
    *,
    source,
    description,
    amount,
    currency,
    transaction_date,
    transaction_type,
    account,
    batch=None,
    external_id=None,
    merchant="",
    destination_account=None,
    suggested_category=None,
    confidence=0,
    raw_metadata=None,
    on_duplicate="mark",
):
    """Create a pending :class:`TransactionDraft`.

    ``on_duplicate`` = ``"mark"`` -> store the new draft as ``duplicate`` and
    link it; ``"raise"`` -> raise :class:`DuplicateDraft`; ``"skip"`` -> return
    the existing draft untouched.
    """
    source = (source or "").strip()
    if not source:
        raise ValidationFailed("source es obligatorio.")
    description = (description or "").strip()
    if not description:
        raise ValidationFailed("description es obligatorio.")
    if len(description) > 180:
        raise ValidationFailed("description supera 180 caracteres.")
    merchant = (merchant or "").strip()[:200]

    amount = validate_amount(amount)
    currency = validate_currency(currency)
    transaction_date = validate_date(transaction_date)
    transaction_type = validate_transaction_type(transaction_type)
    confidence = validate_confidence(confidence)
    ext = normalize_external_id(external_id)
    raw_metadata = sanitize_raw_metadata(raw_metadata)

    account = _resolve_account(user, account, "Cuenta")
    if account is None:
        raise ValidationFailed("account es obligatorio.")
    destination_account = _resolve_account(
        user, destination_account, "Cuenta destino"
    )
    suggested_category = _resolve_category(user, suggested_category)

    if batch is not None and not isinstance(batch, ImportBatch):
        batch = _owned(user, ImportBatch, batch, "Lote de importacion")
    if batch is not None and batch.user_id != user.id:
        raise OwnershipError("El lote no pertenece al usuario.")

    draft = TransactionDraft(
        user=user,
        batch=batch,
        source=source,
        external_id=ext or "",
        merchant=merchant,
        description=description,
        amount=amount,
        currency=currency,
        transaction_date=transaction_date,
        transaction_type=transaction_type,
        suggested_category=suggested_category,
        confidence=confidence,
        account=account,
        destination_account=destination_account,
        raw_metadata=raw_metadata,
        status=TransactionDraft.Status.PENDING,
    )
    draft.fingerprint = draft.compute_fingerprint()

    existing = find_duplicate(
        user, source=source, external_id=ext, fingerprint=draft.fingerprint
    )
    if existing is not None:
        if on_duplicate == "raise":
            raise DuplicateDraft(existing)
        if on_duplicate == "skip":
            return existing
        # "mark"
        draft.status = TransactionDraft.Status.DUPLICATE
        draft.duplicate_of = existing
        draft.reviewed_at = timezone.now()
        draft.save()
        if batch is not None:
            batch.recount()
        return draft

    draft.save()
    if batch is not None:
        batch.recount()
    return draft


# --------------------------------------------------------------------------- #
# update
# --------------------------------------------------------------------------- #
_UPDATABLE = {
    "merchant", "description", "amount", "currency", "transaction_date",
    "transaction_type", "confidence", "external_id",
}


@db_transaction.atomic
def update_draft(draft, *, reviewer=None, account=None, destination_account=None,
                 suggested_category=None, **fields):
    draft = (
        # Lock only the draft row (consistent with approve/reject).
        TransactionDraft.objects.select_for_update(of=("self",))
        .select_related("account")
        .get(pk=draft.pk)
    )
    if draft.status != TransactionDraft.Status.PENDING:
        raise InvalidTransition("Solo se pueden editar borradores pendientes.")

    user = draft.user
    if "amount" in fields:
        draft.amount = validate_amount(fields["amount"])
    if "currency" in fields:
        draft.currency = validate_currency(fields["currency"])
    if "transaction_date" in fields:
        draft.transaction_date = validate_date(fields["transaction_date"])
    if "transaction_type" in fields:
        draft.transaction_type = validate_transaction_type(fields["transaction_type"])
    if "confidence" in fields:
        draft.confidence = validate_confidence(fields["confidence"])
    if "merchant" in fields:
        draft.merchant = (fields["merchant"] or "").strip()[:200]
    if "description" in fields:
        desc = (fields["description"] or "").strip()
        if not desc or len(desc) > 180:
            raise ValidationFailed("description invalido.")
        draft.description = desc
    if "external_id" in fields:
        draft.external_id = normalize_external_id(fields["external_id"]) or ""
    if "raw_metadata" in fields:
        draft.raw_metadata = sanitize_raw_metadata(fields["raw_metadata"])

    if account is not None:
        draft.account = _resolve_account(user, account, "Cuenta")
    if destination_account is not None:
        draft.destination_account = _resolve_account(
            user, destination_account, "Cuenta destino"
        )
    if suggested_category is not None:
        draft.suggested_category = _resolve_category(user, suggested_category)

    draft.fingerprint = draft.compute_fingerprint()
    dup = find_duplicate(
        user, source=draft.source, external_id=draft.external_id,
        fingerprint=draft.fingerprint, exclude_pk=draft.pk,
    )
    if dup is not None:
        raise DuplicateDraft(dup)
    draft.save()
    return draft


# --------------------------------------------------------------------------- #
# approval  (the only path that mutates the financial core from an import)
# --------------------------------------------------------------------------- #
@db_transaction.atomic
def approve_draft(draft, *, reviewer, category=None, account=None,
                  destination_account=None, transaction_type=None):
    """Approve a pending draft -> exactly one :class:`FinancialTransaction`.

    Idempotent: a second call on an already-approved draft returns the same
    transaction and performs no further mutation.
    """
    locked = (
        # ``of=("self",)`` locks only the draft row. Without it PostgreSQL
        # rejects ``FOR UPDATE`` because ``select_related`` LEFT-joins the
        # nullable ``destination_account`` / ``suggested_category`` relations.
        TransactionDraft.objects.select_for_update(of=("self",))
        .select_related("account", "destination_account", "suggested_category")
        .get(pk=draft.pk)
    )

    if locked.status == TransactionDraft.Status.APPROVED:
        if locked.transaction_id:
            return locked.transaction
        raise InvalidTransition("Draft aprobado sin transaccion asociada.")
    if locked.status != TransactionDraft.Status.PENDING:
        raise InvalidTransition(
            f"No se puede aprobar un borrador en estado '{locked.status}'."
        )

    user = locked.user
    acc = _resolve_account(user, account, "Cuenta") or locked.account
    dest = (
        _resolve_account(user, destination_account, "Cuenta destino")
        or locked.destination_account
    )
    cat = _resolve_category(user, category) or locked.suggested_category
    ttype = validate_transaction_type(transaction_type or locked.transaction_type)

    if acc is None:
        raise ValidationFailed("Se requiere una cuenta para aprobar.")
    if acc.user_id != user.id:
        raise OwnershipError("La cuenta no pertenece al usuario.")
    if dest is not None and dest.user_id != user.id:
        raise OwnershipError("La cuenta destino no pertenece al usuario.")
    if cat is not None and cat.user_id != user.id:
        raise OwnershipError("La categoria no pertenece al usuario.")

    tx = FinancialTransaction(
        user=user,
        account=acc,
        destination_account=dest if ttype == FinancialTransaction.TransactionType.TRANSFER else None,
        category=cat,
        transaction_type=ttype,
        description=locked.description,
        counterparty=locked.merchant or "",
        amount=locked.amount,
        date=locked.transaction_date,
        status=FinancialTransaction.Status.CLEARED,
        notes=f"Importado desde {locked.source}",
    )
    tx.full_clean(exclude=["journal_entry"])
    tx.save()

    sync_transaction_journal(tx)
    affected = [tx.account_id]
    if tx.destination_account_id:
        affected.append(tx.destination_account_id)
    rebuild_account_balances(user, force_account_ids=affected)

    locked.status = TransactionDraft.Status.APPROVED
    locked.transaction = tx
    locked.reviewed_at = timezone.now()
    locked.reviewed_by = reviewer
    locked.save(update_fields=[
        "status", "transaction", "reviewed_at", "reviewed_by", "updated_at",
    ])
    return tx


@db_transaction.atomic
def reject_draft(draft, *, reviewer, reason=""):
    locked = TransactionDraft.objects.select_for_update().get(pk=draft.pk)
    if locked.status == TransactionDraft.Status.REJECTED:
        return locked
    if locked.status != TransactionDraft.Status.PENDING:
        raise InvalidTransition(
            f"No se puede rechazar un borrador en estado '{locked.status}'."
        )
    locked.status = TransactionDraft.Status.REJECTED
    locked.reviewed_at = timezone.now()
    locked.reviewed_by = reviewer
    if reason:
        meta = dict(locked.raw_metadata or {})
        meta["reject_reason"] = str(reason)[:500]
        locked.raw_metadata = meta
    locked.save(update_fields=[
        "status", "reviewed_at", "reviewed_by", "raw_metadata", "updated_at",
    ])
    return locked


@db_transaction.atomic
def mark_draft_duplicate(draft, existing_draft, *, reviewer=None):
    locked = TransactionDraft.objects.select_for_update().get(pk=draft.pk)
    if locked.status not in {
        TransactionDraft.Status.PENDING, TransactionDraft.Status.DUPLICATE
    }:
        raise InvalidTransition(
            f"No se puede marcar duplicado desde '{locked.status}'."
        )
    if existing_draft.user_id != locked.user_id:
        raise OwnershipError("El draft de referencia no pertenece al usuario.")
    locked.status = TransactionDraft.Status.DUPLICATE
    locked.duplicate_of = existing_draft
    locked.reviewed_at = timezone.now()
    locked.reviewed_by = reviewer
    locked.save(update_fields=[
        "status", "duplicate_of", "reviewed_at", "reviewed_by", "updated_at",
    ])
    return locked


def pending_drafts(user):
    return TransactionDraft.objects.filter(
        user=user, status=TransactionDraft.Status.PENDING
    ).select_related("account", "suggested_category", "batch")
