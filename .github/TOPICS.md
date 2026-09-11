# GitHub — metadata recomendada

Estos valores se configuran en **Settings → General** del repositorio
`kerwilgil/moneta-lite`. No se pueden fijar desde el código; esta lista es la
recomendación curada tras Phase 8.

## Description

> Self-hosted personal finance manager: accounts, expenses, bills, credit cards,
> subscriptions, reports, an Import Queue with deduplication and an MCP server
> for AI agents. Human-approved. Bilingual (ES/EN). SQLite or PostgreSQL. Django.

(≤ 350 caracteres; GitHub recorta a ~350.)

## Website

`https://github.com/kerwilgil/moneta-lite` (o la landing si existe).

## Topics (15)

```
personal-finance
personal-finance-manager
finance-manager
expense-tracker
budget
budgeting
expenses
income-tracking
money-management
django
python
self-hosted
financial-dashboard
mcp
ai-agents
```

### Justificación

| Topic | Motivo |
|-------|--------|
| `personal-finance`, `personal-finance-manager`, `finance-manager` | Categoría principal y sinónimos buscables. |
| `expense-tracker`, `expenses`, `budget`, `budgeting` | Funciones reales (movimientos, presupuesto por categoría). |
| `income-tracking` | Reportes de ingreso y flujo. |
| `money-management`, `financial-dashboard` | Uso y UX principal. |
| `django`, `python` | Stack. |
| `self-hosted` | Modelo de despliegue. |
| `mcp` | Servidor MCP `2026-07-28` incluido. |
| `ai-agents` | Interoperabilidad con agentes (borradores, aprobación humana). |

### Descartados

- `accounting` — el libro contable es un módulo **Pro**; no está en Lite y puede
  inducir a error.
- `windows`, `sqlite`, `postgresql`, `bilingual` — ciertos pero de menor valor de
  descubrimiento; se dejan fuera para no pasar de 15–20 topics. Se pueden añadir
  si quedan huecos.
