# Cola de importaciones (Import Queue)

La cola de importaciones es el único camino por el que un movimiento originado
**fuera** de Moneta (un agente, un CSV bancario, un importador) llega al núcleo
financiero. Todo pasa por deduplicación y **aprobación humana**.

```text
Fuente externa
      |
      v
   Agente
      |
      v
  Moneta MCP  (scope draft)
      |
      v
Cola de importaciones  (ImportBatch + TransactionDraft)
      |
      v
 Deduplicación  (external_id normalizado + fingerprint v2)
      |
      v
 Revisión humana  (editar / aprobar / rechazar en la UI)
      |
      v
   Aprobación
      |
      v
 Núcleo financiero  (FinancialTransaction + libro contable)
```

---

## Estados de un borrador

| Estado | Significado |
|--------|-------------|
| `pending` | Esperando revisión humana. |
| `approved` | Aprobado; enlazado a un `FinancialTransaction`. |
| `rejected` | Descartado por la persona revisora. |
| `duplicate` | Coincide con un borrador o movimiento previo. |
| `error` | Falló la validación o el volcado atómico. |

---

## Deduplicación

Un borrador se considera duplicado si coincide por **`external_id` normalizado**
(dentro del mismo `source`) o por **fingerprint v2**.

El fingerprint v2 se calcula sobre:

- usuario,
- `source`,
- comercio normalizado,
- descripción normalizada,
- importe canónico,
- moneda,
- fecha,
- signo / tipo de la transacción.

---

## Garantías

- `raw_metadata` se **sanitiza** (límite de tamaño y profundidad) antes de
  guardarse.
- La creación de borradores es **idempotente** por `external_id`.
- La aprobación es **atómica**: si algo falla, se revierte por completo
  (`rollback`) y el borrador queda en `error`, sin dejar un `FinancialTransaction`
  a medias.
- Un borrador aprobado queda **enlazado** a su `FinancialTransaction`.
- **MCP no aprueba.** El scope `draft` sólo puede crear, editar, listar y
  rechazar borradores. La transición `approved` sólo ocurre desde la interfaz de
  Moneta, con una persona al mando.

---

## En la interfaz

**Importaciones** muestra los borradores agrupados por estado
(`Pendientes`, `Aprobados`, `Rechazados`, `Duplicados`, `Con error`). Para cada
borrador pendiente puedes:

- **Editar**: ajustar cuenta, categoría, importe, fecha o descripción.
- **Aprobar**: convertirlo en un movimiento real.
- **Rechazar**: descartarlo (queda registrado, no se borra).

---

## English summary

The Import Queue is the only path for a transaction that originates **outside**
Moneta (an agent, a bank CSV, an importer) to reach the financial core. Every
item goes through exact + fingerprint-v2 deduplication and **human approval**.

Draft states: `pending`, `approved`, `rejected`, `duplicate`, `error`.

MCP's `draft` scope can create, update, list and reject drafts. It **cannot
approve** — the `approved` transition only happens from the Moneta UI, driven by
a person. Approval is atomic and rolls back fully on any failure.
