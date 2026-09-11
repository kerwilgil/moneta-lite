# Movimientos

## Qué es

El registro diario de dinero: ingresos, gastos, transferencias, pagos de tarjeta y cobros.

## Para qué sirve

Es la fuente de verdad de Moneta; balances, reportes y Dashboard se calculan desde aquí.

## Campos principales

- **Tipo**: ingreso, gasto, transferencia, pago de tarjeta o cobro.
- **Cuenta** / **Cuenta destino** (la segunda solo en transferencias y pagos de tarjeta).
- **Categoría**: debe coincidir con el tipo.
- **Importe**, **Fecha**, **Estado** (pendiente / confirmado / anulado).

## Acciones

Filtrar por texto, tipo, estado, cuenta, categoría y fechas. Crear, editar y eliminar. Exportar a CSV.

## Ejemplo

Transferencia de 100 de "Banco" a "Ahorro": Banco -100, Ahorro +100, balance total sin cambios.

## Notas

Editar o eliminar un movimiento recalcula los saldos de las cuentas afectadas de forma atómica.

---

Versión corta dentro de la app: **Ayuda** en Moneta. Índice: [README.md](README.md).
