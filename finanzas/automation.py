"""Bounded and idempotent recurring-payment execution logic."""

import calendar
import logging
from datetime import date, timedelta

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from .accounting import rebuild_account_balances, sync_transaction_journal
from .models import FinancialTransaction, RecurringPayment

logger = logging.getLogger(__name__)


def add_months(base_date, months):
    month_index = base_date.month - 1 + months
    year = base_date.year + month_index // 12
    month = month_index % 12 + 1
    day = min(base_date.day, calendar.monthrange(year, month)[1])
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
    tx = FinancialTransaction(
        user=recurring.user,
        account=recurring.account,
        source_recurring=recurring,
        category=recurring.category,
        transaction_type=recurring.transaction_type,
        description=f"Auto recurrente: {recurring.name}",
        counterparty=recurring.name,
        amount=recurring.amount,
        date=due_date,
        status=FinancialTransaction.Status.CLEARED,
        notes=f"Generado automaticamente desde recurrente ID {recurring.id}.",
    )
    # The database uniqueness constraint is the concurrency authority; model
    # validation still enforces ownership and field/domain invariants.
    tx.full_clean(validate_constraints=False)
    tx.save()
    sync_transaction_journal(tx)
    return tx


def _process_single_recurring(recurring, run_date, max_cycles=None):
    """Lock, process and advance one schedule while preserving occurrence uniqueness."""
    max_cycles = max_cycles or getattr(settings, "MONETA_RECURRING_MAX_CYCLES", 12)
    max_total_transactions = getattr(settings, "MONETA_RECURRING_MAX_TOTAL_TRANSACTIONS", 200)
    created_count = 0
    skipped_count = 0
    cycles = 0

    with transaction.atomic():
        recurring = (
            # ``of=("self",)`` locks only the recurring row; PostgreSQL rejects
            # ``FOR UPDATE`` over the nullable ``category`` LEFT join otherwise.
            RecurringPayment.objects.select_for_update(of=("self",))
            .select_related("user", "account", "category")
            .get(pk=recurring.pk)
        )
        while recurring.next_due_date <= run_date and cycles < max_cycles and created_count < max_total_transactions:
            due_date = recurring.next_due_date
            try:
                with transaction.atomic():
                    _create_auto_transaction(recurring, due_date)
                created_count += 1
            except IntegrityError:
                occurrence_exists = FinancialTransaction.objects.filter(
                    source_recurring=recurring,
                    date=due_date,
                ).exclude(status=FinancialTransaction.Status.VOID).exists()
                if not occurrence_exists:
                    raise
                skipped_count += 1

            recurring.next_due_date = next_due_date(due_date, recurring.frequency)
            cycles += 1

        recurring.last_execution_at = timezone.now()
        if cycles >= max_cycles and recurring.next_due_date <= run_date:
            recurring.last_execution_status = RecurringPayment.ExecutionStatus.ERROR
            recurring.last_execution_message = "Se alcanzo el limite de ciclos; revisa la fecha del recurrente."
        elif created_count:
            recurring.last_execution_status = RecurringPayment.ExecutionStatus.SUCCESS
            recurring.last_execution_message = f"Generados {created_count} movimiento(s)."
        else:
            recurring.last_execution_status = RecurringPayment.ExecutionStatus.SKIPPED
            recurring.last_execution_message = "Sin cambios; las ocurrencias ya existian."
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
    """Execute one bounded batch of due schedules for one user."""
    run_date = run_date or timezone.localdate()
    batch_size = getattr(settings, "MONETA_RECURRING_BATCH_SIZE", 100)
    queryset = RecurringPayment.objects.filter(
        user=user,
        is_active=True,
        auto_create_transaction=True,
        next_due_date__lte=run_date,
    )
    if is_subscription is not None:
        queryset = queryset.filter(is_subscription=is_subscription)
    recurring_rows = list(queryset.order_by("next_due_date", "id")[:batch_size])

    stats = {"processed": 0, "created_transactions": 0, "skipped_transactions": 0, "errors": 0}
    for recurring in recurring_rows:
        stats["processed"] += 1
        try:
            result = _process_single_recurring(recurring, run_date)
            stats["created_transactions"] += result["created"]
            stats["skipped_transactions"] += result["skipped"]
        except Exception:
            logger.exception(
                "recurring_execution_failed user_id=%s recurring_id=%s",
                user.pk,
                recurring.pk,
            )
            RecurringPayment.objects.filter(pk=recurring.pk, user=user).update(
                last_execution_at=timezone.now(),
                last_execution_status=RecurringPayment.ExecutionStatus.ERROR,
                last_execution_message="Error interno; consulta los registros del servidor.",
            )
            stats["errors"] += 1

    if stats["created_transactions"]:
        rebuild_account_balances(user)
    return stats
