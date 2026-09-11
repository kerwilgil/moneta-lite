"""Import Queue UI routes."""

from django.urls import path

from finanzas.intelligence.imports import views

app_name = "imports"

urlpatterns = [
    path("", views.import_queue, name="import_queue"),
    path("<int:pk>/editar/", views.draft_edit, name="draft_edit"),
    path("<int:pk>/aprobar/", views.draft_approve, name="draft_approve"),
    path("<int:pk>/rechazar/", views.draft_reject, name="draft_reject"),
]
