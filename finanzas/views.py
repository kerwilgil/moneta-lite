import csv
from datetime import date, timedelta
from decimal import Decimal

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError
from django.db.models import ProtectedError
from django.db.models import F, Q, Sum
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import translation
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils import timezone
from django.utils.translation import check_for_language
from django.views.decorators.http import require_http_methods

from .accounting import (
    delete_invoice_journal,
    delete_transaction_journal,
    rebuild_account_balances,
    sync_credit_card_account_balance,
    sync_invoice_journal,
    sync_transaction_journal,
)
from .automation import execute_due_recurrings_for_user
from .forms import (
    AccountForm,
    CategoryForm,
    CreditCardForm,
    InvoiceForm,
    InitialSuperuserForm,
    JournalEntryForm,
    JournalLineFormSet,
    RecurringPaymentForm,
    TransactionForm,
)
from .models import Account, Category, CreditCard, FinancialTransaction, Invoice, JournalEntry, JournalLine, RecurringPayment
from .product import require_feature
from .services import advice_for_user, dashboard_summary, monthly_cash_flow_series


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

EXECUTION_STATUS_LABELS = {
    RecurringPayment.ExecutionStatus.SUCCESS: {"es": "Correcto", "en": "Success"},
    RecurringPayment.ExecutionStatus.SKIPPED: {"es": "Sin cambios", "en": "No changes"},
    RecurringPayment.ExecutionStatus.ERROR: {"es": "Error", "en": "Error"},
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
        category.display_name_ui = localized_name(CATEGORY_NAME_LABELS, category.name, english)
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
    response.set_cookie(settings.LANGUAGE_COOKIE_NAME, language)

    if language.startswith("en"):
        messages.success(request, "Language switched to English.")
    else:
        messages.success(request, "Idioma cambiado a Español.")
    return response


@require_http_methods(["GET", "POST"])
def initial_setup(request):
    User = get_user_model()
    if User.objects.exists():
        messages.info(request, "La configuracion inicial ya fue completada.")
        return redirect("login")

    if request.method == "POST":
        form = InitialSuperuserForm(request.POST)
        if form.is_valid():
            user = User.objects.create_superuser(
                username=form.cleaned_data["username"],
                email=form.cleaned_data.get("email", ""),
                password=form.cleaned_data["password"],
            )
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


def monthly_frequency_factor(frequency):
    factors = {
        RecurringPayment.Frequency.WEEKLY: Decimal("4.00"),
        RecurringPayment.Frequency.BIWEEKLY: Decimal("2.00"),
        RecurringPayment.Frequency.MONTHLY: Decimal("1.00"),
        RecurringPayment.Frequency.QUARTERLY: Decimal("0.3333"),
        RecurringPayment.Frequency.YEARLY: Decimal("0.0833"),
    }
    return factors.get(frequency, Decimal("1.00"))


def recurring_overview(queryset):
    today = timezone.localdate()
    limit = today + timedelta(days=30)
    monthly_projection = Decimal("0.00")
    due_next_30 = Decimal("0.00")
    active_count = 0

    rows = queryset.values_list("amount", "frequency", "next_due_date", "is_active")
    for amount, frequency, next_due_date, is_active in rows:
        amount = amount or Decimal("0.00")
        monthly_projection += amount * monthly_frequency_factor(frequency)
        if is_active:
            active_count += 1
            if next_due_date and today <= next_due_date <= limit:
                due_next_30 += amount

    return {
        "monthly_projection": monthly_projection.quantize(Decimal("0.01")),
        "due_next_30": due_next_30.quantize(Decimal("0.01")),
        "active_count": active_count,
    }


def subscription_icon(service_name):
    text = (service_name or "").lower()
    icon_map = {
        "spotify": "\U0001F3A7",
        "youtube": "\u25B6\uFE0F",
        "netflix": "\U0001F3AC",
        "hbo": "\U0001F39E\uFE0F",
        "disney": "\U0001F3F0",
        "instagram": "\U0001F4F8",
        "apple music": "\U0001F3B5",
        "prime": "\U0001F4E6",
        "salud": "\U0001F3E5",
        "seguro": "\U0001F6E1\uFE0F",
        "vida": "\U0001F49F",
    }
    for key, icon in icon_map.items():
        if key in text:
            return icon
    return "\U0001F4CC"


SUBSCRIPTION_PRESETS = [
    {
        "key": "spotify",
        "name": "Spotify Premium",
        "logo_static": "img/services/spotify.svg",
        "default_amount": Decimal("6.99"),
    },
    {
        "key": "youtube",
        "name": "YouTube Premium",
        "logo_static": "img/services/youtube.svg",
        "default_amount": Decimal("11.99"),
    },
    {
        "key": "netflix",
        "name": "Netflix",
        "logo_static": "img/services/netflix.svg",
        "default_amount": Decimal("12.99"),
    },
    {
        "key": "hbo",
        "name": "Max",
        "logo_url": "https://cdn.simpleicons.org/max/0046FE",
        "default_amount": Decimal("9.99"),
    },
    {
        "key": "disney",
        "name": "Disney+",
        "logo_static": "img/services/disneyplus_v2.png",
        "default_amount": Decimal("8.99"),
    },
    {
        "key": "prime",
        "name": "Prime Video",
        "logo_static": "img/services/primevideo_v2.png",
        "default_amount": Decimal("5.99"),
    },
    {
        "key": "paramount",
        "name": "Paramount+",
        "logo_url": "https://cdn.simpleicons.org/paramountplus/0064FF",
        "default_amount": Decimal("7.99"),
    },
    {
        "key": "appletv",
        "name": "Apple TV+",
        "logo_url": "https://cdn.simpleicons.org/appletv/000000",
        "default_amount": Decimal("6.99"),
    },
    {
        "key": "crunchyroll",
        "name": "Crunchyroll",
        "logo_url": "https://cdn.simpleicons.org/crunchyroll/F47521",
        "default_amount": Decimal("9.99"),
    },
    {
        "key": "gamepass",
        "name": "Xbox Game Pass",
        "logo_static": "img/services/xbox.svg",
        "default_amount": Decimal("10.99"),
    },
    {
        "key": "psplus",
        "name": "PlayStation Plus",
        "logo_url": "https://cdn.simpleicons.org/playstation/003791",
        "default_amount": Decimal("9.99"),
    },
    {
        "key": "googleone",
        "name": "Google One",
        "logo_static": "img/services/googleone.svg",
        "default_amount": Decimal("1.99"),
    },
    {
        "key": "icloud",
        "name": "iCloud+",
        "logo_url": "https://cdn.simpleicons.org/icloud/3693F3",
        "default_amount": Decimal("2.99"),
    },
    {
        "key": "dropbox",
        "name": "Dropbox",
        "logo_url": "https://cdn.simpleicons.org/dropbox/0061FF",
        "default_amount": Decimal("11.99"),
    },
    {
        "key": "chatgpt",
        "name": "ChatGPT Plus",
        "logo_static": "img/services/chatgpt.svg",
        "default_amount": Decimal("20.00"),
    },
    {
        "key": "claude",
        "name": "Claude Pro",
        "logo_url": "https://cdn.simpleicons.org/anthropic/111827",
        "default_amount": Decimal("20.00"),
    },
    {
        "key": "canva",
        "name": "Canva Pro",
        "logo_static": "img/services/canva.svg",
        "default_amount": Decimal("12.99"),
    },
    {
        "key": "notion",
        "name": "Notion Plus",
        "logo_url": "https://cdn.simpleicons.org/notion/000000",
        "default_amount": Decimal("10.00"),
    },
    {
        "key": "adobe",
        "name": "Adobe Creative Cloud",
        "logo_static": "img/services/adobe.svg",
        "default_amount": Decimal("54.99"),
    },
    {
        "key": "uberone",
        "name": "Uber One",
        "logo_url": "https://cdn.simpleicons.org/uber/000000",
        "default_amount": Decimal("9.99"),
    },
    {
        "key": "segurovida",
        "name": "Seguro de vida privado",
        "default_amount": Decimal("0.00"),
        "category_name": "Seguros",
        "catalog": "insurance",
    },
    {
        "key": "segurosalud",
        "name": "Seguro de salud privado",
        "default_amount": Decimal("0.00"),
        "category_name": "Seguros",
        "catalog": "insurance",
    },
    {
        "key": "seguroingreso",
        "name": "Seguro de ingreso",
        "default_amount": Decimal("0.00"),
        "category_name": "Seguros",
        "catalog": "insurance",
    },
]


def subscription_preset_map():
    return {preset["key"]: preset for preset in SUBSCRIPTION_PRESETS}


def is_lite_edition():
    return getattr(settings, "APP_EDITION", "demo") == "lite"


def insurance_presets():
    return [preset for preset in SUBSCRIPTION_PRESETS if preset.get("catalog") == "insurance"]


def service_subscription_presets():
    return [preset for preset in SUBSCRIPTION_PRESETS if preset.get("catalog") != "insurance"]


def subscription_preset_initial(preset_key, user=None):
    preset = subscription_preset_map().get(preset_key)
    if not preset:
        return None
    initial = {
        "name": preset["name"],
        "amount": preset.get("default_amount", Decimal("0.00")),
        "frequency": RecurringPayment.Frequency.MONTHLY,
        "next_due_date": timezone.localdate(),
        "auto_create_transaction": True,
        "is_active": True,
    }
    category_name = preset.get("category_name")
    if user and category_name:
        category = Category.objects.filter(user=user, name__iexact=category_name).first()
        if category:
            initial["category"] = category
    return initial


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
    if request.method == "POST":
        form = form_class(request.POST, user=request.user, instance=instance)
        if form.is_valid():
            try:
                obj = form.save(commit=False)
                if instance_mutator:
                    instance_mutator(obj)
                if hasattr(obj, "user_id"):
                    obj.user = request.user
                obj.save()
                form.save_m2m()
                if after_save:
                    after_save(obj)
                messages.success(request, "Registro guardado correctamente.")
                return redirect(success_url)
            except IntegrityError:
                form.add_error(None, "No se pudo guardar porque ya existe un registro con esos datos unicos.")
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
    context["advice"] = advice_for_user(request.user)
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


@login_required
def transaction_list(request):
    english = is_english(request)
    base_queryset = FinancialTransaction.objects.filter(user=request.user).select_related(
        "account",
        "category",
        "destination_account",
        "related_credit_card__account",
    ).order_by("-date", "-id")

    query = request.GET.get("q", "").strip()
    tx_type = request.GET.get("transaction_type", "").strip()
    status = request.GET.get("status", "").strip()
    account_id = request.GET.get("account", "").strip()
    category_id = request.GET.get("category", "").strip()
    date_from = parse_iso_date(request.GET.get("date_from", "").strip())
    date_to = parse_iso_date(request.GET.get("date_to", "").strip())

    if query:
        base_queryset = base_queryset.filter(
            Q(description__icontains=query) | Q(counterparty__icontains=query) | Q(notes__icontains=query)
        )
    if tx_type in dict(FinancialTransaction.TransactionType.choices):
        base_queryset = base_queryset.filter(transaction_type=tx_type)
    if status in dict(FinancialTransaction.Status.choices):
        base_queryset = base_queryset.filter(status=status)
    if account_id.isdigit():
        base_queryset = base_queryset.filter(account_id=account_id)
    if category_id.isdigit():
        base_queryset = base_queryset.filter(category_id=category_id)
    if date_from:
        base_queryset = base_queryset.filter(date__gte=date_from)
    if date_to:
        base_queryset = base_queryset.filter(date__lte=date_to)

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
    transactions = list(base_queryset[:200])
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

    return render(
        request,
        "finanzas/transaction_list.html",
        {
            "transactions": transactions,
            "type_choices": localized_choices(FinancialTransaction.TransactionType.choices, TX_TYPE_LABELS, english),
            "status_choices": localized_choices(FinancialTransaction.Status.choices, TX_STATUS_LABELS, english),
            "accounts": Account.objects.filter(user=request.user, is_active=True).order_by("name"),
            "categories": Category.objects.filter(user=request.user).order_by("name"),
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
        after_save=lambda obj: (sync_transaction_journal(obj), rebuild_account_balances(request.user)),
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
        after_save=lambda obj: (sync_credit_card_account_balance(obj), rebuild_account_balances(request.user)),
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
        after_save=lambda obj: (sync_credit_card_account_balance(obj), rebuild_account_balances(request.user)),
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
    from .models import Category  # local import to keep top imports focused

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
    from .models import Category

    instance = get_object_or_404(Category, pk=pk, user=request.user)
    return confirm_delete(request, instance, "finanzas:settings", "Categoría")


@login_required
def invoice_list(request):
    english = is_english(request)
    queryset = Invoice.objects.filter(user=request.user).select_related("journal_entry").order_by("-issue_date", "-id")
    query = request.GET.get("q", "").strip()
    invoice_type = request.GET.get("invoice_type", "").strip()
    status = request.GET.get("status", "").strip()
    date_from = parse_iso_date(request.GET.get("date_from", "").strip())
    date_to = parse_iso_date(request.GET.get("date_to", "").strip())

    if query:
        queryset = queryset.filter(Q(number__icontains=query) | Q(counterparty__icontains=query))
    if invoice_type in dict(Invoice.InvoiceType.choices):
        queryset = queryset.filter(invoice_type=invoice_type)
    if status in dict(Invoice.Status.choices):
        queryset = queryset.filter(status=status)
    if date_from:
        queryset = queryset.filter(issue_date__gte=date_from)
    if date_to:
        queryset = queryset.filter(issue_date__lte=date_to)

    totals = queryset.annotate(total_amount=F("subtotal") + F("tax")).aggregate(
        total=Sum("total_amount"),
        pending=Sum("total_amount", filter=Q(status=Invoice.Status.PENDING)),
        paid=Sum("total_amount", filter=Q(status=Invoice.Status.PAID)),
        overdue=Sum("total_amount", filter=Q(status=Invoice.Status.OVERDUE)),
    )
    invoices = list(queryset[:200])
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
@require_feature("recurring")
def recurring_list(request):
    english = is_english(request)
    queryset = (
        RecurringPayment.objects.filter(user=request.user, is_subscription=False)
        .select_related("account", "category")
        .order_by("next_due_date", "name")
    )
    active_filter = request.GET.get("active", "all")
    if active_filter == "active":
        queryset = queryset.filter(is_active=True)
    elif active_filter == "inactive":
        queryset = queryset.filter(is_active=False)

    overview = recurring_overview(queryset)
    payments = list(queryset[:200])
    for payment in payments:
        payment.frequency_label_ui = localized_label(
            FREQUENCY_LABELS,
            payment.frequency,
            english,
            payment.get_frequency_display(),
        )
        payment.execution_status_label_ui = localized_label(
            EXECUTION_STATUS_LABELS,
            payment.last_execution_status,
            english,
            payment.get_last_execution_status_display() if payment.last_execution_status else "",
        )
        payment.active_label_ui = "Active" if english else "Activo"
        payment.inactive_label_ui = "Inactive" if english else "Inactivo"

    return render(
        request,
        "finanzas/recurring_list.html",
        {
            "payments": payments,
            "filters": {"active": active_filter},
            "summary_monthly_projection": overview["monthly_projection"],
            "summary_due_next_30": overview["due_next_30"],
            "summary_active_count": overview["active_count"],
        },
    )


@login_required
@require_feature("recurring")
def recurring_create(request):
    return save_user_form(
        request,
        RecurringPaymentForm,
        "finanzas/form.html",
        "finanzas:recurring_list",
        "Nuevo pago recurrente",
        "Programa obligaciones fijas y pagos periodicos.",
        "Guardar recurrente",
        extra_context=category_helper_context(),
        instance_mutator=lambda obj: setattr(obj, "is_subscription", False),
    )


@login_required
@require_feature("recurring")
def recurring_edit(request, pk):
    instance = get_object_or_404(RecurringPayment, pk=pk, user=request.user, is_subscription=False)
    return save_user_form(
        request,
        RecurringPaymentForm,
        "finanzas/form.html",
        "finanzas:recurring_list",
        "Editar pago recurrente",
        "Actualiza monto, frecuencia o estado.",
        "Guardar cambios",
        instance=instance,
        extra_context=category_helper_context(),
        instance_mutator=lambda obj: setattr(obj, "is_subscription", False),
    )


@login_required
@require_http_methods(["GET", "POST"])
@require_feature("recurring")
def recurring_delete(request, pk):
    instance = get_object_or_404(RecurringPayment, pk=pk, user=request.user, is_subscription=False)
    return confirm_delete(request, instance, "finanzas:recurring_list", "Pago recurrente")


@login_required
@require_http_methods(["POST"])
@require_feature("recurring")
def recurring_run_now(request):
    stats = execute_due_recurrings_for_user(request.user, is_subscription=False)
    messages.success(
        request,
        (
            f"Ejecucion recurrentes: procesados {stats['processed']}, "
            f"creados {stats['created_transactions']}, omitidos {stats['skipped_transactions']}, "
            f"errores {stats['errors']}."
        ),
    )
    return redirect("finanzas:recurring_list")


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
    subscriptions = queryset[:200]
    preset_map = subscription_preset_map()
    subscription_rows = []
    for subscription in subscriptions:
        icon = subscription_icon(subscription.name)
        logo_static = None
        logo_url = None
        text = (subscription.name or "").lower()
        for key, preset in preset_map.items():
            if key in text:
                logo_static = preset.get("logo_static")
                logo_url = preset.get("logo_url")
                break
        subscription.frequency_label_ui = localized_label(
            FREQUENCY_LABELS,
            subscription.frequency,
            english,
            subscription.get_frequency_display(),
        )
        subscription.execution_status_label_ui = localized_label(
            EXECUTION_STATUS_LABELS,
            subscription.last_execution_status,
            english,
            subscription.get_last_execution_status_display() if subscription.last_execution_status else "",
        )
        subscription.active_label_ui = "Active" if english else "Activa"
        subscription.inactive_label_ui = "Inactive" if english else "Inactiva"

        subscription_rows.append(
            {
                "item": subscription,
                "icon": icon,
                "logo_static": logo_static,
                "logo_url": logo_url,
            }
        )

    return render(
        request,
        "finanzas/subscription_list.html",
        {
            "subscription_rows": subscription_rows,
            "subscription_presets": sorted(
                [] if is_lite_edition() else service_subscription_presets(),
                key=lambda p: p["name"].lower(),
            ),
            "insurance_presets": insurance_presets(),
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
    if is_lite_edition() and preset_key not in {preset["key"] for preset in insurance_presets()}:
        messages.info(request, "Moneta Lite permite agregar suscripciones solo desde Seguros privados.")
        return redirect("finanzas:subscription_list")
    initial_data = subscription_preset_initial(preset_key, request.user)
    return save_user_form(
        request,
        RecurringPaymentForm,
        "finanzas/form.html",
        "finanzas:subscription_list",
        "Nueva suscripción",
        "Registra servicios, afiliaciones y cargos automaticos.",
        "Guardar suscripción",
        extra_context=category_helper_context(),
        instance_mutator=lambda obj: setattr(obj, "is_subscription", True),
        initial_data=initial_data,
    )


@login_required
@require_feature("subscriptions")
def subscription_edit(request, pk):
    instance = get_object_or_404(RecurringPayment, pk=pk, user=request.user, is_subscription=True)
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
        instance_mutator=lambda obj: setattr(obj, "is_subscription", True),
    )


@login_required
@require_http_methods(["GET", "POST"])
@require_feature("subscriptions")
def subscription_delete(request, pk):
    instance = get_object_or_404(RecurringPayment, pk=pk, user=request.user, is_subscription=True)
    return confirm_delete(request, instance, "finanzas:subscription_list", "Suscripcion")


@login_required
@require_http_methods(["POST"])
@require_feature("subscriptions")
def subscription_run_now(request):
    stats = execute_due_recurrings_for_user(request.user, is_subscription=True)
    messages.success(
        request,
        (
            f"Ejecución suscripciones: procesados {stats['processed']}, "
            f"creados {stats['created_transactions']}, omitidos {stats['skipped_transactions']}, "
            f"errores {stats['errors']}."
        ),
    )
    return redirect("finanzas:subscription_list")


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
        after_save=lambda obj: (rebuild_account_balances(request.user), sync_credit_card_account_balance(obj)),
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
        after_save=lambda obj: (rebuild_account_balances(request.user), sync_credit_card_account_balance(obj)),
    )


@login_required
@require_http_methods(["GET", "POST"])
@require_feature("credit_cards")
def credit_card_delete(request, pk):
    instance = get_object_or_404(CreditCard, pk=pk, user=request.user)
    return confirm_delete(request, instance, "finanzas:credit_card_list", "Tarjeta")


@login_required
@require_feature("ledger")
def ledger(request):
    entries = JournalEntry.objects.filter(user=request.user).prefetch_related("lines__account")[:80]
    return render(request, "finanzas/ledger.html", {"entries": entries})


@login_required
@require_feature("ledger")
def ledger_create(request):
    if request.method == "POST":
        form = JournalEntryForm(request.POST, user=request.user)
        formset = JournalLineFormSet(request.POST, form_kwargs={"user": request.user})
        if form.is_valid() and formset.is_valid():
            lines = [line_form.cleaned_data for line_form in formset if not line_form.is_empty()]
            debit_total = sum((line.get("debit") or Decimal("0.00")) for line in lines)
            credit_total = sum((line.get("credit") or Decimal("0.00")) for line in lines)
            if len(lines) < 2:
                messages.error(request, "El asiento necesita al menos dos lineas.")
            elif debit_total != credit_total:
                messages.error(request, "El asiento no esta balanceado: Debe y Haber deben ser iguales.")
            else:
                entry = form.save(commit=False)
                entry.user = request.user
                entry.save()
                for line in lines:
                    JournalLine.objects.create(
                        entry=entry,
                        account=line["account"],
                        memo=line.get("memo", ""),
                        debit=line.get("debit") or Decimal("0.00"),
                        credit=line.get("credit") or Decimal("0.00"),
                    )
                messages.success(request, "Asiento contable guardado correctamente.")
                return redirect("finanzas:ledger")
    else:
        form = JournalEntryForm(user=request.user)
        formset = JournalLineFormSet(form_kwargs={"user": request.user})

    return render(
        request,
        "finanzas/journal_entry_form.html",
        {
            "form": form,
            "formset": formset,
            "title": "Nuevo asiento contable",
            "subtitle": "Registra lineas Debe/Haber. El total Debe debe ser igual al total Haber.",
            "cancel_url": "finanzas:ledger",
        },
    )


@login_required
def reports(request):
    context = dashboard_summary(request.user)
    english = is_english(request)
    decorate_budget_rows(context.get("category_budget", []), english)
    for row in context.get("expense_breakdown", []):
        row["category_name_ui"] = localized_name(CATEGORY_NAME_LABELS, row.get("category__name"), english)
    return render(request, "finanzas/reports.html", context)


@login_required
def showcase_page(request):
    english = is_english(request)
    context = dashboard_summary(request.user)
    context["advice"] = advice_for_user(request.user)
    context["cash_flow_series"] = monthly_cash_flow_series(request.user, english=english)
    context["showcase_features"] = [
        {
            "eyebrow": "Control",
            "title": "Cash flow visible at a glance." if english else "Flujo de caja visible de inmediato.",
            "body": "Income, expenses, cards and upcoming commitments in one operating view."
            if english
            else "Ingresos, gastos, tarjetas y compromisos próximos en una sola vista operativa.",
        },
        {
            "eyebrow": "Order",
            "title": "Accounting and personal finance aligned." if english else "Contabilidad y finanzas personales alineadas.",
            "body": "Transactions, invoices and ledger entries stay connected without duplicating effort."
            if english
            else "Movimientos, facturas y asientos contables conectados sin duplicar trabajo.",
        },
        {
            "eyebrow": "Focus",
            "title": "A calmer way to review recurring spend." if english else "Una forma más clara de revisar gasto recurrente.",
            "body": "Subscriptions, debt pressure and budget alerts in a cleaner visual layer."
            if english
            else "Suscripciones, presión de deuda y alertas de presupuesto en una capa visual más limpia.",
        },
    ]

    for account in context.get("accounts", []):
        decorate_account(account, english)
    for card in context.get("credit_cards", []):
        decorate_account(card.account, english)
    decorate_budget_rows(context.get("category_budget", []), english)
    for transaction in context.get("recent_transactions", []):
        decorate_account(transaction.account, english)
        decorate_category(transaction.category, english)
        transaction.status_label_ui = localized_label(
            TX_STATUS_LABELS,
            transaction.status,
            english,
            transaction.get_status_display(),
        )
        transaction.transaction_type_label_ui = localized_label(
            TX_TYPE_LABELS,
            transaction.transaction_type,
            english,
            transaction.get_transaction_type_display(),
        )

    context["showcase_subscriptions"] = list(
        RecurringPayment.objects.filter(user=request.user, is_subscription=True, is_active=True)
        .select_related("account", "category")
        .order_by("next_due_date", "name")[:4]
    )
    for subscription in context["showcase_subscriptions"]:
        decorate_account(subscription.account, english)
        decorate_category(subscription.category, english)
        subscription.frequency_label_ui = localized_label(
            FREQUENCY_LABELS,
            subscription.frequency,
            english,
            subscription.get_frequency_display(),
        )

    return render(request, "finanzas/showcase.html", context)


@login_required
@require_feature("net_income")
def net_income(request):
    context = dashboard_summary(request.user)
    return render(request, "finanzas/net_income.html", context)


@login_required
def settings_page(request):
    from .models import Category

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


@login_required
@require_feature("exports_basic")
def export_transactions_csv(request):
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="movimientos.csv"'
    writer = csv.writer(response)
    writer.writerow(["Fecha", "Descripcion", "Tipo", "Cuenta", "Cuenta destino", "Tarjeta", "Categoria", "Monto", "Estado"])

    transactions = FinancialTransaction.objects.filter(user=request.user).select_related(
        "account",
        "destination_account",
        "related_credit_card__account",
        "category",
    )
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

    invoices = Invoice.objects.filter(user=request.user).order_by("-issue_date", "-id")
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


@login_required
@require_feature("exports_advanced")
def export_recurring_csv(request):
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="recurrentes.csv"'
    writer = csv.writer(response)
    writer.writerow(["Nombre", "Cuenta", "Categoria", "Frecuencia", "Proximo pago", "Monto", "Activo"])

    payments = (
        RecurringPayment.objects.filter(user=request.user, is_subscription=False)
        .select_related("account", "category")
        .order_by("next_due_date", "name")
    )
    for payment in payments:
        writer.writerow(
            [
                sanitize_csv_cell(payment.name),
                sanitize_csv_cell(payment.account.name),
                sanitize_csv_cell(payment.category.name if payment.category else ""),
                sanitize_csv_cell(payment.get_frequency_display()),
                sanitize_csv_cell(payment.next_due_date),
                sanitize_csv_cell(payment.amount),
                sanitize_csv_cell("Si" if payment.is_active else "No"),
            ]
        )
    return response


@login_required
@require_feature("exports_advanced")
def export_subscriptions_csv(request):
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="suscripciones.csv"'
    writer = csv.writer(response)
    writer.writerow(["Servicio", "Metodo", "Categoria", "Frecuencia", "Proximo cobro", "Monto", "Activa"])

    subscriptions = (
        RecurringPayment.objects.filter(user=request.user, is_subscription=True)
        .select_related("account", "category")
        .order_by("next_due_date", "name")
    )
    for subscription in subscriptions:
        writer.writerow(
            [
                sanitize_csv_cell(subscription.name),
                sanitize_csv_cell(subscription.account.name),
                sanitize_csv_cell(subscription.category.name if subscription.category else ""),
                sanitize_csv_cell(subscription.get_frequency_display()),
                sanitize_csv_cell(subscription.next_due_date),
                sanitize_csv_cell(subscription.amount),
                sanitize_csv_cell("Si" if subscription.is_active else "No"),
            ]
        )
    return response
