#!/usr/bin/env bash
# Run with an empty disposable database configured through DB_*.
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
cd "$root"
work="$(mktemp -d)"
trap 'rm -r "$work"' EXIT
if [[ "${DB_ENGINE:-django.db.backends.sqlite3}" == django.db.backends.sqlite3 ]]; then
    export DB_NAME="$work/upgrade.sqlite3"
else
    : "${DB_NAME:?Set DB_NAME to an empty disposable PostgreSQL database}"
    python - <<'PYTHON'
import django
import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()
from django.db import connection

if connection.vendor != "postgresql" or connection.introspection.table_names():
    raise SystemExit("Upgrade check requires an empty disposable PostgreSQL database.")
PYTHON
fi

mkdir "$work/old"
git archive v0.3.0 | tar -x -C "$work/old"
cat > "$work/seed_legacy.py" <<'PY'
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.utils import timezone

from finanzas.accounting import rebuild_account_balances, sync_invoice_journal, sync_transaction_journal
from finanzas.models import Account, FinancialTransaction, Invoice, RecurringPayment

user = get_user_model().objects.create_user("upgrade-fixture")
bank = Account.objects.create(
    user=user, name="Synthetic bank", account_type="checking",
    opening_balance="120", current_balance="120",
)
rule = RecurringPayment.objects.create(
    user=user, account=bank, name="Synthetic legacy rule", amount=Decimal("12"),
    next_due_date=timezone.localdate(), auto_create_transaction=True,
)
movement = FinancialTransaction.objects.create(
    user=user, account=bank, description="Synthetic posted occurrence",
    source_recurring=rule, transaction_type="expense", amount=Decimal("12"), status="cleared",
)
invoice = Invoice.objects.create(
    user=user, number="UPGRADE-1", counterparty="Synthetic vendor",
    invoice_type="issued", subtotal=Decimal("90"), tax=Decimal("0"), status="pending",
)
sync_transaction_journal(movement)
sync_invoice_journal(invoice)
rebuild_account_balances(user, force_account_ids=[bank.pk])
bank.refresh_from_db()
movement.refresh_from_db()
invoice.refresh_from_db()
assert bank.current_balance == 108
assert movement.journal_entry.is_balanced and invoice.journal_entry.is_balanced
PY
(
    cd "$work/old"
    python manage.py migrate --noinput
    python manage.py seed_demo
    python manage.py shell < "$work/seed_legacy.py"
    python manage.py dumpdata finanzas --all --indent 2 > "$work/before.json"
)
SAAS_EDITION=pro python manage.py migrate --noinput
python manage.py dumpdata finanzas --all --indent 2 > "$work/after.json"
cmp "$work/before.json" "$work/after.json"
echo "v0.3.0 upgrade preserved all synthetic finance rows."
