# Product Editions

Este proyecto raiz queda como `demo`.

## Ediciones

### Demo
- Uso interno para cambios, pruebas, presentaciones y ajustes.
- Mantiene todos los modulos activos.

### Lite
- Modulos incluidos: dashboard, analisis, movimientos, facturas, tarjetas, suscripciones de seguros privados, ajustes y exportaciones basicas.
- Modulos bloqueados: recurrentes, catalogo completo de suscripciones, libro contable, ingreso neto y exportaciones avanzadas.
- Orientado a una oferta comercial de entrada.

### Pro
- Todos los modulos activos.
- Base comercial completa.

### Personal
- Equivale funcionalmente a `Pro`.
- Pensado para tu instancia privada en PC o NAS.
- Se genera sin base de datos demo ni logs.

## Variables nuevas

Se agregaron variables en `.env` para controlar producto y branding:

- `SAAS_EDITION=demo|lite|pro|personal`
- `SAAS_APP_NAME`
- `SAAS_APP_DESCRIPTION_ES`
- `SAAS_APP_DESCRIPTION_EN`
- `SAAS_APP_FAVICON`
- `SAAS_APP_OG_IMAGE`
- `SAAS_APP_LOGO_LIGHT`
- `SAAS_APP_LOGO_DARK`
- `SAAS_LOGIN_TITLE_ES`
- `SAAS_LOGIN_TITLE_EN`
- `SAAS_LOGIN_DESCRIPTION_ES`
- `SAAS_LOGIN_DESCRIPTION_EN`

## Script de generacion

Usa:

```powershell
.\scripts\create_variant.ps1 -Edition lite
.\scripts\create_variant.ps1 -Edition pro
.\scripts\create_variant.ps1 -Edition personal
```

Por defecto crea las carpetas en `.\variants\`.

Ejemplos:

```powershell
.\scripts\create_variant.ps1 -Edition lite -AppName "Moneta Lite"
.\scripts\create_variant.ps1 -Edition personal -TargetRoot "D:\MisInstancias"
```

## Recomendacion operativa

- `root actual`: demo
- `variants\lite`: producto comercial basico
- `variants\pro`: producto comercial completo
- `variants\personal-clean`: tu uso privado

Si luego quieres publicar en serio, conviene mover cada variante a su propio repositorio o al menos a ramas/versiones separadas despues de estabilizar esta base.
