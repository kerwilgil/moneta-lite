import json
import os
import subprocess
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.test import Client
from django.urls import reverse


EDGE_CANDIDATES = [
    Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
    Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
]


PAGES = [
    {
        "slug": "01-dashboard",
        "url_name": "finanzas:dashboard",
        "title": "Dashboard financiero",
        "eyebrow": "Overview",
        "description": "Vista general de balance, flujo, compromisos y deuda operativa.",
    },
    {
        "slug": "02-reportes",
        "url_name": "finanzas:reports",
        "title": "Reportes y analitica",
        "eyebrow": "Insights",
        "description": "Lectura ejecutiva de activos, pasivos, capital y tendencias.",
    },
    {
        "slug": "03-movimientos",
        "url_name": "finanzas:transaction_list",
        "title": "Movimientos",
        "eyebrow": "Operations",
        "description": "Registro diario de ingresos, gastos, pagos y cobros.",
    },
    {
        "slug": "04-suscripciones",
        "url_name": "finanzas:subscription_list",
        "title": "Suscripciones",
        "eyebrow": "Recurring spend",
        "description": "Control visual del gasto recurrente y servicios activos.",
    },
    {
        "slug": "05-ingreso-neto",
        "url_name": "finanzas:net_income",
        "title": "Ingreso neto",
        "eyebrow": "Planning",
        "description": "Simulacion salarial y capacidad mensual real de planificacion.",
    },
]


SOCIAL_VARIANTS = [
    {
        "slug": "social-dashboard",
        "title": "Panorama financiero en un solo lugar",
        "kicker": "Moneta / Dashboard",
        "description": "Balance, flujo y compromisos con una lectura limpia para presentaciones y redes.",
        "image_slug": "01-dashboard",
    },
    {
        "slug": "social-suscripciones",
        "title": "Gasto recurrente bajo control",
        "kicker": "Moneta / Suscripciones",
        "description": "Seguimiento visual de servicios activos, renovaciones y carga mensual.",
        "image_slug": "04-suscripciones",
    },
    {
        "slug": "social-ingreso-neto",
        "title": "Planifica con ingreso real, no estimado",
        "kicker": "Moneta / Ingreso neto",
        "description": "Simula salario neto, deducciones y capacidad mensual antes de comprometer gasto fijo.",
        "image_slug": "05-ingreso-neto",
    },
]


def edge_path():
    return next((path for path in EDGE_CANDIDATES if path.exists()), None)


def run_edge_screenshot(edge_exe, html_path, png_path, width, height):
    command = [
        str(edge_exe),
        "--headless",
        "--disable-gpu",
        "--hide-scrollbars",
        f"--window-size={width},{height}",
        "--virtual-time-budget=6000",
        f"--screenshot={png_path}",
        html_path.resolve().as_uri(),
    ]
    subprocess.run(command, check=True)


def replace_static_paths(html, static_uri):
    html = html.replace('href="/static/', f'href="{static_uri}')
    html = html.replace('src="/static/', f'src="{static_uri}')
    return html


