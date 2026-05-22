# Guia Para Desarrolladores

Esta guia explica como modificar Moneta sin romper flujos financieros, ediciones o paquetes de entrega.

## Ambiente Local

Requisitos:

- Python 3.10 o superior.
- Entorno virtual `.venv`.
- Dependencias de `requirements.txt`.

Comandos base:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
python manage.py migrate
python manage.py seed_demo
python manage.py runserver 127.0.0.1:8003
```

Usuario demo local si usas `seed_demo`:

```text
usuario: demo
clave: demo12345
```

No uses `seed_demo` en produccion salvo que entiendas el riesgo y pases `--allow-production`.

## Comandos De Verificacion

Antes de commit:

```powershell
python manage.py test finanzas
python manage.py check
python manage.py makemigrations --check --dry-run
```

Antes de publicar:

```powershell
python manage.py check --deploy
python manage.py collectstatic
```

Para verificar automatizaciones:

```powershell
python manage.py run_recurring --username demo --scope all
```

## Convenciones De Codigo

- Mantener la logica financiera en `services.py`, `accounting.py` o `automation.py`, no directamente en templates.
- Mantener validaciones de entrada en `forms.py`.
- Usar `Decimal` para dinero y porcentajes.
- Filtrar siempre por `request.user` o por `user` recibido.
- Usar `select_related`, `prefetch_related` y agregaciones cuando una vista liste muchos registros.
- Agregar tests cuando cambien saldos, asientos, permisos, ediciones o exportaciones.

## Como Agregar Una Pantalla

1. Crear o reutilizar formulario en `finanzas/forms.py`.
2. Agregar vista en `finanzas/views.py`.
3. Registrar URL en `finanzas/urls.py`.
4. Crear plantilla en `templates/finanzas/`.
5. Si el modulo depende de edicion, agregar feature en `finanzas/product.py` y usar `@require_feature`.
6. Agregar smoke test de acceso y flujo principal.

## Como Agregar Un Campo

1. Editar modelo en `finanzas/models.py`.
2. Ejecutar `python manage.py makemigrations`.
3. Revisar migracion generada.
4. Exponer campo en formulario si el usuario debe editarlo.
5. Actualizar vistas, plantillas, admin y exportaciones si aplica.
6. Agregar test de validacion o render segun riesgo.

## Como Cambiar Calculos De Saldos

Revisar primero:

- `finanzas/accounting.py`
- `finanzas/models.py`
- `finanzas/tests.py`

Reglas:

- Solo movimientos `cleared` afectan saldos.
- `expense` reduce cuentas normales y aumenta cuentas de tarjeta.
- `income` y `collection` aumentan cuentas normales y reducen cuentas de tarjeta.
- `transfer` resta origen y suma destino.
- `card_payment` resta cuenta pagadora y reduce deuda de tarjeta.
- Las inversiones preservan balance manual si no fueron tocadas por movimientos.

Despues de cambiar saldos:

```powershell
python manage.py test finanzas
python manage.py shell -c "from django.contrib.auth import get_user_model; from finanzas.accounting import rebuild_account_balances; u=get_user_model().objects.get(username='demo'); rebuild_account_balances(u)"
```

## Como Cambiar Asientos Contables

Revisar:

- `sync_transaction_journal`
- `sync_invoice_journal`
- `delete_transaction_journal`
- `delete_invoice_journal`

Cada asiento automatico debe quedar balanceado: total Debe igual a total Haber.

No cambies nombres de cuentas de sistema sin considerar datos existentes:

- `Resultado ingresos`
- `Resultado gastos`
- `Cuenta puente transferencias`
- `Cuentas por cobrar`
- `Cuentas por pagar`

## Como Cambiar Recurrentes O Suscripciones

Revisar:

- `finanzas/automation.py`
- `RecurringPaymentForm`
- `recurring_list`
- `subscription_list`

Reglas:

- Un recurrente automatico crea movimientos solo si esta activo y vencido.
- No se duplica un movimiento si ya existe uno no anulado para la misma fecha y recurrente.
- `max_cycles` evita loops infinitos si una fecha queda demasiado atrasada.
- Si se crean movimientos, se reconstruyen balances.

## Como Cambiar Ediciones

Revisar:

- `finanzas/product.py`
- navegacion en `templates/base.html`
- tests `LiteEditionGateTests`
- scripts de variantes y releases

Si agregas una feature:

1. Define el nombre en `EDITION_FEATURES`.
2. Decide si Lite la recibe.
3. Protege vistas con `@require_feature`.
4. Ajusta menus para ocultar o mostrar enlaces.
5. Agrega tests para Lite y Pro/Demo.

## Como Cambiar Exportaciones CSV

Revisar funciones al final de `finanzas/views.py`.

Reglas:

- Mantener `EXPORT_ROW_LIMIT`.
- Mantener `sanitize_csv_cell` para valores que empiezan con `=`, `+`, `-` o `@`.
- Usar `select_related` cuando se exportan relaciones.

## Como Cambiar Branding

Variables `.env`:

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

El contexto se arma en `finanzas/context_processors.py`.

## Checklist Antes De Entregar

- Tests pasan.
- `check` pasa.
- `check --deploy` pasa con `.env` real de produccion.
- Migraciones aplican en base limpia.
- Usuario admin no usa claves por defecto.
- Variantes sincronizadas con `scripts/sync_variants.ps1`.
- ZIPs generados con `scripts/package_releases.ps1`.
- `CHANGELOG.md` actualizado.
