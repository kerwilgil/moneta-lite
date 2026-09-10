# Changelog

## [0.3.0] — Unreleased (Intelligence & Interoperability)

_Release candidate. El `tag` y la GitHub Release se hacen tras la auditoría
posterior a Phase 8._

### Added

- **Cola de importaciones**: `ImportBatch` + `TransactionDraft`, deduplicación
  exacta y por *fingerprint v2*, normalización de `external_id`, sanitización de
  `raw_metadata`, aprobación y rechazo humanos, marcado de duplicados,
  idempotencia y volcado atómico con `rollback`. UI de revisión (editar /
  aprobar / rechazar).
- **Servidor Moneta MCP** sobre el SDK oficial `mcp` 2.2.x
  (`mcp.server.lowlevel.Server`): protocolo moderno `2026-07-28` (y legacy
  `2025-11-25`), transportes **stdio** y **Streamable HTTP oficial**
  (`Server.streamable_http_app`), 15 herramientas (10 `read` + 5 `draft`).
  Pantalla **Configuración → Integraciones → Moneta MCP** para el ciclo de vida
  del token.
- **Base de IA** (`AIProvider` / `DisabledProvider`): Moneta funciona sin IA, sin
  clave de API y sin internet; la IA nunca es autoridad financiera.
- **Centro de ayuda in-app** en `/ayuda/`: índice con búsqueda por filtro,
  artículos por módulo, ayuda contextual ("? Cómo funciona") en Dashboard,
  Movimientos, Tarjetas, Suscripciones, Reportes, Importaciones y MCP. i18n
  `es-pa` / `es` / `en` y respeto de los *feature gates* (Lite no muestra
  módulos Pro).
- **PostgreSQL validado en real** (PostgreSQL 18.6): base desde cero, migraciones
  ida y vuelta, constraints/índices/FK, concurrencia con bloqueo de fila, cola de
  importaciones y MCP. SQLite sigue siendo el modo por defecto.
- Versión de la aplicación visible en la interfaz (`APP_VERSION`).

### Changed

- Los `select_for_update()` de aprobación/edición de borradores y de ejecución de
  recurrentes usan `of=("self",)` para bloquear solo la fila objetivo.
- Los tests T-02 (concurrencia) y T-06 (reversibilidad de migraciones) se movieron
  a `Phase3PostgresIntegrationTests(TransactionTestCase)`; se ejecutan de verdad
  en PostgreSQL (siguen `skipped` en SQLite).
- `.env.example` documenta la configuración PostgreSQL con placeholders.

### Fixed

- `finanzas/views.py` importaba `SimpleNamespace` sin declararlo → error 500 en la
  lista de movimientos al reutilizar la caché de filtros de sesión. Añadido el
  import y una prueba de regresión.
- Los tests e2e de MCP por stdio ya no heredan la configuración `DB_*` del proceso
  padre (`_sqlite_subprocess_env`).

### Security

- Autenticación de tokens MCP con HMAC-SHA256 + *pepper* (token en claro no
  persistido), token de un solo uso en la UI, scopes `read`/`draft`, aislamiento
  por inquilino, paginación, validación de entrada, rate limiting, auditoría y
  redacción de secretos. Eliminado `--allow-unauthenticated`.
- `SECURITY.md` con canal de reporte y postura defensiva.

### Documentation

- README profesional con capturas reales (datos de demostración), sección
  "Novedades de v0.3.0", tabla Lite vs Pro por *feature gates* reales.
- `docs/mcp.md`, `docs/import-queue.md`, `docs/postgresql.md`,
  `docs/user-guide/` (guía completa por módulo), `docs/release-notes/v0.3.0.md`
  (borrador de notas de versión), plantilla de release y metadata de GitHub.

### Tests

- 182 tests. SQLite: Full 4 `skipped`, Lite 6 `skipped`. PostgreSQL: Full 0
  `skipped`, Lite 2 `skipped` (`exports_advanced`). Más las suites del centro de
  ayuda. 0 fallos, 0 errores en las cuatro combinaciones.

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
