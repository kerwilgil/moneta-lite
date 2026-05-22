# Proceso De Release

Este documento describe como preparar, validar y empaquetar Moneta para entrega interna, publica o comercial.

## Tipos De Entrega

Demo:

- Paquete completo para pruebas y presentaciones.
- Usa licencia de evaluacion.

Lite:

- Paquete publico o gratuito.
- Usa licencia MIT.
- Tiene features limitadas.

Pro:

- Paquete comercial completo.
- Usa licencia comercial.
- No debe redistribuirse sin permiso.

Personal:

- Paquete privado para uso local.
- Usa licencia privada.

## Flujo Recomendado

1. Trabajar cambios en el repo base privado.
2. Ejecutar tests y checks.
3. Actualizar documentacion y `CHANGELOG.md`.
4. Sincronizar variantes.
5. Probar una variante si el cambio afecta ediciones.
6. Generar ZIPs.
7. Subir commit y tags si aplica.
8. Entregar ZIP correcto segun cliente/uso.

## Verificacion Antes De Release

```powershell
python manage.py test finanzas
python manage.py check
python manage.py makemigrations --check --dry-run
```

Para produccion, con `.env` real:

```powershell
python manage.py check --deploy
python manage.py collectstatic
```

## Sincronizar Variantes

```powershell
.\scripts\sync_variants.ps1
```

Esto copia cambios del proyecto base hacia:

- `variants\lite`
- `variants\pro`
- `variants\personal-clean`
- `instances\personal-live`

Las variantes estan ignoradas por Git. No esperes verlas en `git status`.

## Crear Una Variante Desde Cero

```powershell
.\scripts\create_variant.ps1 -Edition lite -Force
.\scripts\create_variant.ps1 -Edition pro -Force
.\scripts\create_variant.ps1 -Edition personal -Force
```

El script:

- Copia el proyecto sin `.venv`, `.env`, `db.sqlite3`, logs ni releases.
- Genera `DJANGO_SECRET_KEY`.
- Genera clave inicial si no se pasa `-AdminPassword`.
- Ajusta `SAAS_EDITION`.
- Copia licencia por edicion.
- Ejecuta migraciones si existe `.venv`.
- Crea usuario admin inicial.

Para entregar una variante comercial, se recomienda pasar una clave controlada:

```powershell
.\scripts\create_variant.ps1 -Edition pro -AdminUsername admin -AdminPassword "clave-fuerte" -Force
```

## Generar ZIPs

```powershell
.\scripts\package_releases.ps1
```

Salida:

- `releases\demo.zip`
- `releases\lite.zip`
- `releases\pro.zip`
- `releases\personal-clean.zip`

El script excluye:

- `.env`
- bases SQLite
- logs
- `.venv`
- `instances`
- `releases`
- `_publish`
- `staticfiles`
- archivos `.zip`

## Checklist De Contenido

Cada ZIP debe incluir:

- `config/`
- `finanzas/`
- `static/`
- `templates/`
- `.env.example`
- `README.md`
- `QUICKSTART.md`
- `INSTALL.md`
- `FAQ.md`
- `SUPPORT.md`
- `CHANGELOG.md`
- `requirements.txt`
- `manage.py`
- `LICENSE`

Demo tambien puede incluir:

- `docs/`
- `scripts/`
- `security_best_practices_report.md`

## Publicar Cambios En Git

Flujo normal:

```powershell
git status --short
git add .
git commit -m "Mensaje claro"
git push
```

No subir:

- `.env`
- `db.sqlite3`
- `logs/`
- `releases/`
- `variants/`
- `instances/`

Esos paths ya estan en `.gitignore`.

## Versionado

Actualizar `CHANGELOG.md` en cada entrega significativa.

Formato recomendado:

```text
## 0.1.X - YYYY-MM-DD

- Cambio importante.
- Fix relevante.
- Nota de seguridad o release.
```

## Revision De Seguridad Antes De Vender

Verificar:

- `.env.example` no contiene secretos reales.
- `DJANGO_DEBUG=0` en produccion.
- `DJANGO_SECRET_KEY` no es placeholder.
- Usuario admin tiene clave fuerte.
- `check --deploy` no muestra advertencias criticas.
- CSV conserva sanitizacion.
- Feature gates de Lite bloquean modulos Pro.
- No hay bases de datos ni logs dentro del ZIP.

## Entrega Al Cliente

Para Pro:

1. Entregar `pro.zip`.
2. Adjuntar instrucciones de `INSTALL.md`.
3. Informar que debe configurar `.env`.
4. Confirmar licencia comercial.
5. Si hay instalacion guiada, crear usuario admin con clave fuerte y documentar credenciales de forma segura.

Para Lite:

1. Entregar o publicar `lite.zip`.
2. Confirmar que `SAAS_EDITION=lite`.
3. No incluir enlaces privados ni datos demo sensibles.

Para Personal:

1. Entregar `personal-clean.zip`.
2. Recomendar uso local o NAS.
3. Recomendar backups de `.env` y base de datos.
