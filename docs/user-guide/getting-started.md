# Primeros pasos

## Qué es

La ruta mínima para dejar Moneta funcionando y registrar tu primer movimiento.

## Requisitos

Python 3.12, 3.13 o 3.14. SQLite viene incluido; PostgreSQL es opcional.

## Pasos

1. `pip install -r requirements.txt`.
2. `cp .env.example .env` y define al menos `DJANGO_SECRET_KEY`.
3. `python manage.py migrate`.
4. `python manage.py createsuperuser`.
5. `python manage.py runserver 127.0.0.1:8000` y entra en http://127.0.0.1:8000/.

## Ejemplo

Crea la cuenta "Banco principal" con saldo de apertura 1000 y registra un gasto de 20 en "Comida". El Dashboard debe mostrar balance 980.

## Notas

Deja `DJANGO_DEBUG=1` solo para pruebas locales en 127.0.0.1. Para acceso remoto usa HTTPS mediante proxy inverso o VPN privada. En Windows están `start.bat` / `stop.bat`.

---

Versión corta dentro de la app: **Ayuda** en Moneta. Índice: [README.md](README.md).
