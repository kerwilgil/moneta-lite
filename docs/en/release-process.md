# Release Process

This document describes how to prepare, validate and package Moneta for internal, public or commercial delivery.

## Delivery Types

Demo:

- Complete package for testing and presentations.
- Uses evaluation license.

Lite:

- Public or free package.
- Uses MIT license.
- Limited features.

Pro:

- Full commercial package.
- Uses commercial license.
- Must not be redistributed without permission.

Personal:

- Private package for local use.
- Uses private license.

## Recommended Flow

1. Work in the private base repository.
2. Run tests and checks.
3. Update documentation and `CHANGELOG.md`.
4. Synchronize variants.
5. Test a variant if the change affects editions.
6. Generate ZIPs.
7. Push commit and tags if applicable.
8. Deliver the correct ZIP for the client/use case.

## Pre-Release Verification

```powershell
python manage.py test finanzas
python manage.py check
python manage.py makemigrations --check --dry-run
```

For production, with a real `.env`:

```powershell
python manage.py check --deploy
python manage.py collectstatic
```

## Synchronize Variants

```powershell
.\scripts\sync_variants.ps1
```

This copies base project changes into:

- `variants\lite`
- `variants\pro`
- `variants\personal-clean`
- `instances\personal-live`

Variants are ignored by Git.

## Create A Variant From Scratch

```powershell
.\scripts\create_variant.ps1 -Edition lite -Force
.\scripts\create_variant.ps1 -Edition pro -Force
.\scripts\create_variant.ps1 -Edition personal -Force
```

The script:

- Copies the project without `.venv`, `.env`, `db.sqlite3`, logs or releases.
- Generates `DJANGO_SECRET_KEY`.
- Generates initial password if `-AdminPassword` is not passed.
- Sets `SAAS_EDITION`.
- Copies the edition license.
- Runs migrations if `.venv` exists.
- Creates the initial admin user.

For commercial delivery, pass a controlled strong password:

```powershell
.\scripts\create_variant.ps1 -Edition pro -AdminUsername admin -AdminPassword "strong-password" -Force
```

## Generate ZIPs

```powershell
.\scripts\package_releases.ps1
```

Output:

- `releases\demo.zip`
- `releases\lite.zip`
- `releases\pro.zip`
- `releases\personal-clean.zip`

The script excludes:

- `.env`
- SQLite databases
- logs
- `.venv`
- `instances`
- `releases`
- `_publish`
- `staticfiles`
- `.zip` files

## Content Checklist

Each ZIP should include:

- `config/`
- `finanzas/`
- `static/`
- `templates/`
- `.env.example`
- `README.md`
- `QUICKSTART.md`
- `INSTALL.md`
- `FAQ.md`
- `SUPPORT.md`
- `CHANGELOG.md`
- `requirements.txt`
- `manage.py`
- `LICENSE`

Demo may also include:

- `docs/`
- `scripts/`
- `security_best_practices_report.md`

## Publish To Git

Normal flow:

```powershell
git status --short
git add .
git commit -m "Clear message"
git push
```

Do not commit:

- `.env`
- `db.sqlite3`
- `logs/`
- `releases/`
- `variants/`
- `instances/`

These paths are already in `.gitignore`.

## Versioning

Update `CHANGELOG.md` for each relevant delivery.

Recommended format:

```text
## 0.1.X - YYYY-MM-DD

- Important change.
- Relevant fix.
- Security or release note.
```

## Security Review Before Selling

Verify:

- `.env.example` contains no real secrets.
- `DJANGO_DEBUG=0` in production.
- `DJANGO_SECRET_KEY` is not a placeholder.
- Admin user has a strong password.
- `check --deploy` has no critical warnings.
- CSV sanitization remains active.
- Lite feature gates block Pro modules.
- No databases or logs are inside the ZIP.

## Client Delivery

For Pro:

1. Deliver `pro.zip`.
2. Attach `INSTALL.md` instructions.
3. Tell the client to configure `.env`.
4. Confirm commercial license.
5. If guided installation is included, create an admin user with a strong password and share credentials securely.

For Lite:

1. Deliver or publish `lite.zip`.
2. Confirm `SAAS_EDITION=lite`.
3. Do not include private links or sensitive demo data.

For Personal:

1. Deliver `personal-clean.zip`.
2. Recommend local or NAS use.
3. Recommend backups of `.env` and database.
