# Roadmap funcional

## Fase 1: Base contable

- Crear catalogo de cuentas: efectivo, bancos, ahorro, inversiones, tarjetas, prestamos, cuentas por cobrar, cuentas por pagar y capital.
- Registrar movimientos financieros simples.
- Generar asientos contables con Debe/Haber.
- Validar que cada asiento tenga Debe igual a Haber.
- Calcular activos, pasivos y capital neto.

## Fase 2: Operacion diaria

- Gastos y consumos por categoria.
- Ingresos y cobros.
- Pagos recurrentes.
- Suscripciones y afiliaciones.
- Facturas emitidas y recibidas.
- Exportacion CSV.
- Control de presupuesto por categoria (limites mensuales, alertas y uso porcentual).
- Ejecucion automatica de recurrentes/suscripciones con registro de estado.
- Programacion automatica de `run_recurring` en Task Scheduler (Windows).

Estado actual: Fase 2 implementada y validada en flujo manual end-to-end.

## Fase 3: Deuda y tarjetas

- Registrar limite de credito, deuda, tasa anual, fecha de corte y fecha limite.
- Calcular pago minimo.
- Calcular pago recomendado.
- Alertar cuando el uso supere 50%, 70% y 90%.
- Proyectar cuotas proximas y costo estimado de intereses.

## Fase 4: Reporteria

- Libro diario.
- Libro mayor.
- Balance general.
- Estado de resultados.
- Flujo de caja mensual.
- Gastos por categoria.
- Suscripciones anualizadas.
- Exportaciones PDF, Excel y CSV.

## Fase 5: Consejos financieros

- Separar activos y pasivos.
- Medir flujo de caja antes de asumir compromisos.
- Proteger capital y liquidez.
- Detectar deuda cara.
- Detectar gastos recurrentes silenciosos.
- Comparar gasto real contra presupuesto.
- Generar recomendaciones educativas, no asesoria financiera personalizada.
