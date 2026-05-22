# Moneta User Manual

Version: 2026-05-22  
Product: Moneta Demo, Lite, Pro and Personal

## Purpose

This manual explains how to use Moneta day to day: sign in, create accounts, record transactions, manage credit cards, track invoices, automate recurring items, review reports and export data.

Moneta is designed for users who want to control personal finance, cash flow, debt, subscriptions and simple accounting from one panel.

## Initial Access

1. Open your installation URL, for example `http://127.0.0.1:8003/`.
2. Enter your username and password.
3. Press `Enter`.

Demo installation credentials after `seed_demo`:

```text
Username: demo
Password: demo12345
```

For production, change credentials before exposing the system to a network.

## Financial Dashboard

The dashboard summarizes:

- Assets.
- Liabilities.
- Capital.
- Monthly income.
- Monthly expenses.
- Credit card payments.
- Cash flow.
- Credit cards.
- Upcoming payments.
- Category budgets.
- Latest transactions.

Use this screen to quickly see whether the month is healthy or if there are debt, budget or negative cash-flow alerts.

## Accounts

Accounts represent where money moves.

Common types:

- Cash.
- Bank.
- Checking.
- Savings.
- Investment.
- Credit card.
- Loan.
- Receivable.
- Payable.
- Capital.

To create an account:

1. Open `Settings`.
2. Press `Create account`.
3. Enter name, type, currency, opening balance and current balance.
4. Save.

Recommendation: create your main accounts before recording transactions.

## Categories

Categories classify income, expenses or transfers.

Examples:

- Income: Payroll, Consulting, Collections.
- Expense: Groceries, Transport, Software, Health.
- Transfer: Movement between your own accounts.

Rules:

- Expenses must use expense categories.
- Income must use income categories.
- Recurring items and subscriptions usually use expense categories.

## Transactions

Transactions record money in, money out and transfers.

Types:

- Income.
- Expense.
- Transfer.
- Card payment.
- Collection.

To record a transaction:

1. Open `Transactions`.
2. Press `New transaction`.
3. Select type, account, category, amount and date.
4. For transfers, select destination account.
5. For card payments, select related card.
6. Save.

Statuses:

- Pending: does not affect balances.
- Cleared: affects balances and accounting.
- Void: does not affect balances.

## Credit Cards

Credit cards help control limit, debt, available credit, interest and recommended payment.

Before creating a card:

1. Create an account of type `Credit card`.
2. Open `Cards`.
3. Press `New card`.
4. Enter limit, debt, annual/monthly rate, statement day and payment due day.

Important fields:

- Limit: approved credit.
- Current debt: used amount.
- Annual rate: annual interest.
- Monthly statement rate: bank-provided monthly rate.
- Statement balance: exact statement balance.
- Statement minimum payment: bank minimum payment.
- Statement cash payment: amount to avoid interest.

Moneta calculates:

- Utilization percent.
- Available credit.
- Estimated monthly interest.
- FECI when applicable.
- Minimum payment.
- Recommended payment.

## Invoices

Invoices can be issued or received.

To create an invoice:

1. Open `Invoices`.
2. Press `New invoice`.
3. Select type: issued or received.
4. Enter number, counterparty, dates, subtotal, tax and status.
5. Save.

Statuses:

- Draft.
- Pending.
- Paid.
- Overdue.
- Void.

Moneta marks pending invoices as overdue when due date has passed.

## Recurring Payments

Recurring payments are used for repeated expenses or income.

Examples:

- Rent.
- Salary.
- Insurance.
- Loan.
- Services.

To create a recurring item:

1. Open `Recurring`.
2. Press `New recurring`.
3. Select account, category, transaction type, amount, frequency and next due date.
4. Enable automatic transaction creation if needed.
5. Save.

Frequencies:

- Weekly.
- Biweekly.
- Monthly.
- Quarterly.
- Yearly.

The `Run now` button creates due transactions and avoids duplicates.

## Subscriptions

Subscriptions use the recurring engine but are separated to control services, insurance and periodic charges.

Examples:

- Spotify.
- YouTube Premium.
- Netflix.
- Life insurance.
- Health insurance.
- Software.

In Lite, subscriptions may be limited by edition.

## Accounting Ledger

The ledger allows reviewing or creating debit/credit entries.

Rules:

- Each entry needs at least two lines.
- One line cannot have debit and credit at the same time.
- Total debit must equal total credit.

Moneta also creates automatic entries for cleared transactions and invoices.

## Reports

Reports show:

- Financial summary.
- Cash flow.
- Category budgets.
- Expense breakdown.
- Invoices.
- Recurring items.

Use them for weekly or monthly decisions.

## CSV Exports

Depending on edition, Moneta can export:

- Transactions.
- Invoices.
- Recurring payments.
- Subscriptions.

Exports respect the visible filters in main lists when applicable.

## Editions

- Demo: complete testing edition.
- Lite: limited public/demo edition.
- Pro: complete commercial edition.
- Personal: private local-use edition.

If an option is missing, it may be disabled by edition.

## Good Practices

- Create accounts and categories before recording transactions.
- Clear only real transactions.
- Review cards after each statement.
- Use invoice statuses correctly.
- Run recurring items weekly or schedule a task.
- Export CSV before major changes.
- Back up `.env` and database.

## Common Problems

An account does not appear in a form:

- Check it belongs to the current user.
- Check it is active.
- For cards, first create a credit-card account.

Cannot create a recurring item:

- Check category matches transaction type.
- Check amount is greater than zero.

Login is locked:

- Wait 15 minutes.
- Verify the password.

## Production Operation

For a published instance:

```bash
python manage.py migrate
python manage.py createcachetable
python manage.py check --deploy
```

Use `createcachetable` when `DJANGO_CACHE_BACKEND=db`.

## Support

When reporting an issue, include:

- Affected screen.
- Steps to reproduce.
- User/edition.
- Error message.
- Screenshot if available.
