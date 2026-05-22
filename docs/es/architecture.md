# Arquitectura De Moneta

Este documento explica como esta organizado Moneta para que un desarrollador pueda ubicar cambios sin leer todo el proyecto desde cero.

## Vision General

Moneta es una aplicacion Django de finanzas personales y control contable. La app principal es `finanzas`; `config` contiene configuracion Django, rutas globales y despliegue WSGI/ASGI.

Flujo basico:

1. El usuario entra por una URL declarada en `finanzas/urls.py`.
2. La vista en `finanzas/views.py` aplica filtros, permisos de edicion y llama formularios o servicios.
3. Los formularios en `finanzas/forms.py` validan datos de entrada por usuario.
4. Los modelos en `finanzas/models.py` persisten cuentas, movimientos, facturas, tarjetas y asientos.
5. Las reglas agregadas viven en `finanzas/services.py`, `finanzas/accounting.py` y `finanzas/automation.py`.
6. Las plantillas en `templates/finanzas/` renderizan el panel.
7. Archivos estaticos en `static/` dan estilos, JavaScript y marcas visuales.

## Modulos Principales

`finanzas/models.py`

Define el esquema de datos. Es el punto de referencia para saber que informacion existe y como se relaciona:

- `Account`: cuentas financieras por usuario.
- `Category`: categorias de ingreso, gasto o transferencia.
- `FinancialTransaction`: movimientos de dinero.
- `JournalEntry` y `JournalLine`: libro contable Debe/Haber.
- `RecurringPayment`: pagos recurrentes y suscripciones.
- `Invoice`: facturas emitidas o recibidas.
- `CreditCard`: calculos de tarjeta, deuda, disponible, intereses, FECI y pagos.
- `FinancialAdviceRule`: base para reglas de consejo financiero configurables.

`finanzas/forms.py`

Valida la entrada de usuario antes de crear o editar registros. La clase base `UserScopedModelForm` restringe querysets por usuario para evitar que un usuario seleccione objetos ajenos.

`finanzas/views.py`

Contiene las pantallas y acciones HTTP. Actualmente tambien incluye helpers de UI, filtros, exportaciones y catalogos de suscripciones. Si una pantalla cambia, revisa aqui y su plantilla relacionada.

`finanzas/services.py`

Agrupa calculos de dashboard, reportes y consejos. Es el lugar correcto para reglas de consulta o agregacion que no dependen directamente del request HTTP.

`finanzas/accounting.py`

Mantiene saldos y asientos contables automaticos. Es critico para cambios en movimientos, facturas, tarjetas y transferencias.

`finanzas/automation.py`

Procesa pagos recurrentes y suscripciones. Crea movimientos automaticos, evita duplicados por fecha y actualiza el proximo vencimiento.

`finanzas/product.py`

Controla ediciones y features: demo, lite, pro y personal. Las vistas usan `@require_feature` para bloquear modulos no disponibles.

## Capas De Responsabilidad

Modelos:

- Deben contener estructura de datos, propiedades de calculo simples y restricciones.
- No deben depender de `request`.

Forms:

- Deben validar datos ingresados por el usuario.
- Deben filtrar opciones por `user`.
- No deben hacer calculos globales de dashboard.

Services:

- Deben calcular resumenes, series, presupuestos y recomendaciones.
- Deben evitar N+1 queries en paneles o reportes.

Accounting:

- Debe actualizar saldos y asientos.
- Debe ser transaccional cuando toca varias tablas.

Views:

- Deben coordinar request, formulario, servicio y respuesta.
- Deben mantener autorizacion por usuario.

Templates:

- Deben presentar datos ya preparados por views/services.
- No deben contener logica financiera compleja.

## Datos Y Relaciones Clave

Cada objeto financiero principal pertenece a un `user`. Esa regla permite que una misma instalacion tenga varios usuarios aislados.

`Account.current_balance` se recalcula desde movimientos confirmados, salvo tipos manuales como inversiones. Las tarjetas tienen una cuenta asociada uno-a-uno; su deuda se sincroniza con el balance de esa cuenta.

`FinancialTransaction.status` determina si un movimiento afecta saldos y asientos. Solo `cleared` debe impactar saldos.

`Invoice.status` determina si hay asiento automatico. `draft` y `void` eliminan el asiento asociado.

`RecurringPayment.is_subscription` separa pagos recurrentes generales de suscripciones, aunque comparten tabla y logica de automatizacion.

## Flujo De Movimiento

1. La vista `transaction_create` o `transaction_edit` usa `TransactionForm`.
2. El formulario valida monto positivo, tipo, categoria, cuenta destino y tarjeta relacionada.
3. Al guardar, la vista llama `sync_transaction_journal`.
4. Luego llama `rebuild_account_balances`.
5. El listado y dashboard leen el estado actualizado.

## Flujo De Factura

1. La vista `invoice_create` o `invoice_edit` usa `InvoiceForm`.
2. El formulario valida subtotal positivo e impuesto no negativo.
3. Al guardar, la vista llama `sync_invoice_journal`.
4. `mark_overdue_invoices` cambia facturas pendientes vencidas a `overdue`.

## Flujo De Recurrentes

1. El usuario crea un pago recurrente o suscripcion.
2. `execute_due_recurrings_for_user` busca registros activos, automaticos y vencidos.
3. Por cada vencimiento crea un movimiento de gasto si no existe uno para esa fecha.
4. Actualiza `next_due_date` segun frecuencia.
5. Si crea movimientos, reconstruye balances.

## Ediciones

Las ediciones se controlan con `SAAS_EDITION` y `APP_FEATURES`.

- `demo`, `pro` y `personal`: modulos completos.
- `lite`: tarjetas, facturas, transacciones, reportes, suscripciones limitadas y exports basicos.

Si agregas una nueva pantalla, define su feature en `finanzas/product.py` y protege la vista con `@require_feature` si aplica.

## Variantes Y Releases

El repo privado es la fuente principal. Las carpetas `variants/` e `instances/` se regeneran o sincronizan desde el proyecto base y estan ignoradas por Git.

- `scripts/create_variant.ps1`: crea una variante nueva.
- `scripts/sync_variants.ps1`: copia cambios del proyecto base a variantes existentes.
- `scripts/package_releases.ps1`: genera ZIPs publicables en `releases/`.

## Puntos De Riesgo

- Cambios en `accounting.py` pueden alterar saldos historicos.
- Cambios en `models.py` requieren migraciones.
- Cambios en `product.py` pueden exponer o bloquear modulos por edicion.
- Cambios en exportaciones CSV deben conservar `sanitize_csv_cell` para evitar formula injection.
- Cambios en `create_variant.ps1` pueden afectar entregas pagadas.

## Donde Mirar Primero

- Nueva regla financiera: `services.py` o `accounting.py`.
- Nueva validacion de usuario: `forms.py`.
- Nueva columna o relacion: `models.py` + migracion + tests.
- Nueva pantalla: `urls.py`, `views.py`, plantilla y feature gate.
- Nuevo modulo por edicion: `product.py`, templates de navegacion y tests Lite/Pro.
