# Moneta MCP

Moneta expone un servidor **MCP (Model Context Protocol)** para que un agente
compatible pueda **leer** tus finanzas y **proponer borradores** de movimientos.
El agente nunca aprueba nada: toda entrada financiera real sigue pasando por la
revisión humana en la interfaz de Moneta.

- Protocolo moderno: **MCP `2026-07-28`** (SDK oficial `mcp` 2.2.x).
- Compatibilidad legacy: `2025-11-25`.
- Transportes: **stdio** y **Streamable HTTP oficial** (`Server.streamable_http_app`).
- Scopes: `read` y `draft`.
- 15 herramientas: 10 de lectura + 5 de borradores.

---

## 1. Frontera de seguridad

El servidor MCP **no incluye** ninguna herramienta para:

- aprobar borradores,
- crear movimientos directos,
- borrar movimientos o cuentas,
- mutar saldos,
- confirmar pagos.

El usuario efectivo siempre se deriva del token (`MCPAccessToken.user`). No se
puede suplantar otro inquilino con `user_id`, `owner_id` ni `tenant_id`.

```text
Fuente externa
      |
      v
   Agente  --->  Moneta MCP  (read / draft)
                     |
                     v
              Cola de importaciones
                     |
                     v
             Revisión humana (UI)
                     |
                     v
                 Aprobación
                     |
                     v
              Núcleo financiero
```

---

## 2. Generar un token

1. Entra en **Configuración → Integraciones → Moneta MCP**.
2. Escribe un nombre (por ejemplo, `Claude Desktop`).
3. Elige los permisos:
   - **Lectura (`read`)**: resúmenes, cuentas, movimientos, categorías…
   - **Borradores (`draft`)**: además, crear lotes y borradores para revisión humana.
4. Pulsa **Generar token**.
5. Copia el token que aparece **una sola vez**. No se vuelve a mostrar y no se
   guarda en texto plano (se almacena como HMAC-SHA256 con *pepper*).

Desde la misma pantalla puedes **regenerar**, **deshabilitar** o **revocar** cada
token, y ver su prefijo, fecha de creación y último uso.

---

## 3. Conexión por stdio (local)

El token se lee de una variable de entorno, nunca de un argumento visible en la
línea de comandos.

```bash
MONETA_MCP_TOKEN=<tu-token> python manage.py moneta_mcp_stdio
```

Ejemplo de configuración para un cliente MCP (ajusta las rutas):

```json
{
  "mcpServers": {
    "moneta": {
      "command": "python",
      "args": ["manage.py", "moneta_mcp_stdio"],
      "cwd": "/ruta/a/moneta",
      "env": { "MONETA_MCP_TOKEN": "<tu-token>" }
    }
  }
}
```

---

## 4. Conexión por Streamable HTTP

El endpoint HTTP es la app ASGI oficial del SDK montada en `/mcp` (no es una
vista de Django). Sírvela con un servidor ASGI:

```bash
uvicorn config.asgi:application --host 127.0.0.1 --port 8001
```

Petición:

```text
POST http://127.0.0.1:8001/mcp/
Authorization: Bearer <tu-token>
```

El endpoint se enlaza a `127.0.0.1` (el SDK activa protección contra
DNS-rebinding). Para exponerlo más allá del loopback, ponlo detrás de un proxy
inverso autenticado con HTTPS.

---

## 5. Herramientas

### Lectura (`read`)

| Herramienta | Descripción |
|-------------|-------------|
| `moneta.get_summary` | Resumen financiero (balance, flujo, deuda). |
| `moneta.list_accounts` | Cuentas del usuario. |
| `moneta.list_transactions` | Movimientos con paginación. |
| `moneta.search_transactions` | Búsqueda de movimientos por texto/filtros. |
| `moneta.get_spending_by_category` | Gasto agrupado por categoría. |
| `moneta.get_income_summary` | Resumen de ingresos. |
| `moneta.get_subscriptions` | Suscripciones activas. |
| `moneta.get_credit_cards` | Tarjetas de crédito y uso. |
| `moneta.get_upcoming_bills` | Próximos vencimientos. |
| `moneta.get_categories` | Catálogo de categorías. |

### Borradores (`draft`)

| Herramienta | Descripción |
|-------------|-------------|
| `moneta.create_import_batch` | Crea un lote de importación. |
| `moneta.create_transaction_draft` | Crea un borrador de movimiento (estado `pending`). |
| `moneta.update_draft` | Edita un borrador pendiente. |
| `moneta.list_pending_drafts` | Lista borradores pendientes. |
| `moneta.reject_draft` | Marca un borrador como rechazado. |

`moneta.approve` **no existe**. La aprobación es exclusivamente humana.

---

## 6. Controles operativos

- **Autenticación por token** (HMAC-SHA256 + *pepper*); el token en claro nunca se
  persiste.
- **Aislamiento por inquilino**: cada consulta se limita al usuario del token.
- **Validación de entrada** y **paginación** obligatoria en los listados.
- **Rate limiting** por herramienta (`settings.MONETA_MCP_RATE_LIMITS`); por
  defecto 120 llamadas/60 s, con límites más estrictos para creación de lotes y
  borradores.
- **Auditoría**: cada llamada queda registrada (`MCPAuditEvent`).
- **Redacción de secretos** en los registros.
- El antiguo flag `--allow-unauthenticated` fue eliminado y no debe reintroducirse.

---

## English summary

Moneta ships an MCP server so a compatible agent can **read** your finances and
**propose transaction drafts**. The agent never approves anything — every real
financial entry still goes through human review in the Moneta UI.

- Modern protocol **MCP `2026-07-28`** (official `mcp` 2.2.x SDK); legacy
  `2025-11-25` also supported.
- Transports: **stdio** and the **official Streamable HTTP** ASGI app mounted at
  `/mcp`.
- Scopes `read` and `draft`; 15 tools (10 read + 5 draft).
- No `approve`, no direct transaction creation, no delete, no balance mutation,
  no payment confirmation.
- Generate a token in **Settings → Integrations → Moneta MCP**; the raw token is
  shown once and stored only as an HMAC-SHA256 hash.
- stdio: `MONETA_MCP_TOKEN=<token> python manage.py moneta_mcp_stdio`
- HTTP: `POST http://127.0.0.1:8001/mcp/` with `Authorization: Bearer <token>`.

See also: [`import-queue.md`](import-queue.md).