def build_board_html(title, eyebrow, description, iframe_src):
    return f"""<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
  <style>
    :root {{
      --bg: #edf1ee;
      --panel: rgba(255,255,255,0.78);
      --line: rgba(9,19,29,0.09);
      --text: #0b1520;
      --muted: #617487;
      --green: #0b9d67;
      --shadow: 0 24px 70px rgba(9, 19, 29, 0.12);
      --radius: 34px;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      min-height: 100vh;
      font-family: "Segoe UI Variable Text", "Segoe UI", sans-serif;
      color: var(--text);
      background:
        radial-gradient(circle at top left, rgba(11, 157, 103, 0.16), transparent 24%),
        radial-gradient(circle at top right, rgba(24, 95, 255, 0.08), transparent 20%),
        linear-gradient(180deg, #f7faf8, var(--bg));
    }}
    .artboard {{
      width: 1600px;
      min-height: 1000px;
      margin: 0 auto;
      padding: 54px 56px 48px;
      display: grid;
      grid-template-rows: auto 1fr;
      gap: 28px;
    }}
    .heading {{
      display: flex;
      align-items: flex-end;
      justify-content: space-between;
      gap: 24px;
    }}
    .eyebrow {{
      margin: 0 0 10px;
      color: var(--green);
      font-size: 13px;
      letter-spacing: 0.16em;
      text-transform: uppercase;
      font-weight: 700;
    }}
    h1 {{
      margin: 0 0 8px;
      font-family: Georgia, "Times New Roman", serif;
      font-size: 54px;
      line-height: 1;
      letter-spacing: -0.05em;
    }}
    p {{
      margin: 0;
      color: var(--muted);
      font-size: 19px;
      line-height: 1.55;
      max-width: 760px;
    }}
    .brand {{
      display: inline-flex;
      align-items: center;
      gap: 12px;
      padding: 14px 18px;
      border-radius: 999px;
      border: 1px solid var(--line);
      background: var(--panel);
      backdrop-filter: blur(16px);
      box-shadow: 0 16px 40px rgba(9, 19, 29, 0.08);
      font-size: 14px;
      font-weight: 700;
    }}
    .brand-mark {{
      width: 14px;
      height: 14px;
      border-radius: 50%;
      background: linear-gradient(180deg, #15c17d, #08925f);
      box-shadow: 0 0 0 6px rgba(11, 157, 103, 0.12);
    }}
    .frame {{
      border-radius: var(--radius);
      border: 1px solid rgba(255,255,255,0.68);
      background: linear-gradient(180deg, rgba(255,255,255,0.82), rgba(255,255,255,0.56));
      backdrop-filter: blur(18px);
      box-shadow: var(--shadow);
      padding: 16px;
      overflow: hidden;
      position: relative;
    }}
    .frame::before {{
      content: "";
      position: absolute;
      inset: 0;
      border-radius: inherit;
      box-shadow: inset 0 1px 0 rgba(255,255,255,0.75);
      pointer-events: none;
    }}
    iframe {{
      width: 100%;
      height: 800px;
      border: 0;
      border-radius: 24px;
      background: #ffffff;
      overflow: hidden;
    }}
  </style>
</head>
<body>
  <main class="artboard">
    <section class="heading">
      <div>
        <div class="eyebrow">{eyebrow}</div>
        <h1>{title}</h1>
        <p>{description}</p>
      </div>
      <div class="brand">
        <span class="brand-mark"></span>
        <span>Moneta Presentation Capture</span>
      </div>
    </section>
    <section class="frame">
      <iframe src="{iframe_src}"></iframe>
    </section>
  </main>
</body>
</html>
"""


def build_social_html(title, kicker, description, image_uri):
    return f"""<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
  <style>
    :root {{
      --text: #0b1520;
      --muted: #607283;
      --green: #0aa06d;
      --line: rgba(9,19,29,0.08);
      --panel: rgba(255,255,255,0.82);
      --shadow: 0 24px 60px rgba(9,19,29,0.12);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      min-height: 100vh;
      font-family: "Segoe UI Variable Text", "Segoe UI", sans-serif;
      color: var(--text);
      background:
        radial-gradient(circle at top left, rgba(10,160,109,0.2), transparent 28%),
        radial-gradient(circle at bottom right, rgba(33,112,255,0.12), transparent 24%),
        linear-gradient(180deg, #f8fbfa, #e9efec);
    }}
    .poster {{
      width: 1080px;
      min-height: 1350px;
      margin: 0 auto;
      padding: 64px;
      display: grid;
      grid-template-rows: auto auto 1fr auto;
      gap: 24px;
    }}
    .chip {{
      display: inline-flex;
      align-items: center;
      gap: 10px;
      width: fit-content;
      padding: 12px 18px;
      border-radius: 999px;
      border: 1px solid var(--line);
      background: var(--panel);
      backdrop-filter: blur(14px);
      box-shadow: 0 10px 30px rgba(9,19,29,0.06);
      font-size: 13px;
      font-weight: 700;
      letter-spacing: 0.12em;
      text-transform: uppercase;
      color: var(--green);
    }}
    .chip::before {{
      content: "";
      width: 12px;
      height: 12px;
      border-radius: 50%;
      background: linear-gradient(180deg, #1ac783, #089360);
      box-shadow: 0 0 0 6px rgba(10,160,109,0.12);
    }}
    h1 {{
      margin: 0;
      font-family: Georgia, "Times New Roman", serif;
      font-size: 76px;
      line-height: 0.95;
      letter-spacing: -0.06em;
      max-width: 860px;
    }}
    p {{
      margin: 0;
      color: var(--muted);
      font-size: 24px;
      line-height: 1.5;
      max-width: 820px;
    }}
    .frame {{
      position: relative;
      border-radius: 42px;
      padding: 18px;
      background: linear-gradient(180deg, rgba(255,255,255,0.85), rgba(255,255,255,0.65));
      border: 1px solid rgba(255,255,255,0.72);
      box-shadow: var(--shadow);
      overflow: hidden;
      min-height: 760px;
    }}
    .frame img {{
      display: block;
      width: 100%;
      height: 100%;
      object-fit: cover;
      object-position: left top;
      border-radius: 28px;
    }}
    .footer {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 18px;
      color: var(--muted);
      font-size: 18px;
    }}
    .footer strong {{
      color: var(--text);
      font-size: 20px;
    }}
  </style>
</head>
<body>
  <main class="poster">
    <div class="chip">{kicker}</div>
    <h1>{title}</h1>
    <p>{description}</p>
    <section class="frame">
      <img src="{image_uri}" alt="{title}">
    </section>
    <section class="footer">
      <strong>Moneta</strong>
      <span>Diseno listo para demo, social y propuesta comercial.</span>
    </section>
  </main>
</body>
</html>
"""


