# Manual De Uso De Moneta

Version: 2026-05-22  
Producto: Moneta Demo, Lite, Pro y Personal

## Proposito

Este manual explica como usar Moneta en la operacion diaria: iniciar sesion, crear cuentas, registrar movimientos, controlar tarjetas, gestionar facturas, automatizar recurrentes, revisar reportes y exportar informacion.

Moneta esta orientado a usuarios que quieren controlar finanzas personales, flujo de caja, deuda, suscripciones y una base contable simple desde un solo panel.

## Acceso Inicial

1. Abre la URL de tu instalacion, por ejemplo `http://127.0.0.1:8003/`.
2. Escribe tu usuario y clave.
3. Presiona `Entrar`.

En una instalacion demo creada con `seed_demo`:

```text
Usuario: demo
Clave: demo12345
```

En produccion se recomienda cambiar las credenciales antes de exponer el sistema en red.

## Panel Financiero

El dashboard resume el estado general:

- Activos.
- Pasivos.
- Capital.
- Ingresos del mes.
- Gastos del mes.
- Pagos de tarjeta.
- Flujo de caja.
- Tarjetas.
- Proximos pagos.
- Presupuesto por categoria.
- Ultimos movimientos.

Usa esta pantalla para revisar rapidamente si el mes esta sano o si hay alertas de deuda, presupuesto o flujo negativo.

## Cuentas

Las cuentas representan donde se mueve el dinero.

Tipos comunes:

- Efectivo.
- Banco.
- Cuenta corriente.
- Ahorro.
- Inversion.
- Tarjeta de credito.
- Prestamo.
- Cuenta por cobrar.
- Cuenta por pagar.
- Capital.

Para crear una cuenta:

1. Entra a `Configuracion`.
2. Presiona `Crear cuenta`.
3. Completa nombre, tipo, moneda, balance inicial y balance actual.
4. Guarda.

Recomendacion: crea primero tus cuentas principales antes de registrar movimientos.

## Categorias

Las categorias clasifican ingresos, gastos o transferencias.

Ejemplos:

- Ingreso: Nomina, Consultoria, Cobros.
- Gasto: Supermercado, Transporte, Software, Salud.
- Transferencia: Movimiento entre cuentas propias.

Reglas:

- Un gasto debe usar categoria de gasto.
- Un ingreso debe usar categoria de ingreso.
- Los recurrentes y suscripciones normalmente usan categorias de gasto.

## Movimientos

Los movimientos registran entradas, salidas y transferencias.

Tipos:

- Ingreso.
- Gasto.
- Transferencia.
- Pago de tarjeta.
- Cobro.

Para registrar un movimiento:

1. Entra a `Movimientos`.
2. Presiona `Nuevo movimiento`.
3. Selecciona tipo, cuenta, categoria, monto y fecha.
4. Para transferencias, selecciona cuenta destino.
5. Para pago de tarjeta, selecciona la tarjeta relacionada.
6. Guarda.

Estados:

- Pendiente: no afecta saldos.
- Confirmado: afecta saldos y contabilidad.
- Anulado: no afecta saldos.

## Tarjetas De Credito

Las tarjetas ayudan a controlar limite, deuda, disponible, intereses y pago recomendado.

Antes de crear una tarjeta:

1. Crea una cuenta de tipo `Tarjeta de credito`.
2. Luego entra a `Tarjetas`.
3. Presiona `Nueva tarjeta`.
4. Completa limite, deuda, tasa anual o tasa mensual, dias de corte y pago.

Campos importantes:

- Limite: credito aprobado.
- Deuda actual: monto usado.
- Tasa anual: interes anual.
- Tasa mensual estado: si el banco muestra una tasa mensual.
- Saldo estado: saldo exacto del corte.
- Pago minimo estado: pago minimo indicado por el banco.
- Pago contado estado: monto para no generar intereses.

Moneta calcula:

- Porcentaje de utilizacion.
- Credito disponible.
- Interes mensual estimado.
- FECI cuando aplica.
- Pago minimo.
- Pago recomendado.

