from datetime import date
from decimal import Decimal

from django.db.models import Sum
from django.utils import timezone

from .models import Account, Category, CreditCard, FinancialTransaction, RecurringPayment


def money_total(queryset, field="amount"):
    return queryset.aggregate(total=Sum(field))["total"] or Decimal("0.00")


def credit_card_debt_total(user):
    return money_total(CreditCard.objects.filter(user=user), "current_debt")


def _month_start(base_date):
    return base_date.replace(day=1)


def _add_months(base_date, months):
    month_index = base_date.month - 1 + months
    year = base_date.year + month_index // 12
    month = month_index % 12 + 1
    return date(year, month, 1)


def _month_label(base_date, english=False):
    labels = {
        1: ("Ene", "Jan"),
        2: ("Feb", "Feb"),
        3: ("Mar", "Mar"),
        4: ("Abr", "Apr"),
        5: ("May", "May"),
        6: ("Jun", "Jun"),
        7: ("Jul", "Jul"),
        8: ("Ago", "Aug"),
        9: ("Sep", "Sep"),
        10: ("Oct", "Oct"),
        11: ("Nov", "Nov"),
        12: ("Dic", "Dec"),
    }
    es_label, en_label = labels[base_date.month]
    return en_label if english else es_label


def monthly_cash_flow_series(user, months=7, english=False):
    today = timezone.localdate()
    current_month = _month_start(today)
    month_starts = [_add_months(current_month, offset) for offset in range(-(months - 1), 1)]
    labels = [_month_label(month_start, english) for month_start in month_starts]
    values = []

    for month_start in month_starts:
        month_transactions = FinancialTransaction.objects.filter(
            user=user,
            date__year=month_start.year,
            date__month=month_start.month,
            status=FinancialTransaction.Status.CLEARED,
        )
        income = money_total(
            month_transactions.filter(
                transaction_type__in=[
                    FinancialTransaction.TransactionType.INCOME,
                    FinancialTransaction.TransactionType.COLLECTION,
                ]
            )
        )
        expenses = money_total(
            month_transactions.filter(transaction_type=FinancialTransaction.TransactionType.EXPENSE)
        )
        card_payments = money_total(
            month_transactions.filter(transaction_type=FinancialTransaction.TransactionType.CARD_PAYMENT)
        )
        values.append(float((income - expenses - card_payments).quantize(Decimal("0.01"))))

    return {"labels": labels, "values": values}


def category_budget_overview(user, today):
    month_expenses = FinancialTransaction.objects.filter(
        user=user,
        date__year=today.year,
        date__month=today.month,
        status=FinancialTransaction.Status.CLEARED,
        transaction_type=FinancialTransaction.TransactionType.EXPENSE,
        category__isnull=False,
    )
    spent_by_category = {
        row["category_id"]: row["total"] or Decimal("0.00")
        for row in month_expenses.values("category_id").annotate(total=Sum("amount"))
    }

    budget_rows = []
    for category in Category.objects.filter(
        user=user,
        category_type=Category.CategoryType.EXPENSE,
        monthly_limit__isnull=False,
    ).order_by("name"):
        limit = category.monthly_limit or Decimal("0.00")
        spent = spent_by_category.get(category.id, Decimal("0.00"))
        usage_percent = (
            ((spent / limit) * Decimal("100")).quantize(Decimal("0.01"))
            if limit > 0
            else Decimal("0.00")
        )
        remaining = (limit - spent).quantize(Decimal("0.01"))
        if spent > limit:
            status = "over"
        elif usage_percent >= Decimal("80.00"):
            status = "warning"
        else:
            status = "ok"
        budget_rows.append(
            {
                "category": category,
                "spent": spent.quantize(Decimal("0.01")),
                "limit": limit.quantize(Decimal("0.01")),
                "remaining": remaining,
                "usage_percent": usage_percent,
                "status": status,
            }
        )

    budget_rows.sort(key=lambda row: row["usage_percent"], reverse=True)
    return budget_rows