def build_deck_cover_html(image_uri):
    return f"""<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Moneta Deck Cover</title>
  <style>
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      min-height: 100vh;
      font-family: "Segoe UI Variable Text", "Segoe UI", sans-serif;
      background:
        radial-gradient(circle at top left, rgba(12, 160, 111, 0.22), transparent 28%),
        radial-gradient(circle at top right, rgba(34, 110, 255, 0.14), transparent 26%),
        linear-gradient(180deg, #f7fbf8, #e8efeb);
      color: #0b1520;
    }}
    .deck {{
      width: 1600px;
      min-height: 900px;
      margin: 0 auto;
      padding: 58px;
      display: grid;
      grid-template-columns: 0.9fr 1.1fr;
      gap: 34px;
      align-items: center;
    }}
    .copy {{
      display: grid;
      gap: 18px;
    }}
    .kicker {{
      color: #0aa06d;
      text-transform: uppercase;
      letter-spacing: 0.18em;
      font-size: 13px;
      font-weight: 700;
    }}
    h1 {{
      margin: 0;
      font-family: Georgia, "Times New Roman", serif;
      font-size: 78px;
      line-height: 0.94;
      letter-spacing: -0.06em;
    }}
    p {{
      margin: 0;
      color: #5f7282;
      font-size: 24px;
      line-height: 1.55;
      max-width: 560px;
    }}
    .stat-row {{
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 12px;
      margin-top: 12px;
    }}
    .stat {{
      padding: 18px;
      border-radius: 22px;
      background: rgba(255,255,255,0.82);
      border: 1px solid rgba(9,19,29,0.08);
      box-shadow: 0 18px 40px rgba(9,19,29,0.07);
    }}
    .stat span {{
      display: block;
      color: #6b7d8d;
      font-size: 13px;
      margin-bottom: 8px;
    }}
    .stat strong {{
      font-size: 26px;
      line-height: 1;
    }}
    .visual {{
      padding: 18px;
      border-radius: 38px;
      background: linear-gradient(180deg, rgba(255,255,255,0.86), rgba(255,255,255,0.68));
      border: 1px solid rgba(255,255,255,0.76);
      box-shadow: 0 28px 80px rgba(9,19,29,0.16);
    }}
    .visual img {{
      width: 100%;
      height: 740px;
      object-fit: cover;
      object-position: left top;
      display: block;
      border-radius: 24px;
    }}
  </style>
</head>
<body>
  <main class="deck">
    <section class="copy">
      <div class="kicker">Moneta / Product deck</div>
      <h1>Finanzas personales con criterio visual y operativo.</h1>
      <p>Una plataforma para leer balance, deuda, ingreso y gasto recurrente en una experiencia mucho mas clara para demo comercial y presentacion ejecutiva.</p>
      <div class="stat-row">
        <div class="stat"><span>Vista</span><strong>Dashboard</strong></div>
        <div class="stat"><span>Formato</span><strong>Deck</strong></div>
        <div class="stat"><span>Uso</span><strong>Demo</strong></div>
      </div>
    </section>
    <section class="visual">
      <img src="{image_uri}" alt="Dashboard Moneta">
    </section>
  </main>
</body>
</html>
"""


