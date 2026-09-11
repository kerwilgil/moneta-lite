"""Moneta MCP tool registry, validation, tenant-safe dispatch and audit.

Design rules enforced here:

* The acting user is **always** ``token.user``.  No tool argument named
  ``user`` / ``user_id`` / ``owner`` / ``tenant`` is ever honoured.
* ``read`` tools need the ``read`` scope; ``draft`` tools need ``draft``.
* Every list/search tool is bounded (default 50, max 200).
* Every execution (success, failure, denied) writes an :class:`MCPAuditEvent`.
* No tool can approve, delete, mutate balances or confirm payments.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
import time

from django.utils import timezone

from finanzas.models import (
    Account,
    Category,
    CreditCard,
    FinancialTransaction,
    RecurringPayment,
)
from finanzas.services import dashboard_summary
from finanzas.intelligence.imports import services as import_services
from finanzas.intelligence.imports.models import ImportBatch, TransactionDraft
from finanzas.intelligence.mcp.models import (
    MCPAuditEvent,
    SCOPE_DRAFT,
    SCOPE_READ,
)
from finanzas.intelligence.mcp import ratelimit


DEFAULT_PAGE = 50
MAX_PAGE = 200


# --------------------------------------------------------------------------- #
# errors
# --------------------------------------------------------------------------- #
class MCPToolError(Exception):
    code = "tool_error"


class ToolNotFound(MCPToolError):
    code = "tool_not_found"


class ScopeDenied(MCPToolError):
    code = "scope_denied"


class InputInvalid(MCPToolError):
    code = "input_invalid"


class RateLimited(MCPToolError):
    code = "rate_limited"


# Names an MCP client must never find in list_tools (security gate).
FORBIDDEN_TOOL_NAMES = {
    "moneta.approve_draft", "moneta.approve", "approve_draft", "approve",
    "moneta.create_transaction_direct", "create_transaction_direct",
    "moneta.delete_transaction", "delete_transaction",
    "moneta.delete_account", "delete_account",
    "moneta.edit_balance", "edit_balance", "moneta.set_balance",
    "moneta.confirm_payment", "confirm_payment", "moneta.pay",
}


# --------------------------------------------------------------------------- #
# lightweight argument validation
# --------------------------------------------------------------------------- #
def _validate(schema, arguments):
    if arguments is None:
        arguments = {}
    if not isinstance(arguments, dict):
        raise InputInvalid("arguments debe ser un objeto.")
    props = schema.get("properties", {})
    required = schema.get("required", [])
    if not schema.get("additionalProperties", False):
        extra = set(arguments) - set(props)
        if extra:
            raise InputInvalid(f"Campos no permitidos: {sorted(extra)}")
    for field in required:
        if field not in arguments or arguments[field] is None:
            raise InputInvalid(f"Falta el campo obligatorio '{field}'.")
    out = {}
    for key, value in arguments.items():
        if value is None:
            continue
        spec = props.get(key, {})
        out[key] = _coerce(key, value, spec)
    return out


def _coerce(key, value, spec):
    typ = spec.get("type")
    if typ == "integer":
        try:
            value = int(value)
        except (TypeError, ValueError):
            raise InputInvalid(f"'{key}' debe ser entero.")
        if "minimum" in spec and value < spec["minimum"]:
            raise InputInvalid(f"'{key}' minimo {spec['minimum']}.")
        if "maximum" in spec and value > spec["maximum"]:
            raise InputInvalid(f"'{key}' maximo {spec['maximum']}.")
    elif typ == "number":
        try:
            dec = Decimal(str(value))
        except (InvalidOperation, TypeError, ValueError):
            raise InputInvalid(f"'{key}' debe ser numerico.")
        if not dec.is_finite():
            raise InputInvalid(f"'{key}' no puede ser NaN/Infinity.")
        if "minimum" in spec and dec < Decimal(str(spec["minimum"])):
            raise InputInvalid(f"'{key}' minimo {spec['minimum']}.")
        if "maximum" in spec and dec > Decimal(str(spec["maximum"])):
            raise InputInvalid(f"'{key}' maximo {spec['maximum']}.")
        value = dec
    elif typ == "string":
        if not isinstance(value, str):
            raise InputInvalid(f"'{key}' debe ser texto.")
        if "minLength" in spec and len(value) < spec["minLength"]:
            raise InputInvalid(f"'{key}' demasiado corto.")
        if "maxLength" in spec and len(value) > spec["maxLength"]:
            raise InputInvalid(f"'{key}' supera {spec['maxLength']} caracteres.")
        if "pattern" in spec:
            import re
            if not re.fullmatch(spec["pattern"], value):
                raise InputInvalid(f"'{key}' con formato invalido.")
    elif typ == "boolean":
        if not isinstance(value, bool):
            raise InputInvalid(f"'{key}' debe ser booleano.")
    elif typ == "object":
        if not isinstance(value, dict):
            raise InputInvalid(f"'{key}' debe ser un objeto.")
    if "enum" in spec and value not in spec["enum"]:
        raise InputInvalid(f"'{key}' fuera de los valores permitidos.")
    return value


def _page_args(arguments):
    limit = int(arguments.get("limit", DEFAULT_PAGE) or DEFAULT_PAGE)
    offset = int(arguments.get("offset", 0) or 0)
    if limit < 1:
        raise InputInvalid("limit debe ser >= 1.")
    if limit > MAX_PAGE:
        limit = MAX_PAGE
    if offset < 0:
        raise InputInvalid("offset debe ser >= 0.")
    return limit, offset


# --------------------------------------------------------------------------- #
# serializers
# --------------------------------------------------------------------------- #
def _money(value):
    return str(Decimal(value).quantize(Decimal("0.01"))) if value is not None else None


def _account(a):
    return {
        "id": a.id, "name": a.name, "type": a.account_type,
        "type_display": a.get_account_type_display(), "currency": a.currency,
        "current_balance": _money(a.current_balance),
        "opening_balance": _money(a.opening_balance),
        "is_active": a.is_active,
    }


def _transaction(t):
    return {
        "id": t.id, "description": t.description, "counterparty": t.counterparty,
        "amount": _money(t.amount), "date": t.date.isoformat(),
        "transaction_type": t.transaction_type,
        "transaction_type_display": t.get_transaction_type_display(),
        "status": t.status,
        "account": {"id": t.account_id, "name": t.account.name},
        "destination_account": (
            {"id": t.destination_account_id, "name": t.destination_account.name}
            if t.destination_account_id else None
        ),
        "category": (
            {"id": t.category_id, "name": t.category.name} if t.category_id else None
        ),
    }


def _recurring(r):
    return {
        "id": r.id, "name": r.name, "amount": _money(r.amount),
        "frequency": r.frequency, "next_due_date": r.next_due_date.isoformat(),
        "is_active": r.is_active, "is_subscription": r.is_subscription,
        "account": {"id": r.account_id, "name": r.account.name},
        "category": (r.category.name if r.category_id else None),
    }


def _credit_card(c):
    return {
        "id": c.id, "name": c.account.name,
        "credit_limit": _money(c.credit_limit),
        "current_debt": _money(c.current_debt),
        "available_credit": _money(c.available_credit),
        "utilization_percent": _money(c.utilization_percent),
        "minimum_payment": _money(c.minimum_payment),
        "statement_day": c.statement_day, "payment_due_day": c.payment_due_day,
    }


def _category(c):
    return {
        "id": c.id, "name": c.name, "type": c.category_type,
        "type_display": c.get_category_type_display(),
        "monthly_limit": _money(c.monthly_limit) if c.monthly_limit is not None else None,
    }


def _draft(d):
    return {
        "id": d.id, "batch_id": d.batch_id, "source": d.source,
        "external_id": d.external_id, "merchant": d.merchant,
        "description": d.description, "amount": _money(d.amount),
        "currency": d.currency, "transaction_date": d.transaction_date.isoformat(),
        "transaction_type": d.transaction_type,
        "category_id": d.suggested_category_id,
        "account_id": d.account_id, "destination_account_id": d.destination_account_id,
        "confidence": _money(d.confidence), "status": d.status,
        "fingerprint": d.fingerprint, "duplicate_of": d.duplicate_of_id,
        "transaction_id": d.transaction_id,
        "created_at": d.created_at.isoformat(),
    }


def _batch(b):
    return {
        "id": b.id, "source": b.source, "external_batch_id": b.external_batch_id,
        "status": b.status, "item_count": b.item_count,
        "created_at": b.created_at.isoformat(),
    }


# --------------------------------------------------------------------------- #
# read handlers  (user is always ``user`` = token.user)
# --------------------------------------------------------------------------- #
def _h_get_summary(user, args):
    s = dashboard_summary(user)
    return {
        "assets": _money(s["assets"]), "liabilities": _money(s["liabilities"]),
        "capital": _money(s["capital"]), "income": _money(s["income"]),
        "expenses": _money(s["expenses"]), "card_payments": _money(s["card_payments"]),
        "cash_flow": _money(s["cash_flow"]),
    }


def _h_list_accounts(user, args):
    qs = Account.objects.filter(user=user)
    if args.get("active_only", True):
        qs = qs.filter(is_active=True)
    qs = qs.order_by("account_type", "name")
    limit, offset = _page_args(args)
    total = qs.count()
    return {"accounts": [_account(a) for a in qs[offset:offset + limit]],
            "total": total, "limit": limit, "offset": offset}


def _build_tx_qs(user, args):
    qs = FinancialTransaction.objects.filter(user=user).select_related(
        "account", "destination_account", "category"
    )
    if args.get("transaction_type"):
        qs = qs.filter(transaction_type=args["transaction_type"])
    if args.get("status"):
        qs = qs.filter(status=args["status"])
    if args.get("account_id"):
        qs = qs.filter(account_id=args["account_id"])
    if args.get("category_id"):
        qs = qs.filter(category_id=args["category_id"])
    if args.get("date_from"):
        qs = qs.filter(date__gte=import_services.validate_date(args["date_from"]))
    if args.get("date_to"):
        qs = qs.filter(date__lte=import_services.validate_date(args["date_to"]))
    if args.get("search"):
        from django.db.models import Q
        term = args["search"].strip()
        qs = qs.filter(
            Q(description__icontains=term)
            | Q(counterparty__icontains=term)
            | Q(notes__icontains=term)
        )
    return qs.order_by("-date", "-id")


def _h_list_transactions(user, args):
    qs = _build_tx_qs(user, args)
    limit, offset = _page_args(args)
    total = qs.count()
    return {"transactions": [_transaction(t) for t in qs[offset:offset + limit]],
            "total": total, "limit": limit, "offset": offset}


def _h_search_transactions(user, args):
    args = dict(args)
    args["search"] = args.pop("query")
    args.setdefault("limit", 20)
    return _h_list_transactions(user, args)


def _h_spending_by_category(user, args):
    from django.db.models import Sum
    today = timezone.localdate()
    rows = (
        FinancialTransaction.objects.filter(
            user=user, status=FinancialTransaction.Status.CLEARED,
            transaction_type=FinancialTransaction.TransactionType.EXPENSE,
            date__year=today.year, date__month=today.month, category__isnull=False,
        )
        .values("category__name")
        .annotate(total=Sum("amount"))
        .order_by("-total")
    )
    breakdown = [
        {"category": r["category__name"], "total": _money(r["total"])} for r in rows
    ]
    grand = sum((Decimal(str(r["total"] or 0)) for r in rows), Decimal("0.00"))
    return {"month": today.isoformat(), "breakdown": breakdown, "total": _money(grand)}


def _h_income_summary(user, args):
    s = dashboard_summary(user)
    return {"income": _money(s["income"]), "expenses": _money(s["expenses"]),
            "card_payments": _money(s["card_payments"]),
            "cash_flow": _money(s["cash_flow"])}


def _h_get_subscriptions(user, args):
    qs = RecurringPayment.objects.filter(user=user, is_subscription=True).select_related(
        "account", "category"
    )
    if args.get("active_only", True):
        qs = qs.filter(is_active=True)
    qs = qs.order_by("next_due_date", "name")
    limit, offset = _page_args(args)
    total = qs.count()
    return {"subscriptions": [_recurring(r) for r in qs[offset:offset + limit]],
            "total": total, "limit": limit, "offset": offset}


def _h_get_credit_cards(user, args):
    qs = CreditCard.objects.filter(user=user).select_related("account").order_by(
        "account__name"
    )
    limit, offset = _page_args(args)
    total = qs.count()
    return {"credit_cards": [_credit_card(c) for c in qs[offset:offset + limit]],
            "total": total, "limit": limit, "offset": offset}


def _h_upcoming_bills(user, args):
    from datetime import timedelta
    days = int(args.get("days", 30) or 30)
    if days < 1 or days > 365:
        raise InputInvalid("days debe estar entre 1 y 365.")
    until = timezone.localdate() + timedelta(days=days)
    qs = RecurringPayment.objects.filter(
        user=user, is_active=True, next_due_date__lte=until
    ).select_related("account", "category").order_by("next_due_date")
    limit, offset = _page_args(args)
    total = qs.count()
    return {"upcoming": [_recurring(r) for r in qs[offset:offset + limit]],
            "total": total, "limit": limit, "offset": offset}


def _h_get_categories(user, args):
    qs = Category.objects.filter(user=user)
    if args.get("type"):
        qs = qs.filter(category_type=args["type"])
    qs = qs.order_by("category_type", "name")
    limit, offset = _page_args(args)
    total = qs.count()
    return {"categories": [_category(c) for c in qs[offset:offset + limit]],
            "total": total, "limit": limit, "offset": offset}


# --------------------------------------------------------------------------- #
# draft handlers
# --------------------------------------------------------------------------- #
def _h_create_import_batch(user, args):
    batch = import_services.create_import_batch(
        user, source=args["source"],
        external_batch_id=args.get("external_batch_id"),
        metadata=args.get("metadata"),
    )
    return {"batch": _batch(batch)}


def _h_create_transaction_draft(user, args):
    draft = import_services.create_transaction_draft(
        user,
        source=args["source"], description=args["description"], amount=args["amount"],
        currency=args.get("currency", "USD"),
        transaction_date=args["transaction_date"],
        transaction_type=args["transaction_type"],
        account=args["account_id"], batch=args.get("batch_id"),
        external_id=args.get("external_id"), merchant=args.get("merchant", ""),
        destination_account=args.get("destination_account_id"),
        suggested_category=args.get("category_id"),
        confidence=args.get("confidence", 0),
        raw_metadata=args.get("metadata"),
    )
    return {"draft": _draft(draft), "duplicate": draft.status == TransactionDraft.Status.DUPLICATE}


def _h_update_draft(user, args):
    draft = TransactionDraft.objects.filter(id=args["draft_id"], user=user).first()
    if draft is None:
        raise InputInvalid("draft_id no encontrado.")
    fields = {k: v for k, v in args.items() if k in {
        "merchant", "description", "amount", "currency", "transaction_date",
        "transaction_type", "confidence", "external_id",
    }}
    updated = import_services.update_draft(
        draft, reviewer=user,
        account=args.get("account_id"),
        destination_account=args.get("destination_account_id"),
        suggested_category=args.get("category_id"),
        **fields,
    )
    return {"draft": _draft(updated)}


def _h_list_pending_drafts(user, args):
    status = args.get("status", "pending")
    qs = TransactionDraft.objects.filter(user=user).select_related(
        "account", "suggested_category", "batch"
    ).order_by("-created_at")
    if status != "all":
        qs = qs.filter(status=status)
    limit, offset = _page_args(args)
    total = qs.count()
    return {"drafts": [_draft(d) for d in qs[offset:offset + limit]],
            "total": total, "limit": limit, "offset": offset}


def _h_reject_draft(user, args):
    draft = TransactionDraft.objects.filter(id=args["draft_id"], user=user).first()
    if draft is None:
        raise InputInvalid("draft_id no encontrado.")
    rejected = import_services.reject_draft(
        draft, reviewer=user, reason=args.get("reason", "")
    )
    return {"draft": _draft(rejected)}


# --------------------------------------------------------------------------- #
# registry
# --------------------------------------------------------------------------- #
_OBJ = {"type": "object", "additionalProperties": False}


def _schema(**props):
    required = props.pop("_required", [])
    return {**_OBJ, "properties": props, "required": required}


READ_TOOLS = [
    {
        "name": "moneta.get_summary", "scope": SCOPE_READ,
        "description": "Resumen financiero del usuario (patrimonio, ingresos, gastos, flujo).",
        "inputSchema": _schema(),
        "handler": _h_get_summary,
    },
    {
        "name": "moneta.list_accounts", "scope": SCOPE_READ,
        "description": "Lista las cuentas del usuario.",
        "inputSchema": _schema(
            active_only={"type": "boolean"},
            limit={"type": "integer", "minimum": 1},
            offset={"type": "integer", "minimum": 0},
        ),
        "handler": _h_list_accounts,
    },
    {
        "name": "moneta.list_transactions", "scope": SCOPE_READ,
        "description": "Lista transacciones con filtros opcionales.",
        "inputSchema": _schema(
            limit={"type": "integer", "minimum": 1},
            offset={"type": "integer", "minimum": 0},
            transaction_type={"type": "string", "enum": [
                "income", "expense", "transfer", "card_payment", "collection"]},
            status={"type": "string", "enum": ["pending", "cleared", "void"]},
            account_id={"type": "integer", "minimum": 1},
            category_id={"type": "integer", "minimum": 1},
            date_from={"type": "string"}, date_to={"type": "string"},
            search={"type": "string", "maxLength": 120},
        ),
        "handler": _h_list_transactions,
    },
    {
        "name": "moneta.search_transactions", "scope": SCOPE_READ,
        "description": "Busca transacciones por texto libre.",
        "inputSchema": _schema(
            query={"type": "string", "minLength": 1, "maxLength": 120},
            limit={"type": "integer", "minimum": 1},
            offset={"type": "integer", "minimum": 0},
            _required=["query"],
        ),
        "handler": _h_search_transactions,
    },
    {
        "name": "moneta.get_spending_by_category", "scope": SCOPE_READ,
        "description": "Desglose de gasto por categoria del mes en curso.",
        "inputSchema": _schema(),
        "handler": _h_spending_by_category,
    },
    {
        "name": "moneta.get_income_summary", "scope": SCOPE_READ,
        "description": "Resumen de ingresos y gastos del mes en curso.",
        "inputSchema": _schema(),
        "handler": _h_income_summary,
    },
    {
        "name": "moneta.get_subscriptions", "scope": SCOPE_READ,
        "description": "Lista suscripciones y pagos recurrentes marcados como suscripcion.",
        "inputSchema": _schema(
            active_only={"type": "boolean"},
            limit={"type": "integer", "minimum": 1},
            offset={"type": "integer", "minimum": 0},
        ),
        "handler": _h_get_subscriptions,
    },
    {
        "name": "moneta.get_credit_cards", "scope": SCOPE_READ,
        "description": "Lista tarjetas de credito con saldos y metricas.",
        "inputSchema": _schema(
            limit={"type": "integer", "minimum": 1},
            offset={"type": "integer", "minimum": 0},
        ),
        "handler": _h_get_credit_cards,
    },
    {
        "name": "moneta.get_upcoming_bills", "scope": SCOPE_READ,
        "description": "Pagos recurrentes proximos a vencer.",
        "inputSchema": _schema(
            days={"type": "integer", "minimum": 1, "maximum": 365},
            limit={"type": "integer", "minimum": 1},
            offset={"type": "integer", "minimum": 0},
        ),
        "handler": _h_upcoming_bills,
    },
    {
        "name": "moneta.get_categories", "scope": SCOPE_READ,
        "description": "Lista las categorias del usuario.",
        "inputSchema": _schema(
            type={"type": "string", "enum": ["income", "expense", "transfer"]},
            limit={"type": "integer", "minimum": 1},
            offset={"type": "integer", "minimum": 0},
        ),
        "handler": _h_get_categories,
    },
]

DRAFT_TOOLS = [
    {
        "name": "moneta.create_import_batch", "scope": SCOPE_DRAFT,
        "description": "Crea un lote de importacion para agrupar borradores.",
        "inputSchema": _schema(
            source={"type": "string", "minLength": 1, "maxLength": 50},
            external_batch_id={"type": "string", "maxLength": 100},
            metadata={"type": "object"},
            _required=["source"],
        ),
        "handler": _h_create_import_batch,
    },
    {
        "name": "moneta.create_transaction_draft", "scope": SCOPE_DRAFT,
        "description": "Crea un borrador de transaccion para revision humana.",
        "inputSchema": _schema(
            batch_id={"type": "integer", "minimum": 1},
            source={"type": "string", "minLength": 1, "maxLength": 50},
            external_id={"type": "string", "maxLength": 100},
            merchant={"type": "string", "maxLength": 200},
            description={"type": "string", "minLength": 1, "maxLength": 180},
            amount={"type": "number", "minimum": 0.01},
            currency={"type": "string", "pattern": "[A-Za-z]{3}"},
            transaction_date={"type": "string"},
            transaction_type={"type": "string", "enum": [
                "income", "expense", "transfer", "card_payment", "collection"]},
            account_id={"type": "integer", "minimum": 1},
            destination_account_id={"type": "integer", "minimum": 1},
            category_id={"type": "integer", "minimum": 1},
            confidence={"type": "number", "minimum": 0, "maximum": 1},
            metadata={"type": "object"},
            _required=["source", "description", "amount", "currency",
                       "transaction_date", "transaction_type", "account_id"],
        ),
        "handler": _h_create_transaction_draft,
    },
    {
        "name": "moneta.update_draft", "scope": SCOPE_DRAFT,
        "description": "Actualiza un borrador pendiente.",
        "inputSchema": _schema(
            draft_id={"type": "integer", "minimum": 1},
            merchant={"type": "string", "maxLength": 200},
            description={"type": "string", "minLength": 1, "maxLength": 180},
            amount={"type": "number", "minimum": 0.01},
            currency={"type": "string", "pattern": "[A-Za-z]{3}"},
            transaction_date={"type": "string"},
            transaction_type={"type": "string", "enum": [
                "income", "expense", "transfer", "card_payment", "collection"]},
            account_id={"type": "integer", "minimum": 1},
            destination_account_id={"type": "integer", "minimum": 1},
            category_id={"type": "integer", "minimum": 1},
            confidence={"type": "number", "minimum": 0, "maximum": 1},
            external_id={"type": "string", "maxLength": 100},
            _required=["draft_id"],
        ),
        "handler": _h_update_draft,
    },
    {
        "name": "moneta.list_pending_drafts", "scope": SCOPE_DRAFT,
        "description": "Lista borradores del usuario (pendientes por defecto).",
        "inputSchema": _schema(
            status={"type": "string", "enum": [
                "pending", "approved", "rejected", "duplicate", "error", "all"]},
            limit={"type": "integer", "minimum": 1},
            offset={"type": "integer", "minimum": 0},
        ),
        "handler": _h_list_pending_drafts,
    },
    {
        "name": "moneta.reject_draft", "scope": SCOPE_DRAFT,
        "description": "Rechaza un borrador pendiente (sin efecto financiero).",
        "inputSchema": _schema(
            draft_id={"type": "integer", "minimum": 1},
            reason={"type": "string", "maxLength": 500},
            _required=["draft_id"],
        ),
        "handler": _h_reject_draft,
    },
]

ALL_TOOLS = READ_TOOLS + DRAFT_TOOLS
_BY_NAME = {t["name"]: t for t in ALL_TOOLS}

assert not (set(_BY_NAME) & FORBIDDEN_TOOL_NAMES), "forbidden tool leaked into registry"
assert len(_BY_NAME) == len(ALL_TOOLS), "duplicate tool name in registry"


def list_tool_specs():
    """Public shape for MCP ``list_tools``."""
    return [
        {"name": t["name"], "description": t["description"],
         "inputSchema": t["inputSchema"]}
        for t in ALL_TOOLS
    ]


def get_spec(name):
    return _BY_NAME.get(name)


# --------------------------------------------------------------------------- #
# dispatch
# --------------------------------------------------------------------------- #
def execute(token, name, arguments, *, transport="", client_ip=None, user_agent=""):
    """Run tool ``name`` for ``token`` and write an audit event.

    Returns the tool's structured dict result.  Raises :class:`MCPToolError`
    subclasses for denied / invalid / not-found / rate-limited; other
    exceptions are logged as ``error`` and re-raised.
    """
    start = time.monotonic()
    spec = get_spec(name)
    user = token.user
    scope = spec["scope"] if spec else ""

    def _audit(result, *, error_code="", object_reference=""):
        MCPAuditEvent.record(
            user=user, token=token, tool=name, scope=scope, result=result,
            transport=transport,
            duration_ms=int((time.monotonic() - start) * 1000),
            object_reference=object_reference, error_code=error_code,
            client_ip=client_ip, user_agent=user_agent,
        )

    # Bound every authenticated request before lookup, scope checks, or any
    # database-backed audit write.  A single sampled event records saturation
    # without turning rejected traffic into an unbounded write primitive.
    try:
        ratelimit.check(user.id, "__all__")
    except ratelimit.RateLimitExceeded as exc:
        if ratelimit.should_audit_global_limit(user.id):
            _audit(MCPAuditEvent.Result.DENIED, error_code="rate_limited")
        raise RateLimited(str(exc)) from exc

    if spec is None:
        _audit(MCPAuditEvent.Result.DENIED, error_code="tool_not_found")
        raise ToolNotFound(f"Herramienta desconocida: {name}")

    if not token.has_scope(scope):
        _audit(MCPAuditEvent.Result.DENIED, error_code="scope_denied")
        raise ScopeDenied(
            f"El token no tiene el scope '{scope}' requerido por {name}."
        )

    try:
        ratelimit.check(user.id, name)
    except ratelimit.RateLimitExceeded as exc:
        _audit(MCPAuditEvent.Result.DENIED, error_code="rate_limited")
        raise RateLimited(str(exc)) from exc

    try:
        clean = _validate(spec["inputSchema"], arguments)
    except MCPToolError as exc:
        _audit(MCPAuditEvent.Result.FAILURE, error_code=exc.code)
        raise

    try:
        result = spec["handler"](user, clean)
    except MCPToolError as exc:
        _audit(MCPAuditEvent.Result.FAILURE, error_code=exc.code)
        raise
    except import_services.ImportError as exc:
        _audit(MCPAuditEvent.Result.FAILURE, error_code=type(exc).__name__)
        raise InputInvalid(str(exc)) from exc
    except Exception as exc:  # noqa: BLE001 - audited then re-raised
        _audit(MCPAuditEvent.Result.ERROR, error_code=type(exc).__name__)
        raise

    ref = ""
    for key in ("draft", "batch"):
        if isinstance(result, dict) and isinstance(result.get(key), dict):
            ref = f"{key}:{result[key].get('id')}"
            break
    _audit(MCPAuditEvent.Result.SUCCESS, object_reference=ref)
    return result
