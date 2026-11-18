# Auditoría técnica de Moneta Lite v0.3.0

Fecha: 2026-11-17 (America/Panama). Decisión: **BLOCKED** para aprobación final
por la separación física Lite/Pro pendiente. Este PR corrige fallos comprobados;
no constituye una certificación exhaustiva ni modifica la release existente.

## Alcance y línea base

- `main`: `5cf885f241609fda70b899c1061a7169e295ed9e`.
- Tag anotado `v0.3.0`: `63b3fd6b6cb5df999a6a72f8822bd336a3e380ca`,
  commit `5770b66cf1a5758397055828b1ba246e29335cfa`.
- Entre el commit de release y `main` solo cambió `.github/FUNDING.yml`.
  No se encontraron workflows ni ejecuciones CI en la línea base. La release
  publicada tiene cero archivos adjuntos; no se alteró su tag ni sus metadatos.
- Línea base local: Python 3.12.14, Django 6.0.10, MCP 2.3.0; 182 pruebas,
  dos errores y cuatro omisiones de PostgreSQL en SQLite. Los dos errores
  dependían de una clave persistente no declarada en pruebas (configuración de
  producción y hash de token entre subprocesos). Se corrigieron las fixtures,
  sin desactivar pruebas ni relajar la validación de secretos.
- Solo clon nuevo, bases sintéticas y PostgreSQL aislado en loopback. No se
  accedió a datos reales ni a instalaciones existentes. La edición privada se
  consultó únicamente en modo lectura para contrastar límites y licencias.
  Este documento contiene evidencia del repositorio público, no material privado.
- Revisión realizada por un único agente, sin revisor independiente.

## Hallazgos corregidos

| Gravedad | Fallo y consecuencia | Corrección / regresión |
|---|---|---|
| Alta | El admin estándar concedía a `staff` con permisos de modelos acceso a cuentas, facturas y demás registros de otros usuarios. | Querysets, relaciones e inlines limitados al propietario; propietario no editable por staff; pruebas de listados, acceso directo y POST falsificado. |
| Media | Guardar o borrar movimientos/facturas en admin omitía los servicios contables, dejando saldos o asientos inconsistentes. | Hooks atómicos para asientos/saldos, incluidos borrados masivos; rollback ante fallo y prueba de crear/editar/borrar. |
| Media | Aprobación de borradores aceptaba una moneda distinta de la cuenta; transferencias/pagos podían cruzar monedas sin conversión. | Comprobación en aprobación y en validación del núcleo; no se inventa tipo de cambio. |
| Media | Lookup e inserción de lotes/borradores concurrentes no formaban una exclusión mutua en PostgreSQL; la unicidad evitaba duplicados pendientes pero podía devolver errores de integridad al reintentar. Orden de locks financiero inconsistente. | Lock de usuario antes del lookup y de filas en importaciones; mismo orden en automatización y borrado. Cuatro pruebas con conexiones independientes y límites de espera. |
| Baja | El servicio de revisión confiaba en el revisor sin comprobar su propiedad. Las vistas y MCP ya filtraban el borrador, por lo que no se comprobó una ruta HTTP de IDOR en este servicio. | Verificación del propietario activo antes y después del lock, incluso en aprobaciones idempotentes y wrappers del modelo. |
| Baja | Borradores incompletos causaban HTTP 500; valores decimales extremos escapaban de la validación. | Error de revisión controlado; borrador pendiente y rollback completo. |
| Baja | No se podían vaciar destino/categoría al editar. Los pagos importados de tarjeta no podían resolver una tarjeta pagada. | Distinción entre omisión y borrado; destino de pago resuelto a tarjeta del mismo propietario. |
| Baja | GET de crear/editar movimientos creaba cuentas auxiliares. | Creación exclusivamente dentro del guardado atómico; regresión de GET sin efectos. |

El superusuario Django sigue siendo administrador confiable de toda la instalación,
como quien controla la base de datos. El aislamiento por usuario se aplica a usuarios
normales y a staff; no pretende aislar al operador de su propia instalación.

## MCP y núcleo financiero

Se conservan exactamente **15 herramientas: 10 read + 5 draft**. La identidad
proviene del token, no de parámetros de usuario. Se prueban tokens revocados,
usuarios inactivos, scopes, intentos de acceso cruzado, límites, auditoría y
transportes stdio/HTTP modernos y legacy. `draft` implica lectura según el contrato
existente. No se añade aprobación, borrado, pago directo ni mutación de saldos a MCP.

La aprobación humana sigue en UI, protegida por sesión y CSRF. Las pruebas cubren
rollback de transacción y asiento, timeout antes de completar, reintento tras fallo,
repetición tras éxito y aprobación concurrente con un único efecto. Los valores
monetarios siguen siendo Decimal de dos posiciones. No se ofrece conversión FX.

