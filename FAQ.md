# FAQ

## What Is Moneta?

Moneta is a Django-based personal finance and accounting system for accounts,
transactions, invoices, credit cards, subscriptions, reports and cash-flow
tracking.

## What Is The Difference Between Lite And Pro?

Moneta Lite is the free entry edition. It includes dashboard, accounts,
transactions, invoices, credit cards and private insurance subscriptions.

Moneta Pro is the paid edition. It includes the advanced modules such as
recurring payments, full subscriptions, accounting ledger, net income and
advanced exports.

## Can I Use Moneta On A NAS?

Yes. Moneta can run on a NAS or local server if Python and the required
dependencies are available. See `INSTALL.md`.

## Can I Access Moneta From Another Computer?

Yes. Run the server with:

```bash
python manage.py runserver 0.0.0.0:8000
```

Then open:

```text
http://IP_DEL_SERVIDOR:8000/
```

## Should I Use A Simple Demo Password?

No. Use a unique admin username and a strong password. Simple demo credentials
should never be used in a real environment.

## Can I Publish Moneta On The Internet?

Yes, but configure production settings first:

- `DJANGO_DEBUG=0`.
- Strong `DJANGO_SECRET_KEY`.
- Correct `DJANGO_ALLOWED_HOSTS`.
- HTTPS.
- Strong admin password.
- Backups.

## Can I Resell Moneta Lite?

Moneta Lite uses MIT license, so it allows broad reuse. Keep the copyright and
license notice.

## Can I Resell Moneta Pro?

No. Moneta Pro uses a commercial license that allows use and modification, but
does not allow redistribution, resale or publication as a competing template.