def dashboard_summary(user):
    today = timezone.localdate()
    month_transactions = FinancialTransaction.objects.filter(
        user=user,
        date__year=today.year,
        date__month=today.month,
        status=FinancialTransaction.Status.CLEARED,
    )

    income = money_total(
        month_transactions.filter(
            transaction_type__in=[
                FinancialTransaction.TransactionType.INCOME,
                FinancialTransaction.TransactionType.COLLECTION,
            ]
        )
    )
    expenses = money_total(month_transactions.filter(transaction_type=FinancialTransaction.TransactionType.EXPENSE))
    card_payments = money_total(month_transactions.filter(transaction_type=FinancialTransaction.TransactionType.CARD_PAYMENT))

    assets = money_total(
        Account.objects.filter(
            user=user,
            is_active=True,
            account_type__in=[
                Account.AccountType.CASH,
                Account.AccountType.CHECKING,
                Account.AccountType.BANK,
                Account.AccountType.SAVINGS,
                Account.AccountType.INVESTMENT,
                Account.AccountType.RECEIVABLE,
            ],
        ),
        "current_balance",
    )
    account_liabilities = money_total(
        Account.objects.filter(
            user=user,
            is_active=True,
            account_type__in=[
                Account.AccountType.LOAN,
                Account.AccountType.PAYABLE,
            ],
        ),
        "current_balance",
    )
    liabilities = account_liabilities + credit_card_debt_total(user)

    upcoming = (
        RecurringPayment.objects.filter(user=user, is_active=True, next_due_date__gte=today)
        .select_related("account", "category")
        .order_by("next_due_date", "name")[:6]
    )
    credit_cards = CreditCard.objects.filter(user=user).select_related("account")
    recent_transactions = (
        FinancialTransaction.objects.filter(user=user)
        .select_related("account", "category")
        .order_by("-date", "-id")[:8]
    )
    category_budget = category_budget_overview(user, today)
    expense_breakdown = (
        month_transactions.filter(transaction_type=FinancialTransaction.TransactionType.EXPENSE, category__isnull=False)
        .values("category__name")
        .annotate(total=Sum("amount"))
        .order_by("-total")[:8]
    )
    categories_over_limit = [row for row in category_budget if row["status"] == "over"]
    categories_warning = [row for row in category_budget if row["status"] == "warning"]

    return {
        "assets": assets,
        "liabilities": liabilities,
        "capital": assets - liabilities,
        "income": income,
        "expenses": expenses,
        "card_payments": card_payments,
        "cash_flow": income - expenses - card_payments,
        "upcoming": upcoming,
        "credit_cards": credit_cards,
        "recent_transactions": recent_transactions,
        "accounts": Account.objects.filter(user=user, is_active=True).order_by("account_type", "name")[:8],
        "category_budget": category_budget,
        "categories_over_limit": categories_over_limit,
        "categories_warning": categories_warning,
        "expense_breakdown": expense_breakdown,
    }


def advice_for_user(user):
    summary = dashboard_summary(user)
    advice = []

    if summary["expenses"] > summary["income"] and summary["income"]:
        advice.append(
            {
                "title": "Flujo de caja negativo",
                "message": "Tus gastos del mes superan tus ingresos. Revisa consumos variables y pagos recurrentes antes de asumir nuevas deudas.",
            }
        )

    for card in summary["credit_cards"]:
        if card.utilization_percent >= Decimal("70.00"):
            advice.append(
                {
                    "title": f"Uso alto en {card.account.name}",
                    "message": "La tarjeta supera el 70% del límite. Prioriza pagos sobre el mínimo para reducir intereses y liberar capacidad.",
                }
            )
        elif card.utilization_percent >= Decimal("50.00"):
            advice.append(
                {
                    "title": f"Vigila {card.account.name}",
                    "message": "La utilización está por encima de 50%. Un plan de pagos fijo ayuda a evitar que el interés consuma tu flujo.",
                }
            )

    subscriptions = RecurringPayment.objects.filter(user=user, is_active=True, is_subscription=True)
    subscription_total = money_total(subscriptions)
    if subscription_total and summary["expenses"] and subscription_total / summary["expenses"] >= Decimal("0.15"):
        advice.append(
            {
                "title": "Suscripciones elevadas",
                "message": "Las suscripciones pesan mucho dentro de tus gastos. Cancela lo que no uses y anualiza solo servicios indispensables.",
            }
        )

    for row in summary["categories_over_limit"][:2]:
        advice.append(
            {
                "title": f"Presupuesto excedido en {row['category'].name}",
                "message": "Superaste el límite mensual de esta categoría. Reduce consumos variables para no comprometer flujo y capital.",
            }
        )

    for row in summary["categories_warning"][:1]:
        advice.append(
            {
                "title": f"Categoría en zona de alerta: {row['category'].name}",
                "message": "Ya consumiste más del 80% del presupuesto mensual. Planifica el resto del mes para evitar sobrepasarte.",
            }
        )

    if not advice:
        advice.append(
            {
                "title": "Mantén la disciplina",
                "message": "Tu flujo no muestra alertas críticas. Sigue midiendo patrimonio, deuda y gastos recurrentes cada semana.",
            }
        )

    return advice[:4]
