"""HTTP views and UI helpers for the Moneta finance app."""

import csv
import secrets
from datetime import date, timedelta
from decimal import Decimal
from types import SimpleNamespace

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, transaction
from django.db.models import ProtectedError
from django.db.models import Case, Count, DecimalField, F, Q, Sum, Value, When
from django.http import Http404, HttpResponse
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import translation
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils import timezone
from django.utils.translation import check_for_language
from django.views.decorators.http import require_http_methods

from .accounting import (
    delete_invoice_journal,
    delete_transaction_journal,
    lock_financial_user,
    rebuild_account_balances,
    sync_credit_card_account_balance,
    sync_invoice_journal,
    sync_transaction_journal,
)
from .forms import (
    AccountForm,
    CategoryForm,
    CreditCardForm,
    InvoiceForm,
    InitialSuperuserForm,
    RecurringPaymentForm,
    TransactionForm,
)
from .models import Account, Category, CreditCard, FinancialTransaction, Invoice, RecurringPayment, SetupState
from .product import require_feature
from .security import is_login_locked
from .services import advice_for_user, dashboard_summary, monthly_cash_flow_series


LIST_PAGE_SIZE = 100
EXPORT_ROW_LIMIT = 5000


TX_TYPE_LABELS = {
    FinancialTransaction.TransactionType.INCOME: {"es": "Ingreso", "en": "Income"},
    FinancialTransaction.TransactionType.EXPENSE: {"es": "Gasto", "en": "Expense"},
    FinancialTransaction.TransactionType.TRANSFER: {"es": "Transferencia", "en": "Transfer"},
    FinancialTransaction.TransactionType.CARD_PAYMENT: {"es": "Pago de tarjeta", "en": "Card payment"},
    FinancialTransaction.TransactionType.COLLECTION: {"es": "Cobro", "en": "Collection"},
}

TX_STATUS_LABELS = {
    FinancialTransaction.Status.PENDING: {"es": "Pendiente", "en": "Pending"},
    FinancialTransaction.Status.CLEARED: {"es": "Confirmado", "en": "Cleared"},
    FinancialTransaction.Status.VOID: {"es": "Anulado", "en": "Voided"},
}

INVOICE_TYPE_LABELS = {
    Invoice.InvoiceType.ISSUED: {"es": "Emitida", "en": "Issued"},
    Invoice.InvoiceType.RECEIVED: {"es": "Recibida", "en": "Received"},
}

INVOICE_STATUS_LABELS = {
    Invoice.Status.DRAFT: {"es": "Borrador", "en": "Draft"},
    Invoice.Status.PENDING: {"es": "Pendiente", "en": "Pending"},
    Invoice.Status.PAID: {"es": "Pagada", "en": "Paid"},
    Invoice.Status.OVERDUE: {"es": "Vencida", "en": "Overdue"},
    Invoice.Status.VOID: {"es": "Anulada", "en": "Voided"},
}

FREQUENCY_LABELS = {
    RecurringPayment.Frequency.WEEKLY: {"es": "Semanal", "en": "Weekly"},
    RecurringPayment.Frequency.BIWEEKLY: {"es": "Quincenal", "en": "Biweekly"},
    RecurringPayment.Frequency.MONTHLY: {"es": "Mensual", "en": "Monthly"},
    RecurringPayment.Frequency.QUARTERLY: {"es": "Trimestral", "en": "Quarterly"},
    RecurringPayment.Frequency.YEARLY: {"es": "Anual", "en": "Yearly"},
}

ACCOUNT_TYPE_LABELS = {
    Account.AccountType.CASH: {"es": "Efectivo", "en": "Cash"},
    Account.AccountType.CHECKING: {"es": "Cuenta corriente", "en": "Checking"},
    Account.AccountType.BANK: {"es": "Banco", "en": "Bank"},
    Account.AccountType.SAVINGS: {"es": "Ahorro", "en": "Savings"},
    Account.AccountType.INVESTMENT: {"es": "Inversión", "en": "Investment"},
    Account.AccountType.CREDIT_CARD: {"es": "Tarjeta de crédito", "en": "Credit card"},
    Account.AccountType.LOAN: {"es": "Préstamo", "en": "Loan"},
    Account.AccountType.RECEIVABLE: {"es": "Cuenta por cobrar", "en": "Receivable"},
    Account.AccountType.PAYABLE: {"es": "Cuenta por pagar", "en": "Payable"},
    Account.AccountType.CAPITAL: {"es": "Capital", "en": "Capital"},
}


ACCOUNT_TYPE_ICONS = {
    Account.AccountType.CASH: "Caja",
    Account.AccountType.CHECKING: "Cta",
    Account.AccountType.BANK: "Banco",
    Account.AccountType.SAVINGS: "Ahorro",
    Account.AccountType.INVESTMENT: "Inv",
    Account.AccountType.CREDIT_CARD: "TC",
    Account.AccountType.LOAN: "Pr",
    Account.AccountType.RECEIVABLE: "CxC",
    Account.AccountType.PAYABLE: "CxP",
    Account.AccountType.CAPITAL: "Cap",
}


