# Moneta Quickstart

Guia rapida para abrir Moneta en tu computadora y comprobar que funciona.

Si no tienes experiencia tecnica, usa primero esta guia. Para instalacion mas completa, servidor, NAS o produccion, usa `INSTALL.md`.

## Antes De Empezar

Necesitas:

- Python 3.10 o superior instalado.
- La carpeta de Moneta descargada o descomprimida.
- Una terminal abierta dentro de la carpeta de Moneta.

## Como Abrir La Terminal Correcta

### Windows PowerShell

1. Entra a la carpeta donde descomprimiste Moneta.
2. Haz clic derecho en un espacio vacio de la carpeta.
3. Selecciona `Abrir en Terminal` o `Abrir PowerShell aqui`.
4. Ejecuta los comandos de la seccion `Windows PowerShell`.

### Windows CMD

1. Abre `Simbolo del sistema` o `CMD`.
2. Entra a la carpeta de Moneta con `cd`.

Ejemplo:

```cmd
cd C:\Moneta\moneta-lite
```

3. Ejecuta los comandos de la seccion `Windows CMD`.

### Mac O Linux

1. Abre la app `Terminal`.
2. Entra a la carpeta de Moneta con `cd`.

Ejemplo:

```bash
cd ~/Downloads/moneta-lite
```

3. Ejecuta los comandos de la seccion `Mac / Linux`.

## Windows PowerShell

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver 127.0.0.1:8000
```

Abre en el navegador:

```text
http://127.0.0.1:8000/
```

## Windows CMD

```cmd
python -m venv .venv
.venv\Scripts\activate.bat
pip install -r requirements.txt
copy .env.example .env
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver 127.0.0.1:8000
```

Abre en el navegador:

```text
http://127.0.0.1:8000/
```

## Mac / Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver 127.0.0.1:8000
```

Abre en el navegador:

```text
http://127.0.0.1:8000/
```

## Uso En Otra PC De La Misma Red

Si Moneta esta instalado en un NAS o en otra computadora de tu red local, ejecuta:

```bash
python manage.py runserver 0.0.0.0:8000
```

Luego entra desde otro equipo usando la IP del servidor:

```text
http://IP_DEL_SERVIDOR:8000/
```

Ejemplo:

```text
http://192.168.1.50:8000/
```

## Primer Uso

Durante `createsuperuser`, el sistema pedira:

- Usuario.
- Correo, puede dejarse vacio si no quieres usarlo.
- Contrasena.

Despues de iniciar sesion:

1. Crea tus cuentas principales.
2. Registra movimientos.
3. Agrega tarjetas, facturas o suscripciones.
4. Revisa dashboard y reportes.

## Problemas Comunes

- Si `python` no funciona en Windows, prueba `py`.
- Si el puerto `8000` esta ocupado, usa otro: `python manage.py runserver 127.0.0.1:8001`.
- Si PowerShell bloquea la activacion, usa Windows CMD o ejecuta: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`.
- Si accedes desde otra PC o NAS, agrega la IP/dominio en `DJANGO_ALLOWED_HOSTS` dentro del archivo `.env`.
- No uses `DJANGO_DEBUG=1` si vas a publicar Moneta en Internet.
