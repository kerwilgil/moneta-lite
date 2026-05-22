<div align="center">
  <img src="static/img/moneta_icon_dark.png" alt="Moneta" width="160">
  <h1>Moneta</h1>
  <p><strong>SaaS de finanzas personales, tarjetas, suscripciones y control contable.</strong></p>
  <p>
    <img alt="Django" src="https://img.shields.io/badge/Django-5.2%2B-0b5f3a?style=flat-square">
    <img alt="Python" src="https://img.shields.io/badge/Python-3.10%2B-1f6feb?style=flat-square">
    <img alt="Edition" src="https://img.shields.io/badge/Editions-Demo%20%7C%20Lite%20%7C%20Pro%20%7C%20Personal-c9a227?style=flat-square">
  </p>
</div>

Moneta es una plataforma SaaS de finanzas personales y control contable construida con Django. Permite registrar cuentas, movimientos, tarjetas de credito, suscripciones, pagos recurrentes, facturas, reportes y libro contable desde un solo panel.

Este repositorio es la fuente principal privada del producto. Desde aqui se generan las variantes Lite, Pro y Personal.

## Ediciones

- `Demo`: entorno completo para pruebas, presentaciones y ajustes internos.
- `Lite`: version limitada para demostracion o distribucion inicial.
- `Pro`: version completa para entrega pagada.
- `Personal`: version privada para uso local en PC o NAS.

Las ediciones se controlan con `SAAS_EDITION` en `.env`.

## Stack

- Python + Django.
- SQLite para desarrollo/local.
- PostgreSQL recomendado para produccion.
- Templates Django, Bootstrap, Chart.js y JavaScript ligero.
- Scripts PowerShell para variantes, paquetes y tareas recurrentes.

## Puesta En Marcha

Guia rapida:

```text
QUICKSTART.md
```

Instalacion completa para Windows, Linux, NAS o servidor:

```text
INSTALL.md
```

Documentacion complementaria:

```text
FAQ.md
SUPPORT.md
CHANGELOG.md
```

Documentacion tecnica interna en español:

```text
docs/es/architecture.md
docs/es/developer-guide.md
docs/es/business-rules.md
docs/es/release-process.md
```

Internal technical documentation in English:

```text
docs/en/architecture.md
docs/en/developer-guide.md
docs/en/business-rules.md
docs/en/release-process.md
```

Documentacion adicional:

