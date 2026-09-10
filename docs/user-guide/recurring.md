# Pagos recurrentes (Pro)

## Qué es

Pagos que se repiten (alquiler, cuotas, nómina) que Moneta puede convertir en movimientos automáticamente.

## Campos principales

- Frecuencia y próxima fecha de vencimiento.
- Cuenta, categoría e importe.
- "Crear movimiento automático": si está activo, la ejecución genera el movimiento.

## Acciones

Ejecutar los vencimientos pendientes desde la pantalla o por CLI: `python manage.py run_recurring --scope all`.

## Notas

Módulo de la edición Pro. La ejecución es idempotente, acotada por lote y nunca duplica una ocurrencia ya creada para la misma fecha.

---

Versión corta dentro de la app: **Ayuda** en Moneta. Índice: [README.md](README.md).