def build_deck_grid_html(images):
    cards = []
    for title, image_uri in images:
        cards.append(
            f"""
            <article class="card">
              <div class="label">{title}</div>
              <img src="{image_uri}" alt="{title}">
            </article>
            """
        )
    cards_markup = "\n".join(cards)
    return f"""<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Moneta Deck Grid</title>
  <style>
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      min-height: 100vh;
      font-family: "Segoe UI Variable Text", "Segoe UI", sans-serif;
      background:
        radial-gradient(circle at top left, rgba(9, 166, 111, 0.16), transparent 22%),
        linear-gradient(180deg, #f7fbf8, #ebf1ee);
      color: #0b1520;
    }}
    .sheet {{
      width: 1600px;
      min-height: 900px;
      margin: 0 auto;
      padding: 54px;
      display: grid;
      grid-template-rows: auto 1fr;
      gap: 24px;
    }}
    .heading {{
      display: flex;
      justify-content: space-between;
      align-items: end;
      gap: 24px;
    }}
    .heading div:first-child {{
      max-width: 840px;
    }}
    .eyebrow {{
      color: #0aa06d;
      text-transform: uppercase;
      letter-spacing: 0.16em;
      font-size: 13px;
      font-weight: 700;
      margin-bottom: 10px;
    }}
    h1 {{
      margin: 0 0 8px;
      font-family: Georgia, "Times New Roman", serif;
      font-size: 62px;
      line-height: 0.98;
      letter-spacing: -0.05em;
    }}
    p {{
      margin: 0;
      color: #627586;
      font-size: 21px;
      line-height: 1.55;
    }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 18px;
    }}
    .card {{
      padding: 16px;
      border-radius: 30px;
      background: linear-gradient(180deg, rgba(255,255,255,0.88), rgba(255,255,255,0.68));
      border: 1px solid rgba(255,255,255,0.78);
      box-shadow: 0 22px 60px rgba(9,19,29,0.1);
    }}
    .label {{
      margin-bottom: 12px;
      font-size: 15px;
      font-weight: 700;
      color: #0b1520;
    }}
    .card img {{
      width: 100%;
      height: 660px;
      object-fit: cover;
      object-position: left top;
      display: block;
      border-radius: 20px;
    }}
  </style>
</head>
<body>
  <main class="sheet">
    <section class="heading">
      <div>
        <div class="eyebrow">Moneta / deck highlights</div>
        <h1>Tres vistas clave para presentar producto.</h1>
        <p>Dashboard, reportes y suscripciones preparados en una composicion limpia para deck comercial, documento de ventas o propuesta ejecutiva.</p>
      </div>
      <div class="eyebrow">1600 x 900</div>
    </section>
    <section class="grid">
      {cards_markup}
    </section>
  </main>
</body>
</html>
"""


