# GitHub — metadata recomendada

Estos valores se configuran en **Settings → General** del repositorio
`kerwilgil/moneta-lite`. No se pueden fijar desde el código; esta lista es la
recomendación curada para Phase 7 (GH-04).

## Description

> Moneta Lite — self-hosted personal finance dashboard: accounts, transactions,
> credit cards, subscriptions, invoices & reports. Bilingual (ES/EN), dark mode,
> MCP-ready with a human-approval boundary. Django + Python.

## Topics (15)

```
personal-finance
finance-manager
budget
expenses
income-tracking
django
python
self-hosted
financial-dashboard
open-source
windows
bilingual
sqlite
postgresql
mcp
```

### Justificación

| Topic | Motivo |
|-------|--------|
| `personal-finance` / `finance-manager` | Categoría principal. |
| `budget` / `expenses` / `income-tracking` | Módulos reales (presupuesto por categoría, movimientos, reportes de ingreso). |
| `django` / `python` | Stack. |
| `self-hosted` | Modelo de despliegue. |
| `financial-dashboard` | UX principal. |
| `open-source` | Licencia MIT. |
| `windows` | Soporte nativo (`start.bat` / `stop.bat`, guías PowerShell/CMD). |
| `bilingual` | ES (`es-pa`, `es`) + EN. |
| `sqlite` / `postgresql` | Backend por defecto / opción de producción. |
| `mcp` | Servidor MCP `2026-07-28` incluido. |

### Descartados (por ahora)

- `accounting` — el libro contable es un módulo **Pro**; no está en Lite.
- `ai` — la base de IA viene deshabilitada por defecto; `mcp` describe mejor lo
  que Lite realmente expone.
