# Developer Guide

This guide explains how to modify Moneta without breaking financial flows, editions or delivery packages.

## Local Environment

Requirements:

- Python 3.10 or newer.
- `.venv` virtual environment.
- Dependencies from `requirements.txt`.

Base commands:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
python manage.py migrate
python manage.py seed_demo
python manage.py runserver 127.0.0.1:8003
```

Demo credentials after `seed_demo`:

```text
username: demo
password: demo12345
```

Do not run `seed_demo` in production unless you understand the risk and pass `--allow-production`.

## Verification Commands

Before commit:

```powershell
python manage.py test finanzas
python manage.py check
python manage.py makemigrations --check --dry-run
```

Before public release:

```powershell
python manage.py check --deploy
python manage.py collectstatic
```

Recurring automation check:

```powershell
python manage.py run_recurring --username demo --scope all
```

## Code Conventions

- Keep financial logic in `services.py`, `accounting.py` or `automation.py`, not templates.
- Keep input validation in `forms.py`.
- Use `Decimal` for money and percentages.
- Always filter by `request.user` or a `user` argument.
- Use `select_related`, `prefetch_related` and aggregations for large screens.
- Add tests when changing balances, journal entries, permissions, editions or exports.

## Adding A Screen

1. Create or reuse a form in `finanzas/forms.py`.
2. Add a view in `finanzas/views.py`.
3. Register the URL in `finanzas/urls.py`.
4. Create a template in `templates/finanzas/`.
5. If edition-specific, add a feature in `finanzas/product.py` and use `@require_feature`.
6. Add a smoke test for access and the main workflow.

## Adding A Field

1. Edit the model in `finanzas/models.py`.
2. Run `python manage.py makemigrations`.
3. Review the generated migration.
4. Expose the field in a form if users edit it.
5. Update views, templates, admin and exports if needed.
6. Add a validation or render test based on risk.

## Changing Balance Calculations

Review first:

- `finanzas/accounting.py`
- `finanzas/models.py`
- `finanzas/tests.py`

Rules:

- Only `cleared` transactions affect balances.
- `expense` decreases normal accounts and increases credit-card accounts.
- `income` and `collection` increase normal accounts and decrease credit-card accounts.
- `transfer` subtracts origin and adds destination.
- `card_payment` subtracts the payer account and reduces card debt.
- Investments preserve manual balance unless touched by transactions.

After changing balances:

```powershell
python manage.py test finanzas
```

## Changing Journal Entries

Review:

- `sync_transaction_journal`
- `sync_invoice_journal`
- `delete_transaction_journal`
- `delete_invoice_journal`

Every automatic entry must remain balanced: total debit equals total credit.

Do not rename system accounts without considering existing data:

- `Resultado ingresos`
- `Resultado gastos`
- `Cuenta puente transferencias`
- `Cuentas por cobrar`
- `Cuentas por pagar`

## Changing Recurring Payments Or Subscriptions

Review:

- `finanzas/automation.py`
- `RecurringPaymentForm`
- `recurring_list`
- `subscription_list`

Rules:

- Automatic recurring records create transactions only when active and due.
- A transaction is not duplicated if a non-void transaction already exists for the same recurring record and date.
- `max_cycles` prevents infinite loops.
- If transactions are created, balances are rebuilt.

## Changing Editions

Review:

- `finanzas/product.py`
- `templates/base.html`
- `LiteEditionGateTests`
- variant and release scripts

Feature workflow:

1. Define the feature in `EDITION_FEATURES`.
2. Decide whether Lite receives it.
3. Protect views with `@require_feature`.
4. Adjust navigation.
5. Add Lite and Pro/Demo tests.

## Changing CSV Exports

Review export functions at the end of `finanzas/views.py`.

Rules:

- Keep `EXPORT_ROW_LIMIT`.
- Keep `sanitize_csv_cell` for values starting with `=`, `+`, `-` or `@`.
- Use `select_related` when exporting relationships.

## Branding

Relevant `.env` variables:

- `SAAS_APP_NAME`
- `SAAS_APP_DESCRIPTION_ES`
- `SAAS_APP_DESCRIPTION_EN`
- `SAAS_APP_FAVICON`
- `SAAS_APP_OG_IMAGE`
- `SAAS_APP_LOGO_LIGHT`
- `SAAS_APP_LOGO_DARK`
- `SAAS_LOGIN_TITLE_ES`
- `SAAS_LOGIN_TITLE_EN`
- `SAAS_LOGIN_DESCRIPTION_ES`
- `SAAS_LOGIN_DESCRIPTION_EN`

The template context is built in `finanzas/context_processors.py`.

## Delivery Checklist

- Tests pass.
- `check` passes.
- `check --deploy` passes with a real production `.env`.
- Migrations apply on a clean database.
- Admin user does not use default credentials.
- Variants are synchronized with `scripts/sync_variants.ps1`.
- ZIPs are generated with `scripts/package_releases.ps1`.
- `CHANGELOG.md` is updated.
