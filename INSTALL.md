# Guia De Instalacion De Moneta

Esta guia cubre una instalacion local, en NAS o en un servidor Linux. Para una prueba rapida usa `QUICKSTART.md`.

## 1. Preparar El Proyecto

Descarga o descomprime Moneta en una carpeta de trabajo.

Ejemplo en Windows:

```powershell
C:\Moneta\moneta-pro
```

Ejemplo en Linux/NAS:

```bash
/opt/moneta/moneta-pro
```

## 2. Crear Entorno Virtual

Windows:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Linux/NAS:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

## 3. Instalar Dependencias

```bash
pip install -r requirements.txt
```

## 4. Configurar Variables

Copia `.env.example` como `.env`.

Windows:

```powershell
copy .env.example .env
```

Linux/NAS:

```bash
cp .env.example .env
```

Edita `.env` y revisa como minimo:

```env
DJANGO_SECRET_KEY=coloca-una-clave-larga-y-privada
DJANGO_DEBUG=0
DJANGO_ALLOWED_HOSTS=127.0.0.1,localhost,IP_O_DOMINIO
DJANGO_CSRF_TRUSTED_ORIGINS=https://tu-dominio.com
SAAS_EDITION=pro
```

Para uso local sin exponer a Internet puedes dejar `DJANGO_DEBUG=1`, pero no es recomendable para produccion.

## 5. Crear Base De Datos

```bash
python manage.py migrate
```

## 6. Crear Usuario Administrador

```bash
python manage.py createsuperuser
```

Usa una clave fuerte. No uses `admin/admin` en un entorno real.

## 7. Ejecutar El Servidor

Uso local:

```bash
python manage.py runserver 127.0.0.1:8000
```

Uso dentro de una red local:

```bash
python manage.py runserver 0.0.0.0:8000
```

Acceso desde otra PC:

```text
http://IP_DEL_SERVIDOR:8000/
```

## 8. Recomendacion Para NAS

En un NAS tipo QNAP o servidor Linux, lo ideal es:

- Guardar Moneta en una carpeta fija.
- Usar un usuario dedicado para ejecutar el servicio.
- Mantener `.env` fuera de repositorios publicos.
- Configurar una tarea o servicio para iniciar Moneta automaticamente.
- Usar proxy inverso con HTTPS si sera accesible fuera de la red local.

## 9. Produccion

Antes de exponer Moneta a Internet:

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
- Base de datos respaldada.
- Usuario admin con clave fuerte.

## 10. Actualizaciones

Antes de actualizar:

1. Haz copia de seguridad de `.env`.
2. Haz copia de seguridad de la base de datos.
3. Sustituye archivos del codigo.
4. Ejecuta migraciones:

```bash
python manage.py migrate
```

5. Reinicia el servicio.

## 11. Soporte Guiado

La instalacion guiada es un servicio adicional donde se ayuda al comprador a dejar Moneta funcionando en su PC, NAS o servidor. Puede incluir:

- Revision de requisitos.
- Configuracion de `.env`.
- Migraciones iniciales.
- Creacion de usuario administrador.
- Prueba de acceso local.
- Recomendaciones de seguridad basicas.

No incluye personalizaciones profundas salvo que se acuerden como servicio aparte.
