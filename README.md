<div align="center">
  <img src="static/img/moneta_icon_dark.png" alt="Moneta Lite" width="140">

  <h1>Moneta Lite</h1>

  <p><strong>Plataforma self-hosted de finanzas personales: cuentas, tarjetas, suscripciones, facturas y reportes en un panel local, bilingüe y orientado a la privacidad.</strong></p>

  <p>
    <img alt="Python" src="https://img.shields.io/badge/Python-3.12%20%E2%80%93%203.14-1f6feb?style=flat-square&logo=python&logoColor=white">
    <img alt="Django" src="https://img.shields.io/badge/Django-6.0-0b5f3a?style=flat-square&logo=django&logoColor=white">
    <img alt="MCP" src="https://img.shields.io/badge/MCP-2026--07--28-6f42c1?style=flat-square">
    <img alt="Tests" src="https://img.shields.io/badge/tests-172%20passing-2ea44f?style=flat-square">
    <img alt="i18n" src="https://img.shields.io/badge/i18n-ES%20%7C%20EN-1f6feb?style=flat-square">
    <img alt="License" src="https://img.shields.io/badge/License-MIT-c9a227?style=flat-square">
  </p>

  <img src="docs/screenshots/dashboard-light.jpg" alt="Panel financiero de Moneta Lite" width="820">
</div>

---

Moneta Lite es la edición **gratuita y de código abierto** de Moneta. Corre en tu
propia máquina (Windows, Linux, macOS o NAS), guarda los datos en tu disco y
funciona **sin conexión, sin cuenta en la nube y sin clave de API**.

Además, expone un servidor **MCP** para que un agente de IA pueda **leer** tus
finanzas y **proponer borradores** — pero el núcleo financiero es determinista y
**cada movimiento real lo aprueba una persona**.

- 🔒 **Tuyo y local** — SQLite por defecto, PostgreSQL opcional. Nada sale de tu equipo.
- 🌐 **Bilingüe** — español (`es-pa`, `es`) e inglés (`en`).
- 🌗 **Modo claro y oscuro**.
- 🤖 **MCP-ready** — interoperable con agentes, con una frontera de aprobación humana.
- 🧾 **Cola de importaciones** — deduplicación + revisión humana para todo lo que entra de fuera.

## Tabla de contenidos

