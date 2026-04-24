from decimal import Decimal

from django.db import transaction

from .models import Account, CreditCard, FinancialTransaction, Invoice, JournalEntry, JournalLine


MANUAL_BALANCE_TYPES = {Account.AccountType.INVESTMENT}


def _as_money(value):
    return (value or Decimal("0.00")).quantize(Decimal("0.01"))


def ensure_system_account(user, name, account_type):
    account, _ = Account.objects.get_or_create(
        user=user,
        name=name,
        defaults={
            "account_type": account_type,
            "currency": "USD",
            "opening_balance": Decimal("0.00"),
            "current_balance": Decimal("0.00"),
            "is_active": True,
        },
    )
    return account


def sync_credit_card_account_balance(card):
    account = card.account
    account.opening_balance = _as_money(card.current_debt)
    account.current_balance = _as_money(card.current_debt)
    account.save(update_fields=["opening_balance", "current_balance", "updated_at"])


def _journal_line(entry, account, debit=Decimal("0.00"), credit=Decimal("0.00"), memo=""):
    JournalLine.objects.create(
        entry=entry,
        account=account,
        debit=_as_money(debit),
        credit=_as_money(credit),
        memo=memo,
    )


@transaction.atomic
def rebuild_account_balances(user, force_account_ids=None):
    accounts = {account.id: account for account in Account.objects.filter(user=user)}
    force_account_ids = set(force_account_ids or [])
    txs = list(
        FinancialTransaction.objects.filter(user=user, status=FinancialTransaction.Status.CLEARED)
        .select_related("account", "destination_account", "related_credit_card__account")
        .order_by("date", "id")
    )
    touched_account_ids = set()
    for tx in txs:
        touched_account_ids.add(tx.account_id)
        if tx.destination_account_id:
            touched_account_ids.add(tx.destination_account_id)
        if tx.related_credit_card_id and tx.related_credit_card:
            touched_account_ids.add(tx.related_credit_card.account_id)

    for account in accounts.values():
        if (
            account.id in touched_account_ids
            or account.id in force_account_ids
            or account.account_type not in MANUAL_BALANCE_TYPES
        ):
            account.current_balance = account.opening_balance

    for tx in txs:
        amount = _as_money(tx.amount)
        account = accounts.get(tx.account_id)
        destination = accounts.get(tx.destination_account_id) if tx.destination_account_id else None
        card_account = (
            accounts.get(tx.related_credit_card.account_id)
            if tx.related_credit_card_id and tx.related_credit_card
            else None
        )
        if not account:
            continue

        if tx.transaction_type in (FinancialTransaction.TransactionType.INCOME, FinancialTransaction.TransactionType.COLLECTION):
            if account.account_type == Account.AccountType.CREDIT_CARD:
                account.current_balance -= amount
            else:
                account.current_balance += amount
        elif tx.transaction_type == FinancialTransaction.TransactionType.EXPENSE:
            if account.account_type == Account.AccountType.CREDIT_CARD:
                account.current_balance += amount
            else:
                account.current_balance -= amount
        elif tx.transaction_type == FinancialTransaction.TransactionType.TRANSFER:
            account.current_balance -= amount
            if destination and destination.user_id == user.id:
                destination.current_balance += amount
        elif tx.transaction_type == FinancialTransaction.TransactionType.CARD_PAYMENT:
            account.current_balance -= amount
            if card_account:
                card_account.current_balance -= amount

    Account.objects.bulk_update(accounts.values(), ["current_balance"])

    cards = CreditCard.objects.filter(user=user).select_related("account")
    for card in cards:
        card.current_debt = max(_as_money(card.account.current_balance), Decimal("0.00"))
    CreditCard.objects.bulk_update(cards, ["current_debt"])


def _get_or_new_entry(instance, prefix):
    if instance.journal_entry_id:
        entry = instance.journal_entry
        entry.lines.all().delete()
        return entry
    return JournalEntry(user=instance.user, source=prefix, posted=True)