SQLite mantiene su modelo de escritor único: no se promete concurrencia equivalente
a PostgreSQL. Un error de bloqueo/timeout puede requerir reintento con el mismo ID.
La cancelación de un cliente después del commit no deshace un movimiento confirmado;
el reintento idempotente consulta el resultado existente.

El rate limiter existente usa la caché Django: locmem limita por proceso y los
backends file/db no garantizan incremento distribuido atómico. Para exposición
multiworker, usar Redis con incremento atómico y un límite de tráfico en el proxy.
No se ha validado aquí un despliegue distribuido Redis/proxy ni se afirma un límite
global estricto con la caché predeterminada.

## Separación Lite/Pro: bloqueo y propuesta

**Bloqueo registrado antes de trasladar o retirar código.** MIT se conserva. No se
copió código ni documentación de la edición privada y no se cambió su licencia.

La tabla pública en `README.md` reserva recurrentes automáticos, catálogo completo,
libro contable, simulación de ingreso neto y exportaciones avanzadas a Pro. Sin
embargo, el árbol MIT contiene implementaciones completas en:

- `finanzas/product.py`: perfiles demo/pro/personal activables; valor por defecto
  demo en `config/settings.py`, distinto del Lite documentado.
- `finanzas/views.py`: CRUD/ejecución de recurrentes, catálogo de servicios,
  `ledger`/`ledger_create`, `net_income`, exportaciones avanzadas.
- `finanzas/automation.py`, servicios de simulación y sus plantillas/rutas/comandos.
- MCP `get_upcoming_bills` consulta también recurrentes que no son suscripciones;
  admin registra los modelos sin una frontera física de edición.

Los gates de vistas por sí solos no constituyen separación comercial: cambiar
`SAAS_EDITION` activa esos módulos. Esta observación se obtiene íntegramente del
código y de la documentación públicos. No se concluye que el código ya publicado
pueda relicenciarse retroactivamente ni que ocultar botones resuelva el problema.

Propuesta para revisión del propietario:

1. Confirmar el manifiesto de funciones legítimas MIT frente a módulos reservados.
2. Preparar en otro cambio la extracción física de rutas, vistas, plantillas,
   comandos y lógica reservada usando únicamente el árbol público como entrada;
   resolver qué partes del cálculo contable son necesarias para saldos Lite.
3. Conservar dashboard, cuentas, movimientos, facturas, tarjetas, seguros,
   suscripciones Lite, reportes, CSV básico, importaciones y las 15 herramientas
   MCP legítimas. No eliminar modelos/tablas que contengan datos existentes.
4. Ajustar backend, admin y MCP a ese manifiesto; demostrar que configurar Pro no
   hace aparecer implementaciones comerciales. Probar instalación y migración
   conservando datos sintéticos de una instalación Lite existente.
5. Revisar procedencia/licencias por módulo y aprobar el resultado antes de
   trasladar código. Full/Personal/Pro permanecen intactos y de solo lectura.

No se ejecuta esta extracción en el PR de correcciones: hace falta una decisión
explícita sobre el manifiesto y la propiedad del código ya publicado.

## Validación

Resultados locales finales: **201 pruebas**, SQLite **OK (8 omitidas por ser
específicas de PostgreSQL)** y PostgreSQL **OK sin omisiones**. Cobertura de
sentencias del código de aplicación (sin tests ni migraciones): **74%**; servicio
de importaciones **83%**, dispatcher MCP **78%**, admin **74%**. No se afirma
cobertura completa de ramas. Las pruebas de concurrencia usan cuatro conexiones
independientes con `lock_timeout=5s` y `statement_timeout=10s`. Se añade
una matriz CI con Python 3.12, 3.13 y 3.14, SQLite y PostgreSQL 18, migraciones,
pruebas, cobertura, comprobaciones de producción, dependencias y Gitleaks.

- Instalación limpia y `seed_demo` en SQLite y PostgreSQL: OK, datos sintéticos.
- `makemigrations --check --dry-run`: sin cambios; no se requieren migraciones.
- `check --deploy --fail-level WARNING` con configuración de producción sintética:
  sin incidencias.
- `pip-audit` sobre requirements base y PostgreSQL resueltos: sin vulnerabilidades
  conocidas; sin cambios mayores de dependencias. Esto no equivale a auditar toda
  versión histórica permitida por los rangos ni futuras publicaciones.
- Gitleaks: 36 commits públicos y árbol actual; un placeholder literal español
  documentado en `INSTALL.md` se clasificó como falso positivo. Allowlist anclada
  exclusivamente a ese texto; escaneo final sin credenciales detectadas. Nunca se
  imprimen valores de hallazgos ni se prueban credenciales contra servicios.
- Tag, versión de aplicación y release v0.3.0 se mantienen. No merge ni publicación
  de nueva versión. La aprobación final continúa bloqueada por Lite/Pro.