- [Funcionalidades](#funcionalidades)
- [Capturas](#capturas)
- [Inicio rápido](#inicio-rápido)
- [Requisitos](#requisitos)
- [Instalación](#instalación)
- [Configuración](#configuración)
- [Lite vs Pro](#lite-vs-pro)
- [Cola de importaciones](#cola-de-importaciones)
- [Moneta MCP](#moneta-mcp)
- [Interoperabilidad con IA](#interoperabilidad-con-ia)
- [Seguridad](#seguridad)
- [Idiomas](#idiomas)
- [Self-hosting](#self-hosting)
- [Desarrollo](#desarrollo)
- [Tests](#tests)
- [Documentación](#documentación)
- [Roadmap](#roadmap)
- [Licencia](#licencia)

## Funcionalidades

| | Módulo | Qué hace |
|---|--------|----------|
| 📊 | **Dashboard** | Balance, ingresos del mes, deuda registrada, cuentas y tendencia de flujo. |
| 💳 | **Cuentas** | Efectivo, banco, ahorro, inversión, tarjetas, préstamos y capital. |
| 🔁 | **Movimientos** | Ingresos, gastos, transferencias y pagos de tarjeta, con filtros y resumen. |
| 🏦 | **Tarjetas de crédito** | Límite, saldo, disponible, uso %, pago mínimo y contado, corte/vencimiento. |
| 🛡️ | **Suscripciones** | Gasto recurrente y apartado de seguros privados (vida, salud, ingreso). |
| 🧾 | **Facturas** | Emitidas y recibidas, con estados y marcado de vencidas. |
| 📈 | **Reportes** | Activos, pasivos, capital neto, flujo del mes y presupuesto por categoría. |
| 📤 | **Exportación CSV** | Movimientos, facturas y suscripciones. |
| 🧠 | **Cola de importaciones** | Borradores con deduplicación y aprobación humana. |
| 🔌 | **Moneta MCP** | Servidor MCP `2026-07-28` con scopes `read` y `draft`. |
| 📚 | **Manual de usuario** | Incluido en español e inglés (`docs/manual/`). |

> Moneta Lite **no** incluye pagos recurrentes automáticos, catálogo completo de
> suscripciones, libro contable, ingreso neto ni exportaciones avanzadas. Esos
> módulos están en Moneta Pro — ver [Lite vs Pro](#lite-vs-pro).

## Capturas

| Panel financiero (claro) | Panel financiero (oscuro) |
|---|---|
| ![Dashboard claro](docs/screenshots/dashboard-light.jpg) | ![Dashboard oscuro](docs/screenshots/dashboard-dark.jpg) |

| Movimientos | Tarjetas de crédito |
|---|---|
| ![Movimientos](docs/screenshots/transactions.jpg) | ![Tarjetas](docs/screenshots/credit-cards.jpg) |

| Suscripciones | Reportes |
|---|---|
| ![Suscripciones](docs/screenshots/subscriptions.jpg) | ![Reportes](docs/screenshots/reports.jpg) |

| Cola de importaciones | Integraciones · Moneta MCP |
|---|---|
| ![Cola de importaciones](docs/screenshots/import-queue.jpg) | ![Ajustes MCP](docs/screenshots/mcp-settings.jpg) |

_Todas las capturas usan datos de demostración ficticios._

## Inicio rápido

```bash
# 1. Clonar
git clone https://github.com/kerwilgil/moneta-lite.git
cd moneta-lite

# 2. Entorno virtual
python -m venv .venv
# Windows PowerShell:  .\.venv\Scripts\Activate.ps1
# Windows CMD:         .venv\Scripts\activate.bat
# macOS / Linux:       source .venv/bin/activate

# 3. Dependencias
pip install -r requirements.txt

# 4. Configuración
cp .env.example .env          # Windows: copy .env.example .env
#   edita .env: al menos DJANGO_SECRET_KEY; deja DJANGO_DEBUG=1 para probar en 127.0.0.1

# 5. Base de datos + usuario
python manage.py migrate
python manage.py createsuperuser

# 6. (opcional) Datos de demostración
python manage.py seed_demo    # requiere DJANGO_DEBUG=1

# 7. Arrancar
python manage.py runserver 127.0.0.1:8000
```

Abre <http://127.0.0.1:8000/>.

En Windows también puedes usar `start.bat` / `stop.bat`.

Guía paso a paso para usuarios sin experiencia técnica: [`QUICKSTART.md`](QUICKSTART.md).

## Requisitos

- **Python 3.12, 3.13 o 3.14** (línea Django 6 fijada en `requirements.txt`).
- **SQLite** (por defecto, sin instalar nada) o **PostgreSQL** para producción.
- Dependencias: `Django>=6.0.7,<6.1`, `python-dotenv`, `mcp>=2.2,<3`.
- El frontend usa Bootstrap 5 y Chart.js desde CDN.
- Para el transporte MCP Streamable HTTP: un servidor ASGI (por ejemplo `uvicorn`).

## Instalación

- **Prueba rápida:** [`QUICKSTART.md`](QUICKSTART.md).
- **Instalación completa** (Windows, macOS, Linux, NAS/QNAP, servidor): [`INSTALL.md`](INSTALL.md).

## Configuración

Crea `.env` a partir de [`.env.example`](.env.example).

| Variable | Descripción | Requerido | Por defecto |
|----------|-------------|-----------|-------------|
| `DJANGO_SECRET_KEY` | Clave privada de Django (50+ caracteres). | Sí | — |
| `DJANGO_DEBUG` | `1` sólo para pruebas locales en `127.0.0.1`; `0` en producción. | — | `0` |
| `DJANGO_ALLOWED_HOSTS` | Dominios/IP permitidos. | En producción | `127.0.0.1,localhost` |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | Orígenes HTTPS de confianza (`https://tu-dominio`). | Si hay proxy/dominio | vacío |
| `DJANGO_SECURE_SSL_REDIRECT` | Forzar HTTPS. | Producción con HTTPS | `1` |
| `SAAS_EDITION` | Edición activa. | — | `lite` |
| `SAAS_APP_NAME` | Nombre visible de la app. | — | `Moneta Lite` |
| `DB_ENGINE` / `DB_NAME` / `DB_USER` / … | Backend de base de datos (ver comentarios en `.env.example` para PostgreSQL). | — | SQLite |
| `MONETA_MCP_TOKEN` | Token para el transporte MCP stdio (no se pasa como argumento CLI). | Sólo MCP stdio | — |

No subas `.env`, `db.sqlite3` ni `logs/` al repositorio (ya están en `.gitignore`).

## Lite vs Pro

La tabla refleja los *feature gates* reales del código (`finanzas/product.py`).

| Módulo | Lite | Pro |
|--------|:----:|:---:|
| Dashboard, cuentas, movimientos | ✅ | ✅ |
| Facturas (emitidas / recibidas) | ✅ | ✅ |
| Tarjetas de crédito | ✅ | ✅ |
| Suscripciones + seguros privados | ✅ | ✅ |
| Reportes y presupuesto por categoría | ✅ | ✅ |
| Exportación CSV básica | ✅ | ✅ |
| Cola de importaciones | ✅ | ✅ |
| Moneta MCP (`read` + `draft`) | ✅ | ✅ |
| Bilingüe ES/EN + modo claro/oscuro | ✅ | ✅ |
| Pagos recurrentes automáticos | — | ✅ |
| Catálogo completo de suscripciones | — | ✅ |
| Libro contable | — | ✅ |
| Ingreso neto (simulación salarial) | — | ✅ |
| Exportaciones avanzadas | — | ✅ |
| Licencia | MIT | Comercial, no redistribuible |

Moneta Pro es la edición de pago con los módulos avanzados. Moneta Lite es
completamente funcional por sí sola.

## Cola de importaciones

Es el único camino por el que un movimiento originado **fuera** de Moneta llega
al núcleo financiero:

```text
Fuente externa → Agente → Moneta MCP → Cola de importaciones
  → Deduplicación → Revisión humana → Aprobación → Núcleo financiero
```

- Deduplicación por `external_id` normalizado y por *fingerprint v2*
  (usuario, origen, comercio, descripción, importe, moneda, fecha, signo).
- Creación de borradores **idempotente**; `raw_metadata` **sanitizada**.
- Aprobación **atómica** con `rollback` completo ante cualquier fallo.
- Estados: `pending`, `approved`, `rejected`, `duplicate`, `error`.
- **MCP no aprueba** — la transición a `approved` sólo ocurre desde la interfaz.

Detalle: [`docs/import-queue.md`](docs/import-queue.md).

## Moneta MCP

Servidor **MCP (Model Context Protocol)** para agentes compatibles.

- Protocolo moderno **`2026-07-28`** (SDK oficial `mcp` 2.2.x); legacy `2025-11-25`.
- Transportes: **stdio** y **Streamable HTTP oficial** (montado en `/mcp`).
- Scopes: **`read`** (10 herramientas) y **`draft`** (5 herramientas).
- **Sin** `approve`, creación directa de movimientos, borrado, mutación de saldos
  ni confirmación de pagos.
- El usuario siempre se deriva del token; no hay override de inquilino.

Genera un token en **Configuración → Integraciones → Moneta MCP**. Se muestra
**una sola vez** y se guarda como HMAC-SHA256 con *pepper*.

```bash
# stdio
MONETA_MCP_TOKEN=<tu-token> python manage.py moneta_mcp_stdio

# Streamable HTTP
uvicorn config.asgi:application --host 127.0.0.1 --port 8001
#   POST http://127.0.0.1:8001/mcp/   con   Authorization: Bearer <tu-token>
```

Detalle y ejemplo de configuración de cliente: [`docs/mcp.md`](docs/mcp.md).

## Interoperabilidad con IA

- La IA puede **interpretar**, **sugerir** y **crear borradores**.
- El **núcleo financiero es determinista**: los saldos y movimientos no dependen
  de la IA.
- **Se requiere aprobación humana** para cualquier movimiento real.
- Moneta funciona **sin IA, sin clave de API y sin internet**. La base de IA
  (`AIProvider` / `DisabledProvider`) viene deshabilitada por defecto; la IA
  nunca es autoridad financiera.

## Seguridad

- Aislamiento por inquilino en cada consulta (incluido MCP).
- Tokens MCP con hash HMAC-SHA256 + *pepper*; el token en claro no se persiste.
- Modelo de scopes `read` / `draft`; herramientas destructivas ausentes.
- Aprobación humana para entradas externas (Import Queue).
- CSRF en todos los POST; sin efectos de escritura en GET.
- Rate limiting y auditoría de las llamadas MCP, con redacción de secretos.
- Bloqueo de login atómico por cuenta y red.

Antes de exponer una instancia:

```bash
python manage.py test
python manage.py check --deploy
python manage.py secret_scan
python manage.py collectstatic
```

Política y reporte de vulnerabilidades: [`SECURITY.md`](SECURITY.md).

## Idiomas

Interfaz y contenido en `es-pa`, `es` y `en`. El idioma se puede cambiar desde la
propia interfaz. Manual de usuario en [`docs/manual/`](docs/manual/) (ES y EN,
Markdown, HTML y PDF).

## Self-hosting

Moneta corre en PC (Windows/macOS/Linux), NAS o servidor. `runserver` es sólo
para desarrollo local: para acceder desde otra máquina, ponlo detrás de un proxy
inverso con HTTPS o una VPN privada, con `DJANGO_DEBUG=0` y `DJANGO_ALLOWED_HOSTS`
configurado. Ver [`INSTALL.md`](INSTALL.md) (incluye pasos para NAS/QNAP).

## Desarrollo

```bash
python manage.py migrate
python manage.py test
python manage.py check
python manage.py makemigrations --check --dry-run
```

Stack: Django 6 (templates renderizados en servidor), Bootstrap 5, Chart.js,
SQLite/PostgreSQL. Sin build de frontend.

## Tests

```bash
python manage.py test
```

Baseline actual: **172 tests** (`0 fallos`, `0 errores`, `6 omitidos` en Lite —
2 de exportaciones avanzadas por *feature gate* y 4 exclusivos de PostgreSQL).

## Documentación

| Documento | Contenido |
|-----------|-----------|
| [`QUICKSTART.md`](QUICKSTART.md) | Prueba rápida en local. |
| [`INSTALL.md`](INSTALL.md) | Instalación completa (Windows, macOS, Linux, NAS). |
| [`docs/mcp.md`](docs/mcp.md) | Servidor Moneta MCP: transportes, scopes, herramientas, ejemplos. |
| [`docs/import-queue.md`](docs/import-queue.md) | Flujo de la cola de importaciones. |
| [`SECURITY.md`](SECURITY.md) | Política de seguridad y postura defensiva. |
| [`FAQ.md`](FAQ.md) | Preguntas frecuentes. |
| [`SUPPORT.md`](SUPPORT.md) | Alcance del soporte. |
| [`CHANGELOG.md`](CHANGELOG.md) | Historial de cambios. |
| [`docs/manual/`](docs/manual/) | Manual de usuario (ES / EN). |

## Roadmap

- [x] Núcleo financiero determinista, multi-cuenta y multi-moneda.
- [x] i18n ES/EN y modo claro/oscuro.
- [x] Cola de importaciones con deduplicación y aprobación humana.
- [x] Servidor Moneta MCP (`2026-07-28`, stdio + Streamable HTTP).
- [ ] Validación de integración PostgreSQL en real (previa a `v0.3.0`).
- [ ] Publicación de `v0.3.0`.

## Licencia

Moneta Lite se distribuye bajo licencia **MIT**. Ver [`LICENSE`](LICENSE).
Puedes usarla, modificarla y redistribuirla conservando el aviso de copyright y
la nota de licencia.
