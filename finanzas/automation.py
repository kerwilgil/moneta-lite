import calendar
from datetime import date, timedelta

from django.db import transaction
from django.utils import timezone

from .accounting import rebuild_account_balances, sync_transaction_journal
from .models import FinancialTransaction, RecurringPayment


def add_months(base_date, months):
    month_index = base_date.month - 1 + months
    year = base_date.year + month_index // 12
    month = month_index % 12 + 1
    last_day = calendar.monthrange(year, month)[1]
    day = min(base_date.day, last_day)
    return date(year, month, day)


def next_due_date(current_due_date, frequency):
    if frequency == RecurringPayment.Frequency.WEEKLY:
        return current_due_date + timedelta(days=7)
    if frequency == RecurringPayment.Frequency.BIWEEKLY:
        return current_due_date + timedelta(days=14)
    if frequency == RecurringPayment.Frequency.MONTHLY:
        return add_months(current_due_date, 1)
    if frequency == RecurringPayment.Frequency.QUARTERLY:
        return add_months(current_due_date, 3)
    if frequency == RecurringPayment.Frequency.YEARLY:
        return add_months(current_due_date, 12)
    return current_due_date + timedelta(days=30)


def _create_auto_transaction(recurring, due_date):
    tx = FinancialTransaction.objects.create(
        user=recurring.user,
        account=recurring.account,
        source_recurring=recurring,
        category=recurring.category,
        transaction_type=FinancialTransaction.TransactionType.EXPENSE,
        description=f"Auto recurrente: {recurring.name}",
        counterparty=recurring.name,
        amount=recurring.amount,
        date=due_date,
        status=FinancialTransaction.Status.CLEARED,
        notes=f"Generado automaticamente desde recurrente ID {recurring.id}.",
    )
    sync_transaction_journal(tx)
    return tx


def _process_single_recurring(recurring, run_date, max_cycles=24):
    created_count = 0
    skipped_count = 0
    cycles = 0

    with transaction.atomic():
        while recurring.next_due_date <= run_date and cycles < max_cycles:
            due_date = recurring.next_due_date
            already_exists = FinancialTransaction.objects.filter(
                user=recurring.user,
                source_recurring=recurring,
                date=due_date,
            ).exclude(status=FinancialTransaction.Status.VOID).exists()

            if already_exists:
                skipped_count += 1
            else:
                _create_auto_transaction(recurring, due_date)
                created_count += 1

            recurring.next_due_date = next_due_date(due_date, recurring.frequency)
            cycles += 1

        recurring.last_execution_at = timezone.now()
        if cycles >= max_cycles and recurring.next_due_date <= run_date:
            recurring.last_execution_status = RecurringPayment.ExecutionStatus.ERROR
            recurring.last_execution_message = "Se alcanzo el limite de ciclos. Revisa frecuencia/fechas."
        elif created_count > 0:
            recurring.last_execution_status = RecurringPayment.ExecutionStatus.SUCCESS
            recurring.last_execution_message = f"Generados {created_count} movimiento(s)."
        else:
            recurring.last_execution_status = RecurringPayment.ExecutionStatus.SKIPPED
            recurring.last_execution_message = "Sin cambios, ya estaba al dia."

        recurring.save(
            update_fields=[
                "next_due_date",
                "last_execution_at",
                "last_execution_status",
                "last_execution_message",
                "updated_at",
            ]
        )

    return {"created": created_count, "skipped": skipped_count, "errored": 0}


def execute_due_recurrings_for_user(user, run_date=None, is_subscription=None):
    run_date = run_date or timezone.localdate()
    queryset = RecurringPayment.objects.filter(
        user=user,
        is_active=True,
        auto_create_transaction=True,
        next_due_date__lte=run_date,
    ).select_related("account", "category")
    if is_subscription is not None:
        queryset = queryset.filter(is_subscription=is_subscription)

    stats = {
        "processed": 0,
        "created_transactions": 0,
        "skipped_transactions": 0,
        "errors": 0,
    }
    for recurring in queryset.order_by("next_due_date", "id"):
        stats["processed"] += 1
        try:
            result = _process_single_recurring(recurring, run_date)
            stats["created_transactions"] += result["created"]
            stats["skipped_transactions"] += result["skipped"]
        except Exception as exc:  # pragma: no cover - defensive fallback for batch processing
            recurring.last_execution_at = timezone.now()
            recurring.last_execution_status = RecurringPayment.ExecutionStatus.ERROR
            recurring.last_execution_message = f"Error: {exc}"
            recurring.save(update_fields=["last_execution_at", "last_execution_status", "last_execution_message", "updated_at"])
            stats["errors"] += 1

    if stats["created_transactions"] > 0:
        rebuild_account_balances(user)
    return stats
