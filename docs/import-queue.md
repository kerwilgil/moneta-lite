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
  (`rollback`) y el borrador sigue `pending` para corregirlo o reintentar, sin dejar un `FinancialTransaction`
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

La moneda del borrador debe coincidir con la cuenta. Las transferencias y los
pagos de tarjeta requieren cuentas de la misma moneda; no hay conversión de
divisas automática. Para `card_payment`, selecciona la **cuenta de la tarjeta
pagada** como cuenta destino (`destination_account_id` en MCP). La aprobación
resuelve la tarjeta del propietario y actualiza su deuda junto con el saldo de
la cuenta de origen. Sin tarjeta válida el borrador permanece pendiente.

En PostgreSQL, las operaciones de importación se serializan por usuario antes
de comprobar duplicados o bloquear filas. Una repetición MCP con el mismo
identificador devuelve el borrador existente. SQLite conserva sus restricciones
de escritor único: ante un bloqueo o timeout, reintenta con el mismo identificador;
un fallo no confirma parcialmente el movimiento.

---

## English summary

The Import Queue is the only path for a transaction that originates **outside**
Moneta (an agent, a bank CSV, an importer) to reach the financial core. Every
item goes through exact + fingerprint-v2 deduplication and **human approval**.

Draft states: `pending`, `approved`, `rejected`, `duplicate`, `error`.

MCP's `draft` scope can create, update, list and reject drafts. It **cannot
approve** — the `approved` transition only happens from the Moneta UI, driven by
a person. Approval is atomic and rolls back fully on any failure.
