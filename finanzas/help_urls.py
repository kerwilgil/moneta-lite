"""Help Center routes (in-app user guide)."""

from django.urls import path

from finanzas import help as help_views

app_name = "help"

urlpatterns = [
    path("", help_views.help_index, name="help_index"),
    path("<slug:slug>/", help_views.help_article, name="help_article"),
]