CATEGORY_TYPE_LABELS = {
    Category.CategoryType.INCOME: {"es": "Ingreso", "en": "Income"},
    Category.CategoryType.EXPENSE: {"es": "Gasto", "en": "Expense"},
    Category.CategoryType.TRANSFER: {"es": "Transferencia", "en": "Transfer"},
}


ACCOUNT_NAME_LABELS = {
    "Banco Principal": {"en": "Main Bank"},
    "Ahorro Emergencias": {"en": "Emergency Savings"},
    "Visa Personal": {"en": "Personal Visa"},
}


CATEGORY_NAME_LABELS = {
    "Nómina": {"en": "Payroll"},
    "Consultoría": {"en": "Consulting"},
    "Supermercado": {"en": "Groceries"},
    "Transporte": {"en": "Transport"},
    "Software": {"en": "Software"},
    "Entretenimiento": {"en": "Entertainment"},
    "Seguros": {"en": "Insurance"},
    "Salud": {"en": "Health"},
    "Educación": {"en": "Education"},
}



def is_english(request):
    return (getattr(request, "LANGUAGE_CODE", "") or "").lower().startswith("en")


def localized_label(mapping, key, english=False, fallback=""):
    labels = mapping.get(key)
    if not labels:
        return fallback or str(key)
    return labels["en" if english else "es"]


def localized_choices(choices, mapping, english=False):
    return [(value, localized_label(mapping, value, english, fallback=label)) for value, label in choices]


def localized_name(mapping, name, english=False):
    if english:
        return mapping.get(name, {}).get("en", name)
    return name


def decorate_account(account, english=False):
    account.display_name_ui = localized_name(ACCOUNT_NAME_LABELS, account.name, english)
    account.account_type_label_ui = localized_label(
        ACCOUNT_TYPE_LABELS,
        account.account_type,
        english,
        account.get_account_type_display(),
    )
    account.account_type_icon_ui = ACCOUNT_TYPE_ICONS.get(account.account_type, "Cuenta")
    return account


def decorate_category(category, english=False):
    if category:
        category.display_name_ui = category.name
    return category


def decorate_budget_rows(rows, english=False):
    for row in rows:
        decorate_category(row.get("category"), english)
    return rows


def _safe_next_url(request):
    next_url = request.POST.get("next") or request.META.get("HTTP_REFERER") or "/"
    if url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        return next_url
    return "/"


@require_http_methods(["POST"])
def change_language(request):
    next_url = _safe_next_url(request)
    language = (request.POST.get("language") or "").strip().lower()

    if not check_for_language(language):
        messages.error(
            request,
            "Invalid language selection." if is_english(request) else "Seleccion de idioma no valida.",
        )
        return redirect(next_url)

    translation.activate(language)
    if hasattr(request, "session"):
        request.session["django_language"] = language

    response = redirect(next_url)
    response.set_cookie(
        settings.LANGUAGE_COOKIE_NAME,
        language,
        max_age=settings.LANGUAGE_COOKIE_AGE,
        path=settings.LANGUAGE_COOKIE_PATH,
        domain=settings.LANGUAGE_COOKIE_DOMAIN,
        secure=not settings.DEBUG,
        samesite="Lax",
    )

    if language.startswith("en"):
        messages.success(request, "Language switched to English.")
    else:
        messages.success(request, "Idioma cambiado a Español.")
    return response


@require_http_methods(["GET", "POST"])
def initial_setup(request):
    if not getattr(settings, "MONETA_WEB_SETUP_ENABLED", False):
        raise Http404

    # Additional guard: require header or IP allowlist when web setup is enabled
    allowed_ips = getattr(settings, "MONETA_SETUP_ALLOWED_IPS", [])
    required_header = getattr(settings, "MONETA_SETUP_REQUIRE_HEADER", False)

    if required_header:
        header_value = request.META.get("HTTP_X_MONETA_SETUP", "")
        if header_value != "1":
            raise Http404

    if allowed_ips:
        client_ip_val = client_ip(request)
        if client_ip_val not in allowed_ips and client_ip_val != "unknown":
            raise Http404

    User = get_user_model()
    if User.objects.exists():
        messages.info(request, "La configuracion inicial ya fue completada.")
        return redirect("login")

    if request.method == "POST":
        form = InitialSuperuserForm(request.POST)
        form_is_valid = form.is_valid()
        supplied_token = request.POST.get("setup_token", "")
        expected_token = getattr(settings, "MONETA_SETUP_TOKEN", "")
        if not secrets.compare_digest(supplied_token, expected_token):
            form.add_error(None, "El token de configuracion no es valido.")
        elif form_is_valid:
            with transaction.atomic():
                setup_state = SetupState.objects.select_for_update().get(pk=1)
                if setup_state.consumed_at or User.objects.exists():
                    messages.info(request, "La configuracion inicial ya fue completada.")
                    return redirect("login")
                user = User.objects.create_superuser(
                    username=form.cleaned_data["username"],
                    email=form.cleaned_data.get("email", ""),
                    password=form.cleaned_data["password"],
                )
                setup_state.consumed_at = timezone.now()
                setup_state.save(update_fields=["consumed_at"])
            login(request, user)
            messages.success(request, "Superadministrador creado correctamente.")
            return redirect("finanzas:dashboard")
    else:
        form = InitialSuperuserForm(initial={"username": "admin"})

    return render(
        request,
        "registration/initial_setup.html",
        {
            "form": form,
            "title": "Configuracion inicial",
            "subtitle": "Crea el usuario master para administrar esta instalacion.",
            "submit_label": "Crear superadmin",
            "cancel_url": "login",
        },
    )


