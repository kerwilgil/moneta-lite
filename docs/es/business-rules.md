# Reglas De Negocio

Este documento resume las reglas financieras que Moneta implementa. Usalo como referencia antes de cambiar formularios, servicios o saldos.

## Usuarios Y Aislamiento

Todos los registros financieros relevantes pertenecen a un usuario. Una vista o formulario no debe permitir seleccionar cuentas, categorias, tarjetas, facturas o recurrentes de otro usuario.

Regla practica:

- En queries de vistas: filtrar por `request.user`.
- En forms: pasar `user=request.user`.
- En servicios: recibir `user` y filtrar con ese usuario.

## Cuentas

`Account` representa efectivo, banco, ahorro, inversion, tarjeta, prestamo, cuentas por cobrar/pagar y capital.

Campos clave:

- `opening_balance`: saldo base.
- `current_balance`: saldo operativo actual.
- `account_type`: define como se interpreta el saldo.

La restriccion de nombre es case-insensitive por usuario. No deben existir dos cuentas del mismo usuario llamadas igual con distinta capitalizacion.

## Categorias

`Category` clasifica movimientos como ingreso, gasto o transferencia.

Reglas:

- Una categoria de gasto no debe usarse para ingreso.
- Una categoria de ingreso no debe usarse para gasto.
- Pagos recurrentes y suscripciones usan categorias de gasto.
- `monthly_limit` debe ser mayor que cero si se define.
- El nombre es unico por usuario, tipo y capitalizacion case-insensitive.

## Movimientos

`FinancialTransaction` es el registro principal de dinero.

Tipos:

- `income`: ingreso.
- `collection`: cobro.
- `expense`: gasto.
- `transfer`: transferencia entre cuentas.
- `card_payment`: pago de tarjeta.

Estados:

- `pending`: no afecta saldos.
- `cleared`: afecta saldos y genera asiento.
- `void`: no afecta saldos y elimina asiento automatico.

Reglas de validacion:

- `amount` debe ser mayor que cero.
- Transferencia necesita cuenta destino.
- Cuenta origen y destino no pueden ser iguales.
- Pago de tarjeta necesita tarjeta relacionada.
- Categoria debe coincidir con el tipo del movimiento.

Reglas de saldo:

- Ingreso/cobro en cuenta normal aumenta saldo.
- Ingreso/cobro en tarjeta reduce deuda.
- Gasto en cuenta normal reduce saldo.
- Gasto en tarjeta aumenta deuda.
- Transferencia reduce origen y aumenta destino.
- Pago de tarjeta reduce cuenta pagadora y reduce deuda de tarjeta.

## Tarjetas De Credito

`CreditCard` tiene una cuenta asociada de tipo `credit_card`.

Campos importantes:

- `credit_limit`: limite aprobado.
- `current_debt`: deuda actual.
- `annual_interest_rate`: tasa anual.
- `monthly_service_rate`: tasa mensual del estado si existe.
- `statement_balance`: saldo exacto del estado.
- `statement_minimum_payment`: pago minimo exacto del estado.
- `statement_cash_payment`: pago contado exacto del estado.
- `global_limit`, `global_available`, `global_balance`: valores globales si el banco los muestra.
- `statement_day`: dia de corte, 1 a 31.
- `payment_due_day`: dia limite, 1 a 31.
- `minimum_payment_percent`: porcentaje usado si no se capturo pago minimo exacto.

Reglas:

- Limite debe ser mayor que cero.
- Deuda, tasas y valores de estado no deben ser negativos.
- Dia de corte y dia de pago deben estar entre 1 y 31.
- Si existe valor global, se usa antes del calculado.
- Si existe saldo de estado, se usa como base de interes.
- FECI aplica cuando la base de interes supera 5000.00.
- `MONETA_FECI_ANNUAL_RATE_PERCENT` controla la tasa anual FECI y cae a 1.00 si esta mal configurada.

## Facturas

`Invoice` registra facturas emitidas o recibidas.

Reglas:

- `subtotal` debe ser mayor que cero.
- `tax` no puede ser negativo.
- `total = subtotal + tax`.
- Numero es unico por usuario y tipo de factura.
- Facturas pendientes con vencimiento menor que hoy pasan a `overdue`.
- Facturas `draft` y `void` no deben mantener asiento automatico.

Asientos:

- Factura emitida: debita cuentas por cobrar y acredita resultado ingresos.
- Factura recibida: debita resultado gastos y acredita cuentas por pagar.

## Libro Contable

`JournalEntry` y `JournalLine` representan asientos Debe/Haber.

Reglas:

- Un asiento manual necesita al menos dos lineas.
- Una linea no puede tener Debe y Haber al mismo tiempo.
- Una linea debe tener Debe o Haber.
- Total Debe debe ser igual a total Haber.
- Asientos automaticos se recrean al editar movimientos o facturas.

## Recurrentes Y Suscripciones

`RecurringPayment` soporta pagos recurrentes y suscripciones con la misma tabla.

Reglas:

- `amount` debe ser mayor que cero.
- Categoria debe ser de gasto.
- `is_subscription=True` marca suscripciones.
- `auto_create_transaction=True` permite crear movimientos automaticos.
- Solo registros activos se ejecutan.
- La ejecucion no duplica movimientos si ya existe uno no anulado para la misma fecha.
- Frecuencias soportadas: semanal, quincenal, mensual, trimestral y anual.

Proyeccion mensual:

- Semanal: monto x 4.
- Quincenal: monto x 2.
- Mensual: monto x 1.
- Trimestral: monto / 3.
- Anual: monto / 12.

## Dashboard Y Consejos

El dashboard resume:

- Activos.
- Pasivos.
- Capital.
- Ingresos del mes.
- Gastos del mes.
- Pagos de tarjeta.
- Flujo de caja.
- Proximos pagos.
- Tarjetas.
- Presupuestos por categoria.
- Desglose de gastos.

Consejos actuales:

- Flujo negativo cuando gastos superan ingresos.
- Uso alto de tarjeta desde 70%.
- Vigilancia de tarjeta desde 50%.
- Suscripciones elevadas si superan 15% de gastos.
- Categorias excedidas o cerca del limite.

## Exportaciones

CSV disponible por edicion:

- Lite: exportaciones basicas.
- Pro/Demo/Personal: exportaciones basicas y avanzadas.

Reglas:

- Limite de filas: `EXPORT_ROW_LIMIT`.
- Celdas peligrosas se prefijan con `'` para evitar formula injection.

## Produccion

Reglas obligatorias:

- `DJANGO_DEBUG=0`.
- `DJANGO_SECRET_KEY` unica y privada.
- `DJANGO_ALLOWED_HOSTS` con dominio/IP real.
- `DJANGO_CSRF_TRUSTED_ORIGINS` con origen HTTPS real.
- HTTPS activo antes de forzar redirect y HSTS.
- No usar `admin/admin`.
- No subir `.env`, bases SQLite ni logs.
