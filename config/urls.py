from django.contrib import admin
from django.urls import include, path

from finanzas.views import login_view

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/login/", login_view, name="login"),
    path("accounts/", include("django.contrib.auth.urls")),
    path("i18n/", include("django.conf.urls.i18n")),
    path("mcp/", include("finanzas.intelligence.mcp.urls")),
    path("importaciones/", include("finanzas.intelligence.imports.urls")),
    path("configuracion/integraciones/", include("finanzas.intelligence.mcp.ui_urls")),
    path("", include("finanzas.urls")),
]