@transaction.atomic
def sync_transaction_journal(transaction_obj):
    if transaction_obj.status != FinancialTransaction.Status.CLEARED:
        if transaction_obj.journal_entry_id:
            transaction_obj.journal_entry.delete()
            transaction_obj.journal_entry = None
            transaction_obj.save(update_fields=["journal_entry"])
        return

    income_result = ensure_system_account(transaction_obj.user, "Resultado ingresos", Account.AccountType.CAPITAL)
    expense_result = ensure_system_account(transaction_obj.user, "Resultado gastos", Account.AccountType.CAPITAL)
    transfer_bridge = ensure_system_account(transaction_obj.user, "Cuenta puente transferencias", Account.AccountType.CAPITAL)

    entry = _get_or_new_entry(transaction_obj, "tx_auto")
    entry.date = transaction_obj.date
    entry.description = f"Movimiento: {transaction_obj.description}"
    entry.save()
    amount = _as_money(transaction_obj.amount)
    account = transaction_obj.account

    if transaction_obj.transaction_type in (FinancialTransaction.TransactionType.INCOME, FinancialTransaction.TransactionType.COLLECTION):
        _journal_line(entry, account, debit=amount, memo=transaction_obj.description)
        _journal_line(entry, income_result, credit=amount, memo=transaction_obj.description)
    elif transaction_obj.transaction_type == FinancialTransaction.TransactionType.EXPENSE:
        _journal_line(entry, expense_result, debit=amount, memo=transaction_obj.description)
        _journal_line(entry, account, credit=amount, memo=transaction_obj.description)
    elif transaction_obj.transaction_type == FinancialTransaction.TransactionType.TRANSFER:
        destination = transaction_obj.destination_account or transfer_bridge
        _journal_line(entry, destination, debit=amount, memo=transaction_obj.description)
        _journal_line(entry, account, credit=amount, memo=transaction_obj.description)
    elif transaction_obj.transaction_type == FinancialTransaction.TransactionType.CARD_PAYMENT:
        destination = (
            transaction_obj.related_credit_card.account
            if transaction_obj.related_credit_card_id and transaction_obj.related_credit_card
            else transfer_bridge
        )
        _journal_line(entry, destination, debit=amount, memo=transaction_obj.description)
        _journal_line(entry, account, credit=amount, memo=transaction_obj.description)

    if transaction_obj.journal_entry_id != entry.id:
        transaction_obj.journal_entry = entry
        transaction_obj.save(update_fields=["journal_entry"])


@transaction.atomic
def delete_transaction_journal(transaction_obj):
    if transaction_obj.journal_entry_id:
        transaction_obj.journal_entry.delete()


@transaction.atomic
def sync_invoice_journal(invoice_obj):
    if invoice_obj.status in (Invoice.Status.DRAFT, Invoice.Status.VOID):
        if invoice_obj.journal_entry_id:
            invoice_obj.journal_entry.delete()
            invoice_obj.journal_entry = None
            invoice_obj.save(update_fields=["journal_entry"])
        return

    income_result = ensure_system_account(invoice_obj.user, "Resultado ingresos", Account.AccountType.CAPITAL)
    expense_result = ensure_system_account(invoice_obj.user, "Resultado gastos", Account.AccountType.CAPITAL)
    receivable = ensure_system_account(invoice_obj.user, "Cuentas por cobrar", Account.AccountType.RECEIVABLE)
    payable = ensure_system_account(invoice_obj.user, "Cuentas por pagar", Account.AccountType.PAYABLE)

    entry = _get_or_new_entry(invoice_obj, "invoice_auto")
    entry.date = invoice_obj.issue_date
    entry.description = f"Factura {invoice_obj.number}: {invoice_obj.counterparty}"
    entry.save()

    total = _as_money(invoice_obj.total)
    if invoice_obj.invoice_type == Invoice.InvoiceType.ISSUED:
        _journal_line(entry, receivable, debit=total, memo=invoice_obj.number)
        _journal_line(entry, income_result, credit=total, memo=invoice_obj.number)
    else:
        _journal_line(entry, expense_result, debit=total, memo=invoice_obj.number)
        _journal_line(entry, payable, credit=total, memo=invoice_obj.number)

    if invoice_obj.journal_entry_id != entry.id:
        invoice_obj.journal_entry = entry
        invoice_obj.save(update_fields=["journal_entry"])


@transaction.atomic
def delete_invoice_journal(invoice_obj):
    if invoice_obj.journal_entry_id:
        invoice_obj.journal_entry.delete()