def sanitize_csv_cell(value):
    """Escape spreadsheet formula prefixes before writing CSV exports."""
    if value is None:
        return ""
    text = str(value)
    if text and text[0] in ("=", "+", "-", "@"):
        return f"'{text}"
    return text


def parse_iso_date(value):
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def recurring_overview(queryset):
    """Summarize active recurring rows for list headers and dashboards."""
    today = timezone.localdate()
    limit = today + timedelta(days=30)
    factor = Case(
        When(frequency=RecurringPayment.Frequency.WEEKLY, then=Value(Decimal("4.00"))),
        When(frequency=RecurringPayment.Frequency.BIWEEKLY, then=Value(Decimal("2.00"))),
        When(frequency=RecurringPayment.Frequency.QUARTERLY, then=Value(Decimal("0.333333"))),
        When(frequency=RecurringPayment.Frequency.YEARLY, then=Value(Decimal("0.083333"))),
        default=Value(Decimal("1.00")),
        output_field=DecimalField(max_digits=8, decimal_places=6),
    )
    totals = queryset.filter(is_active=True).aggregate(
        monthly_projection=Sum(
            F("amount") * factor,
            output_field=DecimalField(max_digits=18, decimal_places=6),
        ),
        due_next_30=Sum("amount", filter=Q(next_due_date__range=(today, limit))),
        active_count=Count("id"),
    )

    return {
        "monthly_projection": (totals["monthly_projection"] or Decimal("0.00")).quantize(Decimal("0.01")),
        "due_next_30": (totals["due_next_30"] or Decimal("0.00")).quantize(Decimal("0.01")),
        "active_count": totals["active_count"],
    }


def paginate_queryset(request, queryset, per_page=LIST_PAGE_SIZE):
    """Paginate list views using a shared page size."""
    paginator = Paginator(queryset, per_page)
    return paginator.get_page(request.GET.get("page"))


INSURANCE_PRESETS = {
    "segurovida": "Seguro de vida privado",
    "segurosalud": "Seguro de salud privado",
    "seguroingreso": "Seguro de ingreso",
}


def subscription_preset_initial(preset_key, user):
    return {
        "name": INSURANCE_PRESETS[preset_key],
        "frequency": RecurringPayment.Frequency.MONTHLY,
        "next_due_date": timezone.localdate(),
        "is_active": True,
        "category": Category.objects.filter(user=user, name__iexact="Seguros").first(),
    }


def category_helper_context():
    return {
        "helper_note": "Si el campo Categoria aparece vacio, crea primero una categoria de ingreso, gasto o transferencia.",
        "helper_url": "finanzas:category_create",
        "helper_label": "Crear categoria",
    }


def save_user_form(
    request,
    form_class,
    template_name,
    success_url,
    title,
    subtitle,
    submit_label,
    extra_context=None,
    instance_mutator=None,
    instance=None,
    after_save=None,
    initial_data=None,
):
    """Shared create/edit flow for user-owned ModelForms.

    The helper keeps view code consistent: instantiate with request.user,
    assign ownership before save, run optional mutation/hooks and handle
    uniqueness errors without exposing database exceptions to the user.
    """
    if request.method == "POST":
        form = form_class(request.POST, user=request.user, instance=instance)
        if form.is_valid():
            try:
                with transaction.atomic():
                    lock_financial_user(request.user)
                    obj = form.save(commit=False)
                    if instance_mutator:
                        instance_mutator(obj)
                    if hasattr(obj, "user_id"):
                        obj.user = request.user
                    obj.full_clean()
                    obj.save()
                    form.save_m2m()
                    if after_save:
                        after_save(obj)
                messages.success(request, "Registro guardado correctamente.")
                return redirect(success_url)
            except IntegrityError:
                form.add_error(None, "No se pudo guardar. Verifica que no exista ya un registro con los mismos datos.")
    else:
        form = form_class(user=request.user, instance=instance, initial=initial_data)

    context = {
        "form": form,
        "title": title,
        "subtitle": subtitle,
        "submit_label": submit_label,
        "cancel_url": success_url,
        "is_edit": bool(instance),
    }
    if extra_context:
        context.update(extra_context)
    return render(request, template_name, context)


@login_required
@require_http_methods(["GET", "POST"])
def confirm_delete(request, instance, success_url, label):
    if request.method == "POST":
        try:
            instance.delete()
            messages.success(request, f"{label} eliminado correctamente.")
        except ProtectedError:
            messages.error(
                request,
                f"No se puede eliminar {label.lower()} porque tiene registros asociados.",
            )
        return redirect(success_url)
    return render(
        request,
        "finanzas/confirm_delete.html",
        {
            "title": f"Eliminar {label.lower()}",
            "subtitle": f"Esta accion eliminara el registro: {instance}",
            "cancel_url": success_url,
            "label": label,
        },
    )


