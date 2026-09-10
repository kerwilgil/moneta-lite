"""In-app Help Center.

Template-based articles (no Markdown dependency, works fully offline). Each
article is a template under ``finanzas/help/articles/<slug>.html`` that extends
``finanzas/help/_article_base.html``. Visibility follows the same edition
feature gates as the rest of the UI, so the Lite build never advertises Pro-only
modules.

Canonical long-form content lives in ``docs/user-guide/``; each article links to
its counterpart there.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from django.http import Http404
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.template import TemplateDoesNotExist
from django.template.loader import select_template
from django.utils.translation import gettext as _, gettext_lazy as _l

from .product import feature_enabled


@dataclass(frozen=True)
class Article:
    slug: str
    title: str
    section: str
    summary: str
    keywords: tuple = field(default_factory=tuple)
    feature: str = ""          # required edition feature, "" = always available
    guide: str = ""            # docs/user-guide/<guide>.md counterpart

    def visible(self) -> bool:
        return not self.feature or feature_enabled(self.feature)


# Ordered; groups render in first-seen section order.
ARTICLES = (
    Article(
        "primeros-pasos", _l("Primeros pasos"), _l("Primeros pasos"),
        _l("Crea tu primer usuario, tus cuentas y registra un movimiento."),
        (_l("inicio"), _l("empezar"), _l("onboarding"), _l("instalar")),
        guide="getting-started",
    ),
    Article(
        "dashboard", _l("Dashboard"), _l("Uso diario"),
        _l("Cómo leer balance, ingresos del mes, deuda y la tendencia de flujo."),
        (_l("panel"), _l("balance"), _l("flujo"), _l("resumen")),
        guide="dashboard",
    ),
    Article(
        "cuentas", _l("Cuentas"), _l("Uso diario"),
        _l("Tipos de cuenta, saldo de apertura y saldo actual."),
        (_l("cuenta"), _l("banco"), _l("efectivo"), _l("capital"), _l("saldo")),
        feature="transactions", guide="accounts",
    ),
    Article(
        "movimientos", _l("Movimientos"), _l("Uso diario"),
        _l("Ingresos, gastos, transferencias y pagos de tarjeta, con filtros."),
        (_l("movimiento"), _l("gasto"), _l("ingreso"), _l("transferencia"), _l("filtro")),
        feature="transactions", guide="transactions",
    ),
    Article(
        "facturas", _l("Facturas"), _l("Uso diario"),
        _l("Facturas emitidas y recibidas, estados y vencimientos."),
        (_l("factura"), _l("emitida"), _l("recibida"), _l("vencida")),
        feature="invoices", guide="bills",
    ),
    Article(
        "tarjetas", _l("Tarjetas de crédito"), _l("Uso diario"),
        _l("Límite, saldo, disponible, fecha de corte y fecha de pago."),
        (_l("tarjeta"), _l("crédito"), _l("límite"), _l("corte"), _l("pago mínimo")),
        feature="credit_cards", guide="credit-cards",
    ),
    Article(
        "suscripciones", _l("Suscripciones"), _l("Uso diario"),
        _l("Gasto recurrente de servicios y su proyección mensual."),
        (_l("suscripción"), _l("recurrente"), _l("servicio"), _l("mensual")),
        feature="subscriptions", guide="subscriptions",
    ),
    Article(
        "seguros", _l("Seguros privados"), _l("Uso diario"),
        _l("Apartado de seguros de vida, salud e ingreso dentro de suscripciones."),
        (_l("seguro"), _l("vida"), _l("salud"), _l("cobertura")),
        feature="subscriptions", guide="insurance",
    ),
    Article(
        "recurrentes", _l("Pagos recurrentes"), _l("Uso diario"),
        _l("Automatización de pagos periódicos con límites por lote."),
        (_l("recurrente"), _l("automático"), _l("periódico"), _l("lote")),
        feature="recurring", guide="recurring",
    ),
    Article(
        "reportes", _l("Reportes"), _l("Uso diario"),
        _l("Activos, pasivos, capital neto, flujo del mes y presupuesto por categoría."),
        (_l("reporte"), _l("presupuesto"), _l("categoría"), _l("capital neto")),
        feature="reports", guide="reports",
    ),
    Article(
        "ingreso-neto", _l("Ingreso neto"), _l("Uso diario"),
        _l("Simulación de salario neto y capacidad mensual de planificación."),
        (_l("salario"), _l("neto"), _l("deducción"), _l("planificar")),
        feature="net_income", guide="net-income",
    ),
    Article(
        "libro-contable", _l("Libro contable"), _l("Uso diario"),
        _l("Asientos de partida doble y su relación con los movimientos."),
        (_l("contable"), _l("asiento"), _l("debe"), _l("haber"), _l("partida doble")),
        feature="ledger", guide="ledger",
    ),
    Article(
        "importaciones", _l("Importaciones"), _l("Automatización e IA"),
        _l("La cola de importaciones: propuestas, deduplicación y aprobación humana."),
        (_l("importar"), _l("borrador"), _l("duplicado"), _l("aprobar"), _l("agente")),
        feature="transactions", guide="import-queue",
    ),
    Article(
        "mcp", _l("Moneta MCP"), _l("Automatización e IA"),
        _l("Qué pueden y qué no pueden hacer los agentes conectados por MCP."),
        (_l("mcp"), _l("agente"), _l("token"), _l("scope"), _l("lectura"), _l("borrador")),
        feature="settings", guide="mcp",
    ),
    Article(
        "ia", _l("Inteligencia artificial"), _l("Automatización e IA"),
        _l("El papel de la IA en Moneta: sugiere, nunca decide."),
        (_l("ia"), _l("inteligencia artificial"), _l("proveedor"), _l("privacidad")),
        guide="ai",
    ),
    Article(
        "configuracion", _l("Configuración"), _l("Cuenta y plataforma"),
        _l("Cuentas, categorías, idioma, tema y la edición activa."),
        (_l("configuración"), _l("ajustes"), _l("idioma"), _l("tema"), _l("categoría")),
        feature="settings", guide="settings",
    ),
    Article(
        "seguridad", _l("Seguridad y privacidad"), _l("Cuenta y plataforma"),
        _l("Aislamiento por usuario, tokens, aprobación humana y despliegue seguro."),
        (_l("seguridad"), _l("privacidad"), _l("token"), _l("csrf"), _l("aislamiento")),
        guide="security",
    ),
    Article(
        "base-de-datos", _l("SQLite y PostgreSQL"), _l("Cuenta y plataforma"),
        _l("Cuándo usar SQLite y cómo pasar a PostgreSQL."),
        (_l("base de datos"), _l("sqlite"), _l("postgresql"), _l("producción")),
        guide="database",
    ),
    Article(
        "preguntas-frecuentes", _l("Preguntas frecuentes"), _l("Cuenta y plataforma"),
        _l("Dudas habituales sobre ediciones, acceso remoto y datos."),
        (_l("faq"), _l("dudas"), _l("preguntas")),
        guide="faq",
    ),
)

_BY_SLUG = {a.slug: a for a in ARTICLES}


def visible_articles():
    return [a for a in ARTICLES if a.visible()]


def grouped_articles():
    groups: dict[str, list] = {}
    for article in visible_articles():
        groups.setdefault(str(article.section), []).append(article)
    return list(groups.items())


@login_required
def help_index(request):
    return render(
        request,
        "finanzas/help/index.html",
        {"groups": grouped_articles(), "article_count": len(visible_articles())},
    )


@login_required
def help_article(request, slug):
    article = _BY_SLUG.get(slug)
    if article is None or not article.visible():
        raise Http404("help article not found")
    try:
        body_template = select_template([f"finanzas/help/articles/{slug}.html"])
    except TemplateDoesNotExist as exc:  # pragma: no cover - guards a packaging mistake
        raise Http404("help article template missing") from exc
    return render(
        request,
        "finanzas/help/article.html",
        {"article": article, "body_template": body_template.template.name},
    )