```text
docs/product-editions.md
docs/roadmap.md
```

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py seed_demo
python manage.py runserver 127.0.0.1:8002
```

Python 3.13 o 3.14 funcionan bien. En Python 3.10/3.11, `requirements.txt` instala Django 5.2 LTS.

## Configuracion

Crea un archivo `.env` tomando como base `.env.example`.

Variables principales:

- `DJANGO_SECRET_KEY`: clave privada de Django.
- `DJANGO_DEBUG`: `1` para desarrollo, `0` para produccion.
- `DJANGO_ALLOWED_HOSTS`: dominios/IP permitidos.
- `DJANGO_CSRF_TRUSTED_ORIGINS`: origenes HTTPS confiables si hay proxy/dominio.
- `DJANGO_SECURE_SSL_REDIRECT`: `1` en produccion con HTTPS activo.
- `DJANGO_SECURE_HSTS_SECONDS`: `31536000` en produccion con HTTPS estable.
- `SAAS_EDITION`: `demo`, `lite`, `pro` o `personal`.
- `SAAS_APP_NAME`: nombre visible de la app.

No subas `.env`, bases SQLite ni logs al repositorio.

## Modulos

- Dashboard financiero.
- Cuentas: efectivo, banco, cuenta corriente, ahorro, inversion, tarjetas, prestamos, cuentas por cobrar/pagar y capital.
- Movimientos: ingresos, gastos, cobros, pagos de tarjeta y transferencias.
- Tarjetas de credito: limite, deuda, disponible, tasa mensual/anual, pago minimo, pago contado, FECI y estado de cuenta.
- Suscripciones y pagos recurrentes.
- Seguros privados como suscripciones: vida, salud e ingreso.
- Facturas emitidas y recibidas.
- Libro contable Debe/Haber.
- Reportes y presupuestos por categoria.
- Exportacion CSV.
- Ingreso neto y calculadora rapida.

## Variantes

Crear o regenerar una variante:

```powershell
.\scripts\create_variant.ps1 -Edition lite -Force
.\scripts\create_variant.ps1 -Edition pro -Force
.\scripts\create_variant.ps1 -Edition personal -Force
```

Sincronizar cambios del proyecto base hacia variantes existentes:

```powershell
.\scripts\sync_variants.ps1
```

Generar paquetes publicables sin `.env`, bases SQLite ni logs:

```powershell
.\scripts\package_releases.ps1
```

Los ZIP quedan en `releases/`.

## Venta Y Entrega Pro

La estrategia comercial recomendada esta documentada en `COMMERCIAL.md`.

- Moneta Lite: demo publica gratuita.
- Moneta Pro: descarga pagada recomendada en Lemon Squeezy.
- Moneta Pro + instalacion guiada: servicio adicional para dejarlo funcionando en PC, NAS o servidor.
- Moneta Lite usa licencia MIT.
- Moneta Pro usa licencia comercial, no redistribuible.
- Moneta Personal es privada.

Cuando tengas el enlace de compra, agregalo al README publico de Lite como llamada a la version Pro.

## Automatizacion

Ejecucion manual desde interfaz:

- `Recurrentes` -> `Ejecutar ahora`
- `Suscripciones` -> `Ejecutar ahora`

Ejecucion por consola:

```powershell
python manage.py run_recurring --username demo --scope all
```

Opciones:

- `--scope recurring`: solo pagos recurrentes.
- `--scope subscription`: solo suscripciones.
- `--run-date YYYY-MM-DD`: fecha de proceso especifica.

Ejemplo de tarea programada en Windows:

```powershell
python manage.py run_recurring --username TU_USUARIO --scope all
```

## Seguridad

Antes de publicar una variante en Internet:

```powershell
python manage.py test
python manage.py check --deploy
python manage.py collectstatic
```

Configuracion minima de produccion:

- `DJANGO_DEBUG=0`
- `DJANGO_SECRET_KEY` fuerte y privado.
- `DJANGO_ALLOWED_HOSTS` con dominio/IP real.
- `DJANGO_CSRF_TRUSTED_ORIGINS` con `https://dominio.com`.
- `DJANGO_SECURE_SSL_REDIRECT=1`.
- `DJANGO_SECURE_HSTS_SECONDS=31536000` cuando HTTPS ya este confirmado.
- HTTPS obligatorio para sesiones reales.
- `/admin/` protegido con clave fuerte y, si es posible, VPN/IP allowlist.

El comando `bootstrap_admin` bloquea la clave `admin` en produccion. `seed_demo` tambien queda bloqueado con `DJANGO_DEBUG=0` salvo confirmacion explicita.

Ver detalles en `security_best_practices_report.md`.

## Licencia

Este repositorio privado usa licencia privada. Ver `LICENSE`.

Licencias por edicion:

- Lite: `licenses/LITE-MIT.txt`.
- Pro: `licenses/PRO-COMMERCIAL.txt`.
- Personal: `licenses/PERSONAL-PRIVATE.txt`.
- Demo: `licenses/DEMO-EVALUATION.txt`.

## Flujo Recomendado

1. Trabajar siempre sobre este repositorio privado.
2. Probar cambios en `instances/personal-live` o entorno local.
3. Sincronizar variantes con `scripts/sync_variants.ps1`.
4. Validar con tests/checks.
5. Generar ZIPs con `scripts/package_releases.ps1`.
6. Publicar Lite como demo y entregar Pro solo despues del pago.
