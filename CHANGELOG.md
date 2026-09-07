# Changelog

## 0.2.0 - 2026-08-01

- Updated Django to the security-fixed 6.0.7 baseline and made production-safe settings the default.
- Replaced cache-based, IP-only login lockout with atomic account-and-network throttling.
- Disabled browser bootstrap by default; optional setup now requires a one-time secret and database lock.
- Added trusted-proxy CIDR validation, bounded recurring batches and database idempotency constraints.
- Made transaction, invoice and journal synchronization atomic and added tenant/domain constraints.
- Removed write side effects from GET requests and added `mark_overdue_invoices` for scheduled execution.
- Enforced the Lite insurance subscription policy server-side.
- Hardened release scripts, removed password CLI/persistence paths and added SHA-256 manifests.
- Improved form errors, live messages, keyboard navigation, chart alternatives, contrast and mobile tables.
- Expanded regression coverage from 15 to 25 tests.
- Added safe Windows start/stop launchers with PID ownership validation and edition-specific ports.
- Restored the transparent Moneta mark and clarified the scope of the Full, Lite and Personal repositories.

## 0.1.2 - 2026-05-14

- Optimized dashboard cash-flow series from repeated monthly queries to one grouped query.
- Fixed financial advice so zero-income months still trigger negative cash-flow warnings.
- Improved Decimal precision for quarterly and yearly recurring projections.
- Made FECI rate parsing crash-safe when the environment value is invalid.
- Hardened production settings validation and variant generation secrets.
- Added preflight validation for case-insensitive account/category name constraints.

## 0.1.1 - 2026-05-13

- Added money validation to transaction, invoice, recurring payment and credit card forms.
- Added password validation to the initial superuser setup form.
- Added pagination and export row limits for large lists and CSV exports.
- Marked overdue invoices from dashboard and invoice list views.
- Added case-insensitive uniqueness constraints for account and category names per user.
- Expanded finance form, service and view tests.

## 0.1.0 - 2026-05-05

- Added Moneta Lite public edition with credit cards and private insurance subscriptions.
- Locked the public Lite package to Lite features only.
- Added Quickstart and full installation guides for Windows PowerShell, Windows CMD, Mac, Linux and NAS.
- Added MIT license for Lite and commercial/private licenses for paid or private editions.
- Added commercial delivery notes, support scope and release packaging flow.
- Improved README branding with Moneta logo.