@login_required
def dashboard(request):
    context = dashboard_summary(request.user)
    context["advice"] = advice_for_user(request.user, context)
    english = is_english(request)
    context["cash_flow_series"] = monthly_cash_flow_series(request.user, english=english)
    for account in context.get("accounts", []):
        decorate_account(account, english)
    for card in context.get("credit_cards", []):
        decorate_account(card.account, english)
    decorate_budget_rows(context.get("category_budget", []), english)
    for payment in context.get("upcoming", []):
        decorate_account(payment.account, english)
        decorate_category(payment.category, english)
        payment.frequency_label_ui = localized_label(
            FREQUENCY_LABELS,
            payment.frequency,
            english,
            payment.get_frequency_display(),
        )
    for transaction in context.get("recent_transactions", []):
        decorate_account(transaction.account, english)
        decorate_category(transaction.category, english)
        transaction.status_label_ui = localized_label(TX_STATUS_LABELS, transaction.status, english, transaction.get_status_display())
    return render(request, "finanzas/dashboard.html", context)


def _get_cached_filter_choices(request, user):
    """Get filter choices from session cache with 5-minute TTL."""
    cache_key = "_transaction_list_filter_cache"
    now = timezone.now().timestamp()
    cached = request.session.get(cache_key)
    if cached and cached.get("user_id") == user.id:
        expires = cached.get("expires", 0)
        if expires > now:
            # Reconstruct objects from cached data
            accounts_data = cached.get("accounts", [])
            categories_data = cached.get("categories", [])
            accounts = [SimpleNamespace(id=a["id"], name=a["name"], is_active=a["is_active"],
                                       account_type=a["account_type"], currency=a["currency"],
                                       opening_balance=a["opening_balance"], current_balance=a["current_balance"])
                       for a in accounts_data]
            categories = [SimpleNamespace(id=c["id"], name=c["name"], category_type=c["category_type"],
                                         monthly_limit=c.get("monthly_limit")) for c in categories_data]
            return accounts, categories

    accounts_qs = Account.objects.filter(user=user, is_active=True).order_by("name")
    categories_qs = Category.objects.filter(user=user).order_by("name")

    # Store serializable data in session
    accounts_data = [{"id": a.id, "name": a.name, "is_active": a.is_active,
                      "account_type": a.account_type, "currency": a.currency,
                      "opening_balance": str(a.opening_balance), "current_balance": str(a.current_balance)}
                     for a in accounts_qs]
    categories_data = [{"id": c.id, "name": c.name, "category_type": c.category_type,
                        "monthly_limit": str(c.monthly_limit) if c.monthly_limit else None}
                       for c in categories_qs]

    request.session["_transaction_list_filter_cache"] = {
        "user_id": user.id,
        "expires": timezone.now().timestamp() + 300,  # 5 minutes
        "accounts": accounts_data,
        "categories": categories_data,
    }

    return list(accounts_qs), list(categories_qs)


@login_required
def transaction_list(request):
    english = is_english(request)
    base_queryset = _build_transaction_queryset(request.user, request)

    query = request.GET.get("q", "").strip()
    tx_type = request.GET.get("transaction_type", "").strip()
    status = request.GET.get("status", "").strip()
    account_id = request.GET.get("account", "").strip()
    category_id = request.GET.get("category", "").strip()

    summary = base_queryset.aggregate(
        income=Sum(
            "amount",
            filter=Q(
                status=FinancialTransaction.Status.CLEARED,
                transaction_type__in=[
                    FinancialTransaction.TransactionType.INCOME,
                    FinancialTransaction.TransactionType.COLLECTION,
                ],
            ),
        ),
        expense=Sum(
            "amount",
            filter=Q(
                status=FinancialTransaction.Status.CLEARED,
                transaction_type=FinancialTransaction.TransactionType.EXPENSE,
            ),
        ),
        card_payment=Sum(
            "amount",
            filter=Q(
                status=FinancialTransaction.Status.CLEARED,
                transaction_type=FinancialTransaction.TransactionType.CARD_PAYMENT,
            ),
        ),
    )
    income = summary["income"] or Decimal("0.00")
    expense = summary["expense"] or Decimal("0.00")
    card_payment = summary["card_payment"] or Decimal("0.00")
    page_obj = paginate_queryset(request, base_queryset)
    transactions = list(page_obj)
    for transaction in transactions:
        transaction.transaction_type_label_ui = localized_label(
            TX_TYPE_LABELS,
            transaction.transaction_type,
            english,
            transaction.get_transaction_type_display(),
        )
        transaction.status_label_ui = localized_label(
            TX_STATUS_LABELS,
            transaction.status,
            english,
            transaction.get_status_display(),
        )

    accounts, categories = _get_cached_filter_choices(request, request.user)

    return render(
        request,
        "finanzas/transaction_list.html",
        {
            "transactions": transactions,
            "page_obj": page_obj,
            "type_choices": localized_choices(FinancialTransaction.TransactionType.choices, TX_TYPE_LABELS, english),
            "status_choices": localized_choices(FinancialTransaction.Status.choices, TX_STATUS_LABELS, english),
            "accounts": accounts,
            "categories": categories,
            "filters": {
                "q": query,
                "transaction_type": tx_type,
                "status": status,
                "account": account_id,
                "category": category_id,
                "date_from": request.GET.get("date_from", "").strip(),
                "date_to": request.GET.get("date_to", "").strip(),
            },
            "summary_income": income,
            "summary_expense": expense,
            "summary_card_payment": card_payment,
            "summary_cash_flow": income - expense - card_payment,
        },
    )


