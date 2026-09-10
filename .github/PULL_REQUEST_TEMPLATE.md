## Qué cambia / What changes

<!-- Resumen breve. Linked issue: Closes #___ -->

## Checklist

- [ ] `python manage.py test` pasa (0 fallos, 0 errores).
- [ ] `python manage.py check` sin problemas.
- [ ] `python manage.py makemigrations --check --dry-run` → sin cambios pendientes.
- [ ] `python manage.py secret_scan` → limpio (sin tokens ni claves).
- [ ] No se rompe la frontera Lite (sin módulos Pro) ni la frontera MCP (sin `approve`).
- [ ] Documentación actualizada si aplica.
