# SQLite y PostgreSQL

## Qué es

Moneta guarda tus datos en SQLite por defecto y admite PostgreSQL como alternativa.

## SQLite

No requiere instalar nada; ideal para uso personal y pruebas. Un solo archivo `db.sqlite3` que respaldas copiándolo.

## PostgreSQL (recomendado para producción)

Mejor para varios usuarios, alta concurrencia y cargas grandes. Se configura con `DB_ENGINE`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`.

## Cómo cambiar

1. Crea base y usuario en PostgreSQL.
2. Ajusta las variables `DB_*` en `.env`.
3. Ejecuta las migraciones sobre la nueva base.

## Notas

Moneta no migra automáticamente tus datos de SQLite a PostgreSQL. Detalles y errores comunes en [`../postgresql.md`](../postgresql.md).

---

Versión corta dentro de la app: **Ayuda** en Moneta. Índice: [README.md](README.md).
