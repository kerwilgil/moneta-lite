# Moneta Quickstart

Guia rapida para levantar Moneta en local y validar que el sistema funciona.

## Requisitos

- Python 3.10 o superior.
- Git opcional, si vas a clonar desde un repositorio.
- Terminal PowerShell en Windows, o shell equivalente en Linux/NAS.

## Windows

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver 127.0.0.1:8000
```

Entra en:

```text
http://127.0.0.1:8000/
```

## Linux, NAS o servidor local

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver 0.0.0.0:8000
```

Si estas en una red local, entra desde otro equipo usando la IP del servidor:

```text
http://IP_DEL_SERVIDOR:8000/
```

## Primer uso

1. Crea el usuario administrador con `createsuperuser`.
2. Inicia sesion.
3. Crea tus cuentas principales.
4. Registra movimientos, tarjetas, facturas y suscripciones.
5. Revisa dashboard y reportes.

## Problemas comunes

- Si no abre la pagina, confirma que el puerto `8000` no este ocupado.
- Si accedes desde otra PC o NAS, agrega la IP/dominio en `DJANGO_ALLOWED_HOSTS`.
- Si usas HTTPS o proxy inverso, configura `DJANGO_CSRF_TRUSTED_ORIGINS`.
- No uses `DJANGO_DEBUG=1` en produccion.