## Facturas

Las facturas pueden ser emitidas o recibidas.

Para crear una factura:

1. Entra a `Facturas`.
2. Presiona `Nueva factura`.
3. Selecciona tipo: emitida o recibida.
4. Escribe numero, contacto, fechas, subtotal, impuesto y estado.
5. Guarda.

Estados:

- Borrador.
- Pendiente.
- Pagada.
- Vencida.
- Anulada.

Moneta marca como vencidas las facturas pendientes cuya fecha de vencimiento ya paso.

## Pagos Recurrentes

Los recurrentes sirven para gastos o ingresos repetitivos.

Ejemplos:

- Alquiler.
- Salario.
- Seguro.
- Prestamo.
- Servicios.

Para crear un recurrente:

1. Entra a `Recurrentes`.
2. Presiona `Nuevo recurrente`.
3. Selecciona cuenta, categoria, tipo de movimiento, monto, frecuencia y proxima fecha.
4. Marca `Crear movimiento automaticamente` si quieres automatizarlo.
5. Guarda.

Frecuencias:

- Semanal.
- Quincenal.
- Mensual.
- Trimestral.
- Anual.

El boton `Ejecutar ahora` crea los movimientos vencidos y evita duplicados.

## Suscripciones

Las suscripciones usan la misma base de recurrentes, pero estan separadas para controlar servicios, seguros y cargos periodicos.

Ejemplos:

- Spotify.
- YouTube Premium.
- Netflix.
- Seguro de vida.
- Seguro de salud.
- Software.

En Lite, las suscripciones pueden estar limitadas segun la edicion.

## Libro Contable

El libro contable permite revisar o crear asientos Debe/Haber.

Reglas:

- Cada asiento debe tener al menos dos lineas.
- Una linea no puede tener Debe y Haber al mismo tiempo.
- El total Debe debe ser igual al total Haber.

Moneta tambien crea asientos automaticos para movimientos y facturas confirmadas.

## Reportes

Los reportes muestran:

- Resumen financiero.
- Flujo.
- Presupuestos por categoria.
- Desglose de gastos.
- Facturas.
- Recurrentes.

Usalos para tomar decisiones semanales o mensuales.

## Exportaciones CSV

Segun la edicion, Moneta permite exportar:

- Movimientos.
- Facturas.
- Recurrentes.
- Suscripciones.

Los exports respetan filtros visibles en listas principales cuando aplica.

## Ediciones

- Demo: completa para pruebas.
- Lite: limitada para demo publica o distribucion inicial.
- Pro: completa para entrega comercial.
- Personal: privada para uso local.

Si una opcion no aparece, puede estar deshabilitada por la edicion.

## Buenas Practicas

- Registra cuentas y categorias antes de cargar movimientos.
- Confirma solo movimientos reales.
- Revisa tarjetas cada corte.
- Usa estados de factura correctamente.
- Ejecuta recurrentes semanalmente o programa una tarea.
- Exporta CSV antes de cambios grandes.
- Haz respaldo de `.env` y base de datos.

## Problemas Comunes

No aparece una cuenta en un formulario:

- Verifica que pertenece al usuario actual.
- Verifica que este activa.
- Para tarjetas, primero crea cuenta tipo tarjeta de credito.

No puedo crear recurrente:

- Revisa que la categoria coincida con el tipo de movimiento.
- Revisa que el monto sea mayor que cero.

El login esta bloqueado:

- Espera 15 minutos.
- Verifica que la clave sea correcta.

## Operacion En Produccion

Para una instancia publicada:

```bash
python manage.py migrate
python manage.py createcachetable
python manage.py check --deploy
```

Usa `createcachetable` cuando `DJANGO_CACHE_BACKEND=db`.

## Soporte

Para reportar un problema incluye:

- Pantalla afectada.
- Pasos para reproducir.
- Usuario/edicion.
- Mensaje de error.
- Captura si aplica.