class Command(BaseCommand):
    help = "Exporta capturas horizontales, sociales y de deck a una carpeta local."

    def add_arguments(self, parser):
        parser.add_argument("--username", default="demo")
        parser.add_argument("--password-env", default="MONETA_PRESENTATION_PASSWORD")
        parser.add_argument("--width", type=int, default=1600)
        parser.add_argument("--height", type=int, default=1000)

    def handle(self, *args, **options):
        username = options["username"]
        password_env = options["password_env"]
        password = os.getenv(password_env, "")
        if not password:
            raise CommandError(f"Define {password_env}; la clave no se acepta como argumento CLI.")
        width = options["width"]
        height = options["height"]

        output_root = Path(settings.BASE_DIR) / "presentation"
        source_dir = output_root / "source"
        board_dir = output_root / "boards"
        shot_dir = output_root / "shots"
        social_dir = output_root / "social"
        deck_dir = output_root / "deck"
        for folder in (source_dir, board_dir, shot_dir, social_dir, deck_dir):
            folder.mkdir(parents=True, exist_ok=True)

        client = Client(HTTP_HOST="127.0.0.1")
        if not client.login(username=username, password=password):
            raise CommandError(f"No fue posible iniciar sesion con {username}.")

        static_uri = (Path(settings.BASE_DIR) / "static").resolve().as_uri() + "/"
        manifest = {"boards": [], "social": [], "deck": []}
        edge_exe = edge_path()

        for page in PAGES:
            response = client.get(reverse(page["url_name"]))
            if response.status_code != 200:
                raise CommandError(
                    f"No fue posible exportar {page['slug']} (status {response.status_code})."
                )
            html = replace_static_paths(response.content.decode("utf-8"), static_uri)

            source_path = source_dir / f'{page["slug"]}.html'
            source_path.write_text(html, encoding="utf-8")

            board_html = build_board_html(
                title=page["title"],
                eyebrow=page["eyebrow"],
                description=page["description"],
                iframe_src=source_path.resolve().as_uri(),
            )
            board_path = board_dir / f'{page["slug"]}.html'
            board_path.write_text(board_html, encoding="utf-8")

            shot_path = shot_dir / f'{page["slug"]}.png'
            if edge_exe:
                run_edge_screenshot(edge_exe, board_path, shot_path, width, height)

            manifest["boards"].append(
                {
                    "slug": page["slug"],
                    "title": page["title"],
                    "source_html": str(source_path.relative_to(output_root)),
                    "board_html": str(board_path.relative_to(output_root)),
                    "shot_png": str(shot_path.relative_to(output_root)),
                }
            )

        for variant in SOCIAL_VARIANTS:
            image_uri = (shot_dir / f'{variant["image_slug"]}.png').resolve().as_uri()
            social_html = build_social_html(
                title=variant["title"],
                kicker=variant["kicker"],
                description=variant["description"],
                image_uri=image_uri,
            )
            social_html_path = social_dir / f'{variant["slug"]}.html'
            social_png_path = social_dir / f'{variant["slug"]}.png'
            social_html_path.write_text(social_html, encoding="utf-8")
            if edge_exe:
                run_edge_screenshot(edge_exe, social_html_path, social_png_path, 1080, 1350)
            manifest["social"].append(
                {
                    "slug": variant["slug"],
                    "html": str(social_html_path.relative_to(output_root)),
                    "shot_png": str(social_png_path.relative_to(output_root)),
                }
            )

        cover_html_path = deck_dir / "cover.html"
        cover_png_path = deck_dir / "cover.png"
        cover_html_path.write_text(
            build_deck_cover_html((shot_dir / "01-dashboard.png").resolve().as_uri()),
            encoding="utf-8",
        )
        if edge_exe:
            run_edge_screenshot(edge_exe, cover_html_path, cover_png_path, 1600, 900)
        manifest["deck"].append(
            {
                "slug": "cover",
                "html": str(cover_html_path.relative_to(output_root)),
                "shot_png": str(cover_png_path.relative_to(output_root)),
            }
        )

        grid_html_path = deck_dir / "highlights.html"
        grid_png_path = deck_dir / "highlights.png"
        grid_html_path.write_text(
            build_deck_grid_html(
                [
                    ("Dashboard", (shot_dir / "01-dashboard.png").resolve().as_uri()),
                    ("Reportes", (shot_dir / "02-reportes.png").resolve().as_uri()),
                    ("Suscripciones", (shot_dir / "04-suscripciones.png").resolve().as_uri()),
                ]
            ),
            encoding="utf-8",
        )
        if edge_exe:
            run_edge_screenshot(edge_exe, grid_html_path, grid_png_path, 1600, 900)
        manifest["deck"].append(
            {
                "slug": "highlights",
                "html": str(grid_html_path.relative_to(output_root)),
                "shot_png": str(grid_png_path.relative_to(output_root)),
            }
        )

        manifest_path = output_root / "manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

        readme_path = output_root / "README.md"
        readme_path.write_text(
            "\n".join(
                [
                    "# Presentation Assets",
                    "",
                    "Activos exportados para presentacion comercial, deck y redes.",
                    "",
                    "Estructura:",
                    "- `source/`: HTML real exportado desde la app autenticada.",
                    "- `boards/`: pantallas horizontales de presentacion.",
                    "- `shots/`: PNG horizontales finales.",
                    "- `social/`: piezas verticales 1080x1350 para redes o promos.",
                    "- `deck/`: composiciones 1600x900 para portada y resumen de deck.",
                    "",
                    f"Usuario utilizado: `{username}`",
                ]
            ),
            encoding="utf-8",
        )

        if edge_exe:
            self.stdout.write(self.style.SUCCESS(f"Activos generados en {output_root}"))
        else:
            self.stdout.write(self.style.WARNING("No se encontro Microsoft Edge. Se exportaron solo los HTML."))
