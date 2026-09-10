# Moneta MCP

## Qué es

Permite que clientes compatibles con MCP consulten tu información y creen borradores para revisión humana.

## Qué NO pueden hacer los agentes

Aprobar transacciones, cambiar balances, borrar transacciones o cuentas, confirmar pagos.

## Scopes

- `read`: 10 herramientas de consulta.
- `draft`: además, 5 herramientas para crear/editar/listar/rechazar borradores.

## Cómo usarlo

Genera un token en Integraciones -> Moneta MCP (se muestra una vez, se guarda como hash) y conecta por stdio o Streamable HTTP.

## Notas

Protocolo moderno 2026-07-28. Token limitado a tu usuario. Detalle, transportes y ejemplos en [`../mcp.md`](../mcp.md).

---

Versión corta dentro de la app: **Ayuda** en Moneta. Índice: [README.md](README.md).
