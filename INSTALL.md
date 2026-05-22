# Guia De Instalacion De Moneta

Esta guia explica como instalar Moneta paso a paso. Esta pensada para usuarios con poca experiencia tecnica.

Para una prueba rapida en pocos minutos, usa `QUICKSTART.md`.

## 1. Elegir Donde Instalar

Puedes instalar Moneta en:

- Tu PC con Windows.
- Una Mac.
- Una computadora Linux.
- Un NAS o servidor local, por ejemplo QNAP.
- Un servidor en Internet.

Si solo quieres probar, usa tu PC y ejecuta Moneta en:

```text
http://127.0.0.1:8000/
```

Si quieres acceder desde otra PC de tu red, ejecuta Moneta en:

```text
http://IP_DEL_SERVIDOR:8000/
```

## 2. Preparar La Carpeta

Descarga o descomprime Moneta en una carpeta facil de encontrar.

Ejemplo Windows:

```text
C:\Moneta\moneta-pro
```

Ejemplo Mac/Linux/NAS:

```text
/opt/moneta/moneta-pro
```

## 3. Abrir La Terminal Correcta

### Windows PowerShell

1. Abre la carpeta de Moneta.
2. Haz clic derecho en un espacio vacio.
3. Selecciona `Abrir en Terminal` o `Abrir PowerShell aqui`.

Usa comandos marcados como `powershell`.

### Windows CMD

1. Abre `Simbolo del sistema` o `CMD`.
2. Entra a la carpeta de Moneta:

```cmd
cd C:\Moneta\moneta-pro
```

Usa comandos marcados como `cmd`.

### Mac / Linux / NAS

1. Abre `Terminal`.
2. Entra a la carpeta de Moneta:

```bash
cd /opt/moneta/moneta-pro
```

Usa comandos marcados como `bash`.

## 4. Crear Entorno Virtual

El entorno virtual guarda las dependencias de Moneta separadas del resto del sistema.

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Windows CMD:

```cmd
python -m venv .venv
.venv\Scripts\activate.bat
```

Mac / Linux / NAS:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Si todo esta bien, veras `(.venv)` al inicio de la linea de comandos.

## 5. Instalar Dependencias

Ejecuta dentro de la carpeta de Moneta:

```bash
pip install -r requirements.txt
```

Este paso puede tardar varios minutos.

## 6. Crear El Archivo De Configuracion

Moneta usa un archivo `.env` para guardar configuracion privada.

Windows PowerShell o CMD:

```cmd
copy .env.example .env
```

Mac / Linux / NAS:

```bash
cp .env.example .env
```

Abre `.env` con un editor de texto y revisa:

```env
DJANGO_SECRET_KEY=coloca-una-clave-larga-y-privada
DJANGO_DEBUG=1
DJANGO_ALLOWED_HOSTS=127.0.0.1,localhost
SAAS_EDITION=pro
```

Para publicar en Internet, cambia:

```env
DJANGO_DEBUG=0
DJANGO_SECRET_KEY=una-clave-unica-privada-de-50-caracteres-o-mas
DJANGO_ALLOWED_HOSTS=tu-dominio.com,IP_DEL_SERVIDOR
DJANGO_CSRF_TRUSTED_ORIGINS=https://tu-dominio.com
DJANGO_SECURE_SSL_REDIRECT=1
DJANGO_SECURE_HSTS_SECONDS=31536000
```

Activa `DJANGO_SECURE_SSL_REDIRECT=1` y HSTS solo cuando el dominio ya responda por HTTPS. Si estas haciendo una prueba local por `http://127.0.0.1`, deja `DJANGO_DEBUG=1`.

## 7. Crear Base De Datos

```bash
python manage.py migrate
```

Esto crea las tablas necesarias.

## 8. Crear Usuario Administrador

```bash
python manage.py createsuperuser
```

El sistema pedira usuario, correo y contrasena.

Recomendacion:

- No uses `admin/admin`.
- Usa una contrasena fuerte.
- Guarda el usuario en un lugar seguro.

## 9. Ejecutar Moneta

Solo en tu PC:

```bash
python manage.py runserver 127.0.0.1:8000
```

Abre:

```text
http://127.0.0.1:8000/
```

Para acceder desde otra PC de tu red:

```bash
python manage.py runserver 0.0.0.0:8000
```

Abre desde otra PC:

```text
http://IP_DEL_SERVIDOR:8000/
```

## 10. Instalacion En NAS O QNAP

En QNAP o NAS Linux:

1. Copia Moneta en una carpeta fija.
2. Instala Python 3 si el NAS no lo tiene.
3. Abre terminal/SSH.
4. Entra a la carpeta de Moneta.
5. Ejecuta los pasos de Mac/Linux/NAS.

Recomendado:

- Usar una IP fija para el NAS.
- Mantener `.env` privado.
- Hacer respaldo de la base de datos.
- Usar HTTPS si vas a acceder fuera de casa/oficina.
- Configurar un servicio o tarea para iniciar Moneta automaticamente.

## 11. Verificaciones Antes De Publicar En Internet

Ejecuta:

```bash
python manage.py test
python manage.py check --deploy
python manage.py collectstatic
```

Configuracion minima:

- `DJANGO_DEBUG=0`.
- `DJANGO_SECRET_KEY` unico y privado.
- `DJANGO_ALLOWED_HOSTS` con dominio/IP real.
- HTTPS activo.
- `DJANGO_SECURE_SSL_REDIRECT=1` si todo el trafico publico entra por HTTPS.
- `DJANGO_SECURE_HSTS_SECONDS=31536000` cuando ya confirmaste HTTPS estable.
- Base de datos respaldada.
- Usuario admin con clave fuerte.

## 12. Actualizaciones

Antes de actualizar:

1. Haz copia de seguridad de `.env`.
2. Haz copia de seguridad de la base de datos.
3. Sustituye archivos del codigo.
4. Ejecuta migraciones:

```bash
python manage.py migrate
```

5. Reinicia Moneta.

## 13. Soporte Guiado

La instalacion guiada es un servicio adicional donde se ayuda al comprador a dejar Moneta funcionando en su PC, NAS o servidor.

Puede incluir:

- Revision de requisitos.
- Configuracion de `.env`.
- Migraciones iniciales.
- Creacion de usuario administrador.
- Prueba de acceso local.
- Recomendaciones de seguridad basicas.

No incluye personalizaciones profundas salvo que se acuerden como servicio aparte.
