# Business Rules

This document summarizes Moneta's financial rules. Use it before changing forms, services or balances.

## Users And Isolation

Every relevant financial record belongs to a user. A view or form must not allow a user to select accounts, categories, cards, invoices or recurring records from another user.

Practical rule:

- In views: filter by `request.user`.
- In forms: pass `user=request.user`.
- In services: receive `user` and filter by it.

## Accounts

`Account` represents cash, bank, checking, savings, investment, credit card, loan, receivable, payable and capital accounts.

Key fields:

- `opening_balance`: base balance.
- `current_balance`: current operating balance.
- `account_type`: determines how the balance is interpreted.

Account names are case-insensitive unique per user.

## Categories

`Category` classifies transactions as income, expense or transfer.

Rules:

- Expense categories must not be used for income.
- Income categories must not be used for expenses.
- Recurring payments and subscriptions use expense categories.
- `monthly_limit` must be greater than zero when provided.
- Names are unique per user, type and case-insensitive spelling.

## Transactions

`FinancialTransaction` is the main money movement record.

Types:

- `income`: income.
- `collection`: collection.
- `expense`: expense.
- `transfer`: transfer between accounts.
- `card_payment`: credit card payment.

Statuses:

- `pending`: does not affect balances.
- `cleared`: affects balances and creates journal entry.
- `void`: does not affect balances and removes automatic journal entry.

Validation rules:

- `amount` must be greater than zero.
- Transfers require destination account.
- Origin and destination accounts cannot be the same.
- Card payment requires related card.
- Category must match transaction type.

Balance rules:

- Income/collection in normal accounts increases balance.
- Income/collection in credit-card accounts decreases debt.
- Expense in normal accounts decreases balance.
- Expense in credit-card accounts increases debt.
- Transfer decreases origin and increases destination.
- Card payment decreases payer account and reduces card debt.

## Credit Cards

`CreditCard` has one linked account of type `credit_card`.

Important fields:

- `credit_limit`: approved limit.
- `current_debt`: current debt.
- `annual_interest_rate`: annual rate.
- `monthly_service_rate`: statement monthly rate when available.
- `statement_balance`: exact statement balance.
- `statement_minimum_payment`: exact statement minimum payment.
- `statement_cash_payment`: exact statement cash payment.
- `global_limit`, `global_available`, `global_balance`: bank-provided global values.
- `statement_day`: statement day, 1 to 31.
- `payment_due_day`: due day, 1 to 31.
- `minimum_payment_percent`: fallback percentage for estimated minimum payment.

Rules:

- Limit must be greater than zero.
- Debt, rates and statement values must not be negative.
- Statement day and due day must be between 1 and 31.
- Global values override calculated values when present.
- Statement balance is used as interest basis when present.
- FECI applies when interest basis exceeds 5000.00.
- `MONETA_FECI_ANNUAL_RATE_PERCENT` controls annual FECI rate and falls back to 1.00 if invalid.

## Invoices

`Invoice` stores issued or received invoices.

Rules:

- `subtotal` must be greater than zero.
- `tax` cannot be negative.
- `total = subtotal + tax`.
- Number is unique by user and invoice type.
- Pending invoices with due date before today become `overdue`.
- `draft` and `void` invoices must not keep automatic journal entries.

Journal entries:

- Issued invoice: debit receivables and credit income result.
- Received invoice: debit expense result and credit payables.

## Accounting Ledger

`JournalEntry` and `JournalLine` represent debit/credit entries.

Rules:

- A manual entry needs at least two lines.
- One line cannot have debit and credit at the same time.
- One line must have debit or credit.
- Total debit must equal total credit.
- Automatic entries are rebuilt when transactions or invoices are edited.

## Recurring Payments And Subscriptions

`RecurringPayment` supports recurring payments and subscriptions in the same table.

Rules:

- `amount` must be greater than zero.
- Category must be expense.
- `is_subscription=True` marks subscriptions.
- `auto_create_transaction=True` allows automatic transaction creation.
- Only active records execute.
- Execution does not duplicate movements if a non-void transaction already exists for the same date.
- Supported frequencies: weekly, biweekly, monthly, quarterly and yearly.

Monthly projection:

- Weekly: amount x 4.
- Biweekly: amount x 2.
- Monthly: amount x 1.
- Quarterly: amount / 3.
- Yearly: amount / 12.

## Dashboard And Advice

Dashboard summarizes:

- Assets.
- Liabilities.
- Capital.
- Monthly income.
- Monthly expenses.
- Card payments.
- Cash flow.
- Upcoming payments.
- Credit cards.
- Category budgets.
- Expense breakdown.

Current advice rules:

- Negative cash flow when expenses exceed income.
- High card usage from 70%.
- Card watch from 50%.
- High subscriptions when they exceed 15% of expenses.
- Categories exceeded or near the limit.

## Exports

CSV availability by edition:

- Lite: basic exports.
- Pro/Demo/Personal: basic and advanced exports.

Rules:

- Row limit: `EXPORT_ROW_LIMIT`.
- Dangerous cells are prefixed with `'` to prevent formula injection.

## Production

Required rules:

- `DJANGO_DEBUG=0`.
- Unique private `DJANGO_SECRET_KEY`.
- `DJANGO_ALLOWED_HOSTS` with real domain/IP.
- `DJANGO_CSRF_TRUSTED_ORIGINS` with real HTTPS origin.
- HTTPS active before redirect and HSTS.
- Do not use `admin/admin`.
- Do not commit `.env`, SQLite databases or logs.
