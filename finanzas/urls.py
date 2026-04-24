from django.urls import path

from . import views


app_name = "finanzas"

urlpatterns = [
    path("setup/", views.initial_setup, name="initial_setup"),
    path("idioma/cambiar/", views.change_language, name="change_language"),
    path("", views.dashboard, name="dashboard"),
    path("movimientos/", views.transaction_list, name="transaction_list"),
    path("movimientos/nuevo/", views.transaction_create, name="transaction_create"),
    path("movimientos/<int:pk>/editar/", views.transaction_edit, name="transaction_edit"),
    path("movimientos/<int:pk>/eliminar/", views.transaction_delete, name="transaction_delete"),
    path("cuentas/nueva/", views.account_create, name="account_create"),
    path("cuentas/<int:pk>/editar/", views.account_edit, name="account_edit"),
    path("cuentas/<int:pk>/eliminar/", views.account_delete, name="account_delete"),
    path("categorias/nueva/", views.category_create, name="category_create"),
    path("categorias/<int:pk>/editar/", views.category_edit, name="category_edit"),
    path("categorias/<int:pk>/eliminar/", views.category_delete, name="category_delete"),
    path("facturas/", views.invoice_list, name="invoice_list"),
    path("facturas/nueva/", views.invoice_create, name="invoice_create"),
    path("facturas/<int:pk>/editar/", views.invoice_edit, name="invoice_edit"),
    path("facturas/<int:pk>/eliminar/", views.invoice_delete, name="invoice_delete"),
    path("recurrentes/", views.recurring_list, name="recurring_list"),
    path("recurrentes/nuevo/", views.recurring_create, name="recurring_create"),
    path("recurrentes/ejecutar/", views.recurring_run_now, name="recurring_run_now"),
    path("recurrentes/<int:pk>/editar/", views.recurring_edit, name="recurring_edit"),
    path("recurrentes/<int:pk>/eliminar/", views.recurring_delete, name="recurring_delete"),
    path("suscripciones/", views.subscription_list, name="subscription_list"),
    path("suscripciones/nueva/", views.subscription_create, name="subscription_create"),
    path("suscripciones/ejecutar/", views.subscription_run_now, name="subscription_run_now"),
    path("suscripciones/<int:pk>/editar/", views.subscription_edit, name="subscription_edit"),
    path("suscripciones/<int:pk>/eliminar/", views.subscription_delete, name="subscription_delete"),
    path("tarjetas/", views.credit_card_list, name="credit_card_list"),
    path("tarjetas/nueva/", views.credit_card_create, name="credit_card_create"),
    path("tarjetas/<int:pk>/editar/", views.credit_card_edit, name="credit_card_edit"),
    path("tarjetas/<int:pk>/eliminar/", views.credit_card_delete, name="credit_card_delete"),
    path("libro-contable/", views.ledger, name="ledger"),
    path("libro-contable/nuevo/", views.ledger_create, name="ledger_create"),
    path("reportes/", views.reports, name="reports"),
    path("ingreso-neto/", views.net_income, name="net_income"),
    path("configuracion/", views.settings_page, name="settings"),
    path("exportar/movimientos.csv", views.export_transactions_csv, name="export_transactions_csv"),
    path("exportar/facturas.csv", views.export_invoices_csv, name="export_invoices_csv"),
    path("exportar/recurrentes.csv", views.export_recurring_csv, name="export_recurring_csv"),
    path("exportar/suscripciones.csv", views.export_subscriptions_csv, name="export_subscriptions_csv"),
]
