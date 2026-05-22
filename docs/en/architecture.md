# Moneta Architecture

This document explains how Moneta is organized so a developer can locate changes without reading the whole project from scratch.

## Overview

Moneta is a Django application for personal finance and accounting control. The main app is `finanzas`; `config` contains Django settings, global URLs and WSGI/ASGI deployment entry points.

Basic flow:

1. The user enters through a URL declared in `finanzas/urls.py`.
2. A view in `finanzas/views.py` applies filters, edition permissions and calls forms or services.
3. Forms in `finanzas/forms.py` validate user input.
4. Models in `finanzas/models.py` persist accounts, transactions, invoices, credit cards and journal entries.
5. Shared rules live in `finanzas/services.py`, `finanzas/accounting.py` and `finanzas/automation.py`.
6. Templates in `templates/finanzas/` render the panel.
7. Static files in `static/` provide styles, JavaScript and visual branding.

## Main Modules

`finanzas/models.py`

Defines the data schema:

- `Account`: user-owned financial accounts.
- `Category`: income, expense or transfer categories.
- `FinancialTransaction`: money movements.
- `JournalEntry` and `JournalLine`: Debe/Haber accounting ledger.
- `RecurringPayment`: recurring payments and subscriptions.
- `Invoice`: issued or received invoices.
- `CreditCard`: card debt, available credit, interest, FECI and payment calculations.
- `FinancialAdviceRule`: metadata for configurable advice rules.

`finanzas/forms.py`

Validates user input before create/edit operations. `UserScopedModelForm` restricts selectable querysets to the active user.

`finanzas/views.py`

Contains HTTP screens and actions. It also includes UI helpers, filters, CSV exports and subscription preset catalogs.

`finanzas/services.py`

Contains dashboard, reporting and advice calculations. Put query and aggregation rules here when they are not directly tied to an HTTP request.

`finanzas/accounting.py`

Maintains balances and automatic journal entries. This is critical for transactions, invoices, cards and transfers.

`finanzas/automation.py`

Processes recurring payments and subscriptions. It creates automatic transactions, avoids duplicates by due date and advances the next due date.

`finanzas/product.py`

Controls editions and feature gates: demo, lite, pro and personal.

## Responsibility Layers

Models:

- Store structure, relationships, simple computed properties and constraints.
- Must not depend on `request`.

Forms:

- Validate user-entered data.
- Scope selectable objects by `user`.

Services:

- Calculate summaries, series, budgets and advice.
- Avoid N+1 queries in dashboards and reports.

Accounting:

- Update balances and journal entries.
- Use transactions when multiple tables are touched.

Views:

- Coordinate request, forms, services and responses.
- Enforce per-user access.

Templates:

- Present data prepared by views/services.
- Avoid complex financial logic.

## Key Data Relationships

Every main financial object belongs to a `user`, which keeps users isolated in the same installation.

`Account.current_balance` is rebuilt from cleared transactions, except manual account types such as investments. Credit cards have a one-to-one account; card debt is synchronized with that account balance.

`FinancialTransaction.status` determines whether a transaction affects balances and journal entries. Only `cleared` affects balances.

`Invoice.status` determines whether an automatic journal entry exists. `draft` and `void` remove the linked automatic entry.

`RecurringPayment.is_subscription` separates general recurring payments from subscriptions while sharing the same table and automation.

## Transaction Flow

1. `transaction_create` or `transaction_edit` uses `TransactionForm`.
2. The form validates positive amount, type, category, destination account and related card.
3. The view saves and calls `sync_transaction_journal`.
4. The view calls `rebuild_account_balances`.
5. Lists and dashboard read updated state.

## Invoice Flow

1. `invoice_create` or `invoice_edit` uses `InvoiceForm`.
2. The form validates positive subtotal and non-negative tax.
3. The view saves and calls `sync_invoice_journal`.
4. `mark_overdue_invoices` updates overdue pending invoices.

## Recurring Flow

1. The user creates a recurring payment or subscription.
2. `execute_due_recurrings_for_user` finds active, automatic, due records.
3. It creates an expense transaction for each missing due date.
4. It advances `next_due_date` according to frequency.
5. If transactions were created, it rebuilds balances.

## Editions

Editions are controlled by `SAAS_EDITION` and `APP_FEATURES`.

- `demo`, `pro`, `personal`: full modules.
- `lite`: limited modules and basic exports.

When adding a new screen, define its feature in `finanzas/product.py` and protect the view with `@require_feature` if needed.

## Variants And Releases

The private repository is the source of truth. `variants/` and `instances/` are generated or synchronized from the base project and ignored by Git.

- `scripts/create_variant.ps1`: creates a new variant.
- `scripts/sync_variants.ps1`: copies base changes into existing variants.
- `scripts/package_releases.ps1`: creates release ZIPs in `releases/`.

## Risk Areas

- `accounting.py` changes can alter historical balances.
- `models.py` changes require migrations.
- `product.py` changes can expose or block modules by edition.
- CSV exports must preserve `sanitize_csv_cell`.
- `create_variant.ps1` changes can affect paid deliveries.

## Where To Look First

- New financial rule: `services.py` or `accounting.py`.
- New input validation: `forms.py`.
- New column or relationship: `models.py`, migration and tests.
- New screen: `urls.py`, `views.py`, template and feature gate.
- New edition module: `product.py`, navigation templates and Lite/Pro tests.