@login_required
def transaction_create(request):
    return save_user_form(
        request,
        TransactionForm,
        "finanzas/form.html",
        "finanzas:transaction_list",
        "Nuevo movimiento",
        "Registra ingresos, gastos, pagos de tarjeta, cobros o transferencias.",
        "Guardar movimiento",
        extra_context=category_helper_context(),
        after_save=lambda obj: (sync_transaction_journal(obj), rebuild_account_balances(request.user, force_account_ids=[obj.account_id, obj.destination_account_id, obj.related_credit_card.account_id if obj.related_credit_card else None])),
    )


@login_required
def transaction_edit(request, pk):
    instance = get_object_or_404(FinancialTransaction, pk=pk, user=request.user)
    original_account_ids = {instance.account_id}
    if instance.destination_account_id:
        original_account_ids.add(instance.destination_account_id)
    if instance.related_credit_card_id and instance.related_credit_card:
        original_account_ids.add(instance.related_credit_card.account_id)

    def after_transaction_edit(obj):
        account_ids = set(original_account_ids)
        account_ids.add(obj.account_id)
        if obj.destination_account_id:
            account_ids.add(obj.destination_account_id)
        if obj.related_credit_card_id and obj.related_credit_card:
            account_ids.add(obj.related_credit_card.account_id)
        sync_transaction_journal(obj)
        rebuild_account_balances(request.user, force_account_ids=account_ids)

    return save_user_form(
        request,
        TransactionForm,
        "finanzas/form.html",
        "finanzas:transaction_list",
        "Editar movimiento",
        "Actualiza valores y la contabilidad se recalculará automáticamente.",
        "Guardar cambios",
        instance=instance,
        extra_context=category_helper_context(),
        after_save=after_transaction_edit,
    )


@login_required
@require_http_methods(["GET", "POST"])
def transaction_delete(request, pk):
    instance = get_object_or_404(FinancialTransaction, pk=pk, user=request.user)
    if request.method == "POST":
        account_ids = {instance.account_id}
        if instance.destination_account_id:
            account_ids.add(instance.destination_account_id)
        if instance.related_credit_card_id and instance.related_credit_card:
            account_ids.add(instance.related_credit_card.account_id)
        try:
            with transaction.atomic():
                lock_financial_user(request.user)
                delete_transaction_journal(instance)
                instance.delete()
                rebuild_account_balances(request.user, force_account_ids=account_ids)
            messages.success(request, "Movimiento eliminado correctamente.")
        except ProtectedError:
            messages.error(request, "No se puede eliminar el movimiento porque tiene registros asociados.")
        return redirect("finanzas:transaction_list")
    return render(
        request,
        "finanzas/confirm_delete.html",
        {
            "title": "Eliminar movimiento",
            "subtitle": f"Esta accion eliminara el movimiento: {instance.description}",
            "cancel_url": "finanzas:transaction_list",
            "label": "Movimiento",
        },
    )


@login_required
def account_create(request):
    return save_user_form(
        request,
        AccountForm,
        "finanzas/form.html",
        "finanzas:settings",
        "Nueva cuenta",
        "Agrega bancos, efectivo, tarjetas, préstamos, inversiones o capital.",
        "Guardar cuenta",
        after_save=lambda obj: (sync_credit_card_account_balance(obj), rebuild_account_balances(request.user, force_account_ids=[obj.id])),
    )


@login_required
def account_edit(request, pk):
    instance = get_object_or_404(Account, pk=pk, user=request.user)
    return save_user_form(
        request,
        AccountForm,
        "finanzas/form.html",
        "finanzas:settings",
        "Editar cuenta",
        "Ajusta tipo, moneda y balances base.",
        "Guardar cambios",
        instance=instance,
        after_save=lambda obj: (sync_credit_card_account_balance(obj), rebuild_account_balances(request.user, force_account_ids=[obj.id])),
    )


@login_required
@require_http_methods(["GET", "POST"])
def account_delete(request, pk):
    instance = get_object_or_404(Account, pk=pk, user=request.user)
    return confirm_delete(request, instance, "finanzas:settings", "Cuenta")


@login_required
def category_create(request):
    return save_user_form(
        request,
        CategoryForm,
        "finanzas/form.html",
        "finanzas:settings",
        "Nueva categoria",
        "Organiza ingresos, gastos y transferencias con límites mensuales.",
        "Guardar categoria",
    )


