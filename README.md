<p align="center">
  <img src="static/img/moneta_icon_dark.png" alt="Moneta" width="140">
</p>

<h1 align="center">Moneta Lite</h1>

<p align="center">
  Control financiero personal ligero con dashboard, cuentas, movimientos, facturas, tarjetas y seguros privados.
</p>

## Caracteristicas

- Dashboard financiero con resumen de activos, deudas y flujo.
- Gestion de cuentas, movimientos y facturas.
- Modulo de tarjetas de credito con limite, disponible, deuda e interes mensual estimado.
- Modulo de suscripciones limitado a seguros privados: vida, salud y respaldo ante incapacidad laboral o perdida de ingresos.
- Exportaciones basicas.

## Requisitos

- Python 3.10 o superior recomendado.
- Django 3.2.x segun `requirements.txt`.
- SQLite para uso local.

## Instalacion Local

Guia rapida:

```text
QUICKSTART.md
```

Instalacion completa:

```text
INSTALL.md
```

```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver 127.0.0.1:8000
```

Luego entra en `http://127.0.0.1:8000/`.

## Seguridad

- No publiques tu archivo `.env`.
- Cambia `SECRET_KEY` antes de usarlo en produccion.
- Usa `DEBUG=False` y configura `ALLOWED_HOSTS` si lo expones en red.
- No subas `db.sqlite3` si contiene datos personales.

## Edicion

Moneta Lite es la version de entrada. Los modulos avanzados como recurrentes, libro contable, ingreso neto y exportaciones avanzadas no estan incluidos en esta edicion.

## Version Pro

Moneta Pro incluye los modulos avanzados para uso completo.

Enlace de compra:

```text
PROXIMAMENTE: agregar aqui el enlace de Lemon Squeezy
```

Cuando el enlace este activo, reemplaza este bloque por:

```markdown
Compra Moneta Pro: https://tu-enlace-de-compra
```
