<div align="center">
  <img src="static/img/moneta_logo.png" alt="Moneta Lite" width="180">
  <h1>Moneta Lite</h1>
  <p>Una edición ligera para organizar tus finanzas esenciales sin perder control ni claridad.</p>

  <p>
    <img src="https://img.shields.io/badge/Django-6.0.7%2B-0C4B33?logo=django&logoColor=white" alt="Django 6.0.7+">
    <img src="https://img.shields.io/badge/Python-3.12%2B-3776AB?logo=python&logoColor=white" alt="Python 3.12+">
    <img src="https://img.shields.io/badge/idiomas-ES%20%7C%20EN-0F766E" alt="Español e inglés">
    <img src="https://img.shields.io/badge/licencia-MIT-blue" alt="Licencia MIT">
  </p>
</div>

Moneta Lite está pensada para evaluaciones, demostraciones y uso financiero básico. Mantiene una interfaz adaptable y las protecciones de seguridad del proyecto principal, con un conjunto reducido de módulos.

## Qué incluye

- Panel con cuentas, balances y movimientos.
- Registro de ingresos, gastos, transferencias y categorías.
- Facturas y tarjetas de crédito.
- Suscripciones privadas de seguros disponibles en el catálogo Lite.
- Reportes y exportaciones básicas.
- Configuración administrativa, español e inglés, tema claro y oscuro.

## Límites de esta edición

Lite no habilita pagos recurrentes automatizados, libro contable, cálculo de utilidad neta ni exportaciones avanzadas. Estas restricciones se aplican en el servidor mediante controles de funciones.

Para acceder al conjunto completo de módulos, solicita **Moneta Full** mediante contacto comercial.

## Inicio rápido local

Requisitos: Python 3.12 o superior y Git.

```powershell
git clone https://github.com/kerwilgil/moneta-lite.git
cd moneta-lite
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
$env:DJANGO_DEBUG = "1"
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Abre `http://127.0.0.1:8000/`. La edición del paquete ya está fijada como Lite; no necesitas cambiar `SAAS_EDITION`.

## Configuración segura

Antes de desplegar:

- Sustituye `DJANGO_SECRET_KEY` por un valor único de 50 caracteres o más.
- Mantén `DJANGO_DEBUG=0` y configura hosts y orígenes CSRF explícitos.
- Usa HTTPS antes de activar HSTS y redirección estricta.
- Mantén deshabilitada la configuración web salvo durante un alta controlada.
- No subas `.env`, `db.sqlite3`, registros ni copias de seguridad al repositorio.

Consulta [`.env.example`](.env.example) para conocer todas las variables disponibles.

## Validación

```powershell
python manage.py check
python manage.py test finanzas
```

Documentación adicional:

- [Inicio rápido](QUICKSTART.md)
- [Instalación](INSTALL.md)
- [Preguntas frecuentes](FAQ.md)
- [Manual de usuario](docs/manual/user-manual-es.md)
- [Soporte](SUPPORT.md)

## Licencia

Moneta Lite se distribuye bajo la [licencia MIT](LICENSE).