@login_required
def category_edit(request, pk):
    instance = get_object_or_404(Category, pk=pk, user=request.user)
    return save_user_form(
        request,
        CategoryForm,
        "finanzas/form.html",
        "finanzas:settings",
        "Editar categoria",
        "Actualiza nombre, tipo o limite mensual.",
        "Guardar cambios",
        instance=instance,
    )


@login_required
@require_http_methods(["GET", "POST"])
def category_delete(request, pk):
    instance = get_object_or_404(Category, pk=pk, user=request.user)
    return confirm_delete(request, instance, "finanzas:settings", "Categoría")


@login_required
def invoice_list(request):
    english = is_english(request)
    queryset = _build_invoice_queryset(request.user, request)

    query = request.GET.get("q", "").strip()
    invoice_type = request.GET.get("invoice_type", "").strip()
    status = request.GET.get("status", "").strip()

    totals = queryset.annotate(total_amount=F("subtotal") + F("tax")).aggregate(
        total=Sum("total_amount"),
        pending=Sum("total_amount", filter=Q(status=Invoice.Status.PENDING)),
        paid=Sum("total_amount", filter=Q(status=Invoice.Status.PAID)),
        overdue=Sum("total_amount", filter=Q(status=Invoice.Status.OVERDUE)),
    )
    page_obj = paginate_queryset(request, queryset)
    invoices = list(page_obj)
    for invoice in invoices:
        invoice.invoice_type_label_ui = localized_label(
            INVOICE_TYPE_LABELS,
            invoice.invoice_type,
            english,
            invoice.get_invoice_type_display(),
        )
        invoice.status_label_ui = localized_label(
            INVOICE_STATUS_LABELS,
            invoice.status,
            english,
            invoice.get_status_display(),
        )

    return render(
        request,
        "finanzas/invoice_list.html",
        {
            "invoices": invoices,
            "page_obj": page_obj,
            "invoice_type_choices": localized_choices(Invoice.InvoiceType.choices, INVOICE_TYPE_LABELS, english),
            "invoice_status_choices": localized_choices(Invoice.Status.choices, INVOICE_STATUS_LABELS, english),
            "filters": {
                "q": query,
                "invoice_type": invoice_type,
                "status": status,
                "date_from": request.GET.get("date_from", "").strip(),
                "date_to": request.GET.get("date_to", "").strip(),
            },
            "summary_total": totals["total"] or Decimal("0.00"),
            "summary_pending": totals["pending"] or Decimal("0.00"),
            "summary_paid": totals["paid"] or Decimal("0.00"),
            "summary_overdue": totals["overdue"] or Decimal("0.00"),
        },
    )


@login_required
def invoice_create(request):
    return save_user_form(
        request,
        InvoiceForm,
        "finanzas/form.html",
        "finanzas:invoice_list",
        "Nueva factura",
        "Registra facturas emitidas y recibidas con estado de pago.",
        "Guardar factura",
        after_save=lambda obj: sync_invoice_journal(obj),
    )


@login_required
def invoice_edit(request, pk):
    instance = get_object_or_404(Invoice, pk=pk, user=request.user)
    return save_user_form(
        request,
        InvoiceForm,
        "finanzas/form.html",
        "finanzas:invoice_list",
        "Editar factura",
        "Actualiza fechas, montos o estado.",
        "Guardar cambios",
        instance=instance,
        after_save=lambda obj: sync_invoice_journal(obj),
    )


@login_required
@require_http_methods(["GET", "POST"])
def invoice_delete(request, pk):
    instance = get_object_or_404(Invoice, pk=pk, user=request.user)
    if request.method == "POST":
        try:
            with transaction.atomic():
                delete_invoice_journal(instance)
                instance.delete()
            messages.success(request, "Factura eliminada correctamente.")
        except ProtectedError:
            messages.error(request, "No se puede eliminar la factura porque tiene registros asociados.")
        return redirect("finanzas:invoice_list")
    return render(
        request,
        "finanzas/confirm_delete.html",
        {
            "title": "Eliminar factura",
            "subtitle": f"Esta accion eliminara la factura: {instance.number}",
            "cancel_url": "finanzas:invoice_list",
            "label": "Factura",
        },
    )


@login_required
@require_feature("subscriptions")
def subscription_list(request):
    english = is_english(request)
    queryset = (
        RecurringPayment.objects.filter(user=request.user, is_subscription=True)
        .select_related("account", "category")
        .order_by("next_due_date", "name")
    )
    active_filter = request.GET.get("active", "all")
    if active_filter == "active":
        queryset = queryset.filter(is_active=True)
    elif active_filter == "inactive":
        queryset = queryset.filter(is_active=False)

    overview = recurring_overview(queryset)
    page_obj = paginate_queryset(request, queryset)
    for subscription in page_obj:
        subscription.frequency_label_ui = localized_label(
            FREQUENCY_LABELS,
            subscription.frequency,
            english,
            subscription.get_frequency_display(),
        )
        subscription.active_label_ui = "Active" if english else "Activa"

    return render(
        request,
        "finanzas/subscription_list.html",
        {
            "page_obj": page_obj,
            "filters": {"active": active_filter},
            "summary_monthly_projection": overview["monthly_projection"],
            "summary_due_next_30": overview["due_next_30"],
            "summary_active_count": overview["active_count"],
            "summary_average_active": (
                (overview["monthly_projection"] / overview["active_count"]).quantize(Decimal("0.01"))
                if overview["active_count"]
                else Decimal("0.00")
            ),
        },
    )


