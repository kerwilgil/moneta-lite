<div align="center">
  <img src="static/img/moneta_icon_dark.png" alt="Moneta Lite" width="160">
  <h1>Moneta Lite</h1>
  <p><strong>Finanzas personales, tarjetas, suscripciones y reportes en un panel local.</strong></p>
  <p>
    <img alt="Django" src="https://img.shields.io/badge/Django-5.2%2B-0b5f3a?style=flat-square">
    <img alt="Python" src="https://img.shields.io/badge/Python-3.12%2B-1f6feb?style=flat-square">
    <img alt="License" src="https://img.shields.io/badge/License-MIT-c9a227?style=flat-square">
  </p>
</div>

Moneta Lite es la edicion gratuita de Moneta para organizar finanzas personales desde una instalacion local. Incluye cuentas, movimientos, tarjetas de credito, suscripciones, pagos recurrentes, facturas, reportes, presupuesto por categoria y libro contable basico.

## Que Incluye

- Dashboard financiero con ingresos, gastos, deuda, capital y flujo reciente.
- Cuentas de efectivo, banco, ahorro, inversion, tarjetas, prestamos y capital.
- Movimientos, transferencias, cobros y pagos de tarjeta.
- Suscripciones y pagos recurrentes.
- Facturas emitidas y recibidas.
- Reportes, presupuesto por categoria y exportacion CSV.
- Manual de usuario en espanol e ingles.

## Primeros Pasos

Guia rapida:

```text
QUICKSTART.md
```

Instalacion completa para Windows, Linux, NAS o servidor:

```text
INSTALL.md
```

Documentacion de ayuda:

```text
FAQ.md
SUPPORT.md
CHANGELOG.md
docs/manual/user-manual-es.md
docs/manual/moneta-user-manual-es.html
docs/manual/user-manual-en.md
docs/manual/moneta-user-manual-en.html
```

## Instalacion Local

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py seed_demo
python manage.py runserver 127.0.0.1:8000
```

Python 3.12, 3.13 o 3.14 funcionan con la linea Django 6 fijada en `requirements.txt`.

## Configuracion

Crea un archivo `.env` tomando como base `.env.example`.

Variables principales:

- `DJANGO_SECRET_KEY`: clave privada de Django.
- `DJANGO_DEBUG`: `1` para desarrollo, `0` para produccion.
- `DJANGO_ALLOWED_HOSTS`: dominios/IP permitidos.
- `DJANGO_CSRF_TRUSTED_ORIGINS`: origenes HTTPS confiables si hay proxy/dominio.
- `DJANGO_SECURE_SSL_REDIRECT`: `1` en produccion con HTTPS activo.
- `SAAS_EDITION`: `lite`.
- `SAAS_APP_NAME`: nombre visible de la app.

No subas `.env`, bases SQLite ni logs al repositorio.

## Seguridad

Antes de publicar una instalacion en Internet:

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
- HTTPS obligatorio para sesiones reales.
- `/admin/` protegido con usuario y clave fuertes.

## Ediciones

- Moneta Lite: edicion publica gratuita.
- Moneta Pro: edicion completa de pago.
- Moneta Personal: edicion privada para uso propio.

## Licencia

Moneta Lite se publica bajo licencia MIT. Ver `LICENSE`.
