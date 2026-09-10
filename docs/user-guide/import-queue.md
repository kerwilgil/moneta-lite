# Cola de importaciones

## Qué es

Los elementos de Importaciones son propuestas de movimientos, no movimientos reales.

## De dónde vienen

Desde integraciones, archivos o agentes de IA conectados por MCP.

## Flujo

```
Fuente externa -> Agente -> Moneta MCP -> Cola de importaciones
  -> Deduplicación -> Revisión humana -> Aprobación -> Núcleo financiero
```

## Estados

`pending`, `approved`, `rejected`, `duplicate`, `error`.

## Notas

La deduplicación combina el identificador externo normalizado y una huella v2 (usuario, origen, comercio, descripción, importe, moneda, fecha, signo). La aprobación es atómica con rollback total. **MCP no aprueba.** Detalle completo en [`../import-queue.md`](../import-queue.md).

---

Versión corta dentro de la app: **Ayuda** en Moneta. Índice: [README.md](README.md).