@login_required
@require_feature("subscriptions")
def subscription_create(request):
    preset_key = request.GET.get("preset", "").strip()
    if preset_key and preset_key not in INSURANCE_PRESETS:
        raise Http404
    initial_data = subscription_preset_initial(preset_key, request.user) if preset_key else {}

    def mark_subscription(obj):
        obj.is_subscription = True
        if preset_key:
            obj.name = INSURANCE_PRESETS[preset_key]
            obj.subscription_catalog = RecurringPayment.SubscriptionCatalog.INSURANCE

    return save_user_form(
        request,
        RecurringPaymentForm,
        "finanzas/form.html",
        "finanzas:subscription_list",
        "Nueva suscripción",
        "Registra servicios, afiliaciones y seguros.",
        "Guardar suscripción",
        extra_context=category_helper_context(),
        instance_mutator=mark_subscription,
        initial_data=initial_data,
    )


@login_required
@require_feature("subscriptions")
def subscription_edit(request, pk):
    instance = get_object_or_404(RecurringPayment, pk=pk, user=request.user, is_subscription=True)

    policy_name = instance.name

    def preserve_insurance_name(obj):
        if obj.subscription_catalog == RecurringPayment.SubscriptionCatalog.INSURANCE:
            obj.name = policy_name

    return save_user_form(
        request,
        RecurringPaymentForm,
        "finanzas/form.html",
        "finanzas:subscription_list",
        "Editar suscripción",
        "Actualiza monto, fecha o estado del servicio.",
        "Guardar cambios",
        instance=instance,
        extra_context=category_helper_context(),
        instance_mutator=preserve_insurance_name,
    )


@login_required
@require_http_methods(["GET", "POST"])
@require_feature("subscriptions")
def subscription_delete(request, pk):
    instance = get_object_or_404(RecurringPayment, pk=pk, user=request.user, is_subscription=True)
    return confirm_delete(request, instance, "finanzas:subscription_list", "Suscripcion")


@login_required
@require_feature("credit_cards")
def credit_card_list(request):
    cards = CreditCard.objects.filter(user=request.user).select_related("account")
    return render(request, "finanzas/credit_card_list.html", {"cards": cards})


@login_required
@require_feature("credit_cards")
def credit_card_create(request):
    return save_user_form(
        request,
        CreditCardForm,
        "finanzas/form.html",
        "finanzas:credit_card_list",
        "Nueva tarjeta",
        "Configura limite, deuda, tasa y fechas de pago.",
        "Guardar tarjeta",
        extra_context={
            "helper_note": "Primero crea una cuenta de tipo Tarjeta de crédito si no aparece ninguna opción.",
            "helper_url": "finanzas:account_create",
            "helper_label": "Crear cuenta de tarjeta",
        },
        after_save=lambda obj: (rebuild_account_balances(request.user, force_account_ids=[obj.account_id]), sync_credit_card_account_balance(obj)),
    )


@login_required
@require_feature("credit_cards")
def credit_card_edit(request, pk):
    instance = get_object_or_404(CreditCard, pk=pk, user=request.user)
    return save_user_form(
        request,
        CreditCardForm,
        "finanzas/form.html",
        "finanzas:credit_card_list",
        "Editar tarjeta",
        "Ajusta deuda, tasa y configuracion de pagos.",
        "Guardar cambios",
        instance=instance,
        after_save=lambda obj: (rebuild_account_balances(request.user, force_account_ids=[obj.account_id]), sync_credit_card_account_balance(obj)),
    )


@login_required
@require_http_methods(["GET", "POST"])
@require_feature("credit_cards")
def credit_card_delete(request, pk):
    instance = get_object_or_404(CreditCard, pk=pk, user=request.user)
    return confirm_delete(request, instance, "finanzas:credit_card_list", "Tarjeta")


@login_required
def reports(request):
    context = dashboard_summary(request.user)
    english = is_english(request)
    decorate_budget_rows(context.get("category_budget", []), english)
    for row in context.get("expense_breakdown", []):
        row["category_name_ui"] = localized_name(CATEGORY_NAME_LABELS, row.get("category__name"), english)
    return render(request, "finanzas/reports.html", context)


@login_required
def settings_page(request):
    english = is_english(request)
    accounts = Account.objects.filter(user=request.user).order_by("account_type", "name")
    categories = Category.objects.filter(user=request.user).order_by("category_type", "name")
    for account in accounts:
        account.account_type_label_ui = localized_label(
            ACCOUNT_TYPE_LABELS,
            account.account_type,
            english,
            account.get_account_type_display(),
        )
    for category in categories:
        category.category_type_label_ui = localized_label(
            CATEGORY_TYPE_LABELS,
            category.category_type,
            english,
            category.get_category_type_display(),
        )
    return render(request, "finanzas/settings.html", {"accounts": accounts, "categories": categories})


