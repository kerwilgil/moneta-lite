# Changelog

## Unreleased — 0.3.0 (Intelligence & Interoperability)

_En preparación. La publicación de `v0.3.0` está bloqueada por la validación de
integración PostgreSQL en real._

- Añadida la **cola de importaciones**: `ImportBatch` + `TransactionDraft`,
  deduplicación exacta y por *fingerprint v2*, normalización de `external_id`,
  sanitización de `raw_metadata`, aprobación y rechazo humanos, marcado de
  duplicados, idempotencia y volcado atómico con `rollback`.
- Añadido el **servidor Moneta MCP** sobre el SDK oficial `mcp` 2.2.x
  (`mcp.server.lowlevel.Server`): protocolo moderno `2026-07-28` (y legacy
  `2025-11-25`), transportes **stdio** y **Streamable HTTP oficial**
  (`Server.streamable_http_app`), 15 herramientas (10 `read` + 5 `draft`).
- Seguridad MCP: autenticación por token con HMAC-SHA256 + *pepper* (token en
  claro no persistido), token de un solo uso en la UI, scopes `read`/`draft`,
  aislamiento por inquilino, paginación, validación de entrada, rate limiting,
  auditoría y redacción de secretos. Eliminado `--allow-unauthenticated`.
- Añadida la **base de IA** (`AIProvider` / `DisabledProvider`): Moneta funciona
  sin IA, sin clave de API y sin internet; la IA nunca es autoridad financiera.
- UI: pantalla de cola de importaciones (editar / aprobar / rechazar) y ajustes
  **Configuración → Integraciones → Moneta MCP** (habilitar, generar, regenerar,
  revocar, scopes, prefijo, último uso, instrucciones de conexión, token de un
  solo uso), con i18n `es-pa` / `es` / `en` y accesibilidad revisada.
- Corrección: `finanzas/views.py` importaba `SimpleNamespace` sin declararlo, lo
  que provocaba un error 500 en la lista de movimientos al reutilizar la caché de
  filtros de sesión; añadido el import y una prueba de regresión.
- Documentación: README profesional, capturas reales con datos de demostración,
  `docs/mcp.md`, `docs/import-queue.md`, `SECURITY.md`, plantilla de release y
  metadata de GitHub.
- Cobertura de pruebas: 172 tests (0 fallos, 0 errores).

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
