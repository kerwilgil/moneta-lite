# PostgreSQL

Moneta usa **SQLite por defecto** y no necesita nada más para uso personal o
para probar. **PostgreSQL** es la opción recomendada para producción, varios
usuarios, alta concurrencia o cargas grandes.

Moneta v0.3.0 se validó contra **PostgreSQL 18.6** real: creación de base desde
cero, todas las migraciones (ida y vuelta), constraints, índices, claves
foráneas, concurrencia con bloqueo de fila, cola de importaciones y MCP.

## 1. Requisitos

- PostgreSQL 14 o superior (probado con 18.x).
- El cliente Python psycopg 3: `pip install -r requirements-postgres.txt`
  (o `pip install "psycopg[binary]"`). No está en
  `requirements.txt` para no volver PostgreSQL obligatorio.

## 2. Crear la base y el usuario

Con un rol administrador de PostgreSQL (por ejemplo `postgres`):

```sql
CREATE ROLE moneta LOGIN PASSWORD 'CAMBIA-ESTA-CLAVE';
CREATE DATABASE moneta OWNER moneta ENCODING 'UTF8';
```

No pongas la contraseña en ningún archivo versionado. Usa `.env` (ignorado por
git) o el gestor de secretos de tu plataforma.

## 3. Variables de entorno

En tu `.env` (ver `.env.example`):

```env
DB_ENGINE=django.db.backends.postgresql
DB_NAME=moneta
DB_USER=moneta
DB_PASSWORD=CAMBIA-ESTA-CLAVE
DB_HOST=127.0.0.1
DB_PORT=5432
```

Alternativa con un único valor: define `DATABASE_URL` en tu proceso y tradúcelo a
estas variables en tu script de arranque; Moneta lee las `DB_*`.

## 4. Migrar

```bash
python manage.py migrate
python manage.py check --deploy
```

Comprueba en la salida que:

- todas las migraciones se aplican sin error,
- se crean constraints, índices y claves foráneas,
- `check --deploy` no reporta problemas nuevos.

## 5. Ejecutar los tests contra PostgreSQL

Los mismos `python manage.py test`, apuntando a una base de test separada
mediante las variables `DB_*`. La base `test_<DB_NAME>` la crea y destruye el
propio runner; el rol necesita `CREATEDB`.

```bash
# PowerShell
$env:DB_ENGINE="django.db.backends.postgresql"
$env:DB_NAME="moneta_test"; $env:DB_USER="moneta"; $env:DB_PASSWORD="..."
$env:DB_HOST="127.0.0.1"; $env:DB_PORT="5432"
python manage.py test
```

En PostgreSQL se ejecutan además los tests que en SQLite quedan `skipped`:
concurrencia (`Phase3PostgresIntegrationTests`) y reversibilidad de migraciones.

## 6. Copias de seguridad

```bash
pg_dump -Fc moneta > moneta_YYYYMMDD.dump
pg_restore -d moneta_nueva moneta_YYYYMMDD.dump
```

Programa `pg_dump` con la periodicidad que necesites y guarda las copias fuera
del servidor.

## 7. Errores comunes

| Síntoma | Causa / solución |
|---------|------------------|
| `password authentication failed` | Usuario/clave incorrectos o `pg_hba.conf` no permite el método; revisa `DB_USER` / `DB_PASSWORD`. |
| `database "..." does not exist` | Crea la base (paso 2) o revisa `DB_NAME`. |
| `permission denied to create database` (en tests) | Da `CREATEDB` al rol: `ALTER ROLE moneta CREATEDB;`. |
| `could not connect to server` | El servicio no está arriba o el puerto/host no coinciden. |
| `psycopg` no instalado | `pip install "psycopg[binary]"`. |

## 8. Cambiar de SQLite a PostgreSQL

Moneta **no** migra automáticamente los datos de un `db.sqlite3` a PostgreSQL.
Para un traslado real:

1. Levanta PostgreSQL vacío y aplica `migrate`.
2. Exporta desde SQLite con `python manage.py dumpdata` (excluye `contenttypes`
   y `auth.permission`) e impórtalo con `loaddata`, o usa una herramienta de
   migración de datos. Verifica balances y conteos después.
3. Cambia las variables `DB_*` y reinicia.

Para instalaciones nuevas, empieza directamente en PostgreSQL.