def _build_transaction_queryset(user, request):
    qs = FinancialTransaction.objects.filter(user=user).select_related(
        "account", "destination_account", "related_credit_card__account", "category"
    ).order_by("-date", "-id")
    query = request.GET.get("q", "").strip()
    tx_type = request.GET.get("transaction_type", "").strip()
    status = request.GET.get("status", "").strip()
    account_id = request.GET.get("account", "").strip()
    category_id = request.GET.get("category", "").strip()
    date_from = parse_iso_date(request.GET.get("date_from", "").strip())
    date_to = parse_iso_date(request.GET.get("date_to", "").strip())
    if query:
        qs = qs.filter(Q(description__icontains=query) | Q(counterparty__icontains=query) | Q(notes__icontains=query))
    if tx_type in dict(FinancialTransaction.TransactionType.choices):
        qs = qs.filter(transaction_type=tx_type)
    if status in dict(FinancialTransaction.Status.choices):
        qs = qs.filter(status=status)
    if account_id.isdigit():
        qs = qs.filter(account_id=account_id)
    if category_id.isdigit():
        qs = qs.filter(category_id=category_id)
    if date_from:
        qs = qs.filter(date__gte=date_from)
    if date_to:
        qs = qs.filter(date__lte=date_to)
    return qs


def _build_invoice_queryset(user, request):
    qs = Invoice.objects.filter(user=user).order_by("-issue_date", "-id")
    query = request.GET.get("q", "").strip()
    invoice_type = request.GET.get("invoice_type", "").strip()
    status = request.GET.get("status", "").strip()
    date_from = parse_iso_date(request.GET.get("date_from", "").strip())
    date_to = parse_iso_date(request.GET.get("date_to", "").strip())
    if query:
        qs = qs.filter(Q(number__icontains=query) | Q(counterparty__icontains=query))
    if invoice_type in dict(Invoice.InvoiceType.choices):
        qs = qs.filter(invoice_type=invoice_type)
    if status in dict(Invoice.Status.choices):
        qs = qs.filter(status=status)
    if date_from:
        qs = qs.filter(issue_date__gte=date_from)
    if date_to:
        qs = qs.filter(issue_date__lte=date_to)
    return qs


@login_required
@require_feature("exports_basic")
def export_transactions_csv(request):
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="movimientos.csv"'
    writer = csv.writer(response)
    writer.writerow(["Fecha", "Descripcion", "Tipo", "Cuenta", "Cuenta destino", "Tarjeta", "Categoria", "Monto", "Estado"])

    transactions = _build_transaction_queryset(request.user, request)[:EXPORT_ROW_LIMIT]
    for tx in transactions:
        writer.writerow(
            [
                sanitize_csv_cell(tx.date),
                sanitize_csv_cell(tx.description),
                sanitize_csv_cell(tx.get_transaction_type_display()),
                sanitize_csv_cell(tx.account.name),
                sanitize_csv_cell(tx.destination_account.name if tx.destination_account else ""),
                sanitize_csv_cell(tx.related_credit_card.account.name if tx.related_credit_card else ""),
                sanitize_csv_cell(tx.category.name if tx.category else ""),
                sanitize_csv_cell(tx.amount),
                sanitize_csv_cell(tx.get_status_display()),
            ]
        )
    return response


@login_required
@require_feature("exports_basic")
def export_invoices_csv(request):
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="facturas.csv"'
    writer = csv.writer(response)
    writer.writerow(["Numero", "Tipo", "Contacto", "Emision", "Vence", "Subtotal", "Impuesto", "Total", "Estado"])

    invoices = _build_invoice_queryset(request.user, request)[:EXPORT_ROW_LIMIT]
    for invoice in invoices:
        writer.writerow(
            [
                sanitize_csv_cell(invoice.number),
                sanitize_csv_cell(invoice.get_invoice_type_display()),
                sanitize_csv_cell(invoice.counterparty),
                sanitize_csv_cell(invoice.issue_date),
                sanitize_csv_cell(invoice.due_date),
                sanitize_csv_cell(invoice.subtotal),
                sanitize_csv_cell(invoice.tax),
                sanitize_csv_cell(invoice.total),
                sanitize_csv_cell(invoice.get_status_display()),
            ]
        )
    return response


@require_http_methods(["GET", "POST"])
def login_view(request):
    from django.contrib.auth.views import LoginView
    identity = request.POST.get("username", "") if request.method == "POST" else ""
    if request.method == "POST" and is_login_locked(request, identity):
        from django.contrib.auth.forms import AuthenticationForm
        form = AuthenticationForm()
        response = render(
            request,
            "registration/login.html",
            {
                "form": form,
                "login_locked": True,
                "error_message": "Demasiados intentos fallidos. Intenta de nuevo en 15 minutos.",
            },
            status=429,
        )
        response["Retry-After"] = str(getattr(settings, "MONETA_LOGIN_LOCKOUT_SECONDS", 900))
        return response
    return LoginView.as_view()(request)
