"""Human Import Queue review UI.

Every mutation delegates to :mod:`finanzas.intelligence.imports.services`; this
module never touches ``FinancialTransaction`` or accounting helpers directly.
"""

from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _
from django.views.decorators.http import require_http_methods

from finanzas.product import require_feature
from finanzas.intelligence.imports import services
from finanzas.intelligence.imports.forms import DraftEditForm
from finanzas.intelligence.imports.models import ImportBatch, TransactionDraft

STATUS_TABS = ["pending", "approved", "rejected", "duplicate", "error"]


@login_required
@require_feature("transactions")
def import_queue(request):
    status = request.GET.get("status", "pending")
    if status not in STATUS_TABS:
        status = "pending"
    drafts = (
        TransactionDraft.objects.filter(user=request.user, status=status)
        .select_related("account", "destination_account", "suggested_category",
                        "batch", "transaction")
        .order_by("-created_at")
    )
    paginator = Paginator(drafts, 25)
    page = paginator.get_page(request.GET.get("page"))

    labels = {
        "pending": _("Pendientes"), "approved": _("Aprobados"),
        "rejected": _("Rechazados"), "duplicate": _("Duplicados"),
        "error": _("Con error"),
    }
    tabs = [
        {
            "key": s,
            "label": labels[s],
            "count": TransactionDraft.objects.filter(user=request.user, status=s).count(),
            "active": s == status,
        }
        for s in STATUS_TABS
    ]
    context = {
        "page_obj": page,
        "drafts": page.object_list,
        "status": status,
        "status_tabs": tabs,
        "batches": ImportBatch.objects.filter(user=request.user).order_by("-created_at")[:10],
    }
    return render(request, "finanzas/import_queue.html", context)


@login_required
@require_feature("transactions")
def draft_edit(request, pk):
    draft = get_object_or_404(TransactionDraft, pk=pk, user=request.user)
    if draft.status != TransactionDraft.Status.PENDING:
        messages.info(request, _("Solo se pueden editar borradores pendientes."))
        return redirect("imports:import_queue")

    if request.method == "POST":
        form = DraftEditForm(request.POST, instance=draft, user=request.user)
        if form.is_valid():
            cd = form.cleaned_data
            try:
                services.update_draft(
                    draft,
                    reviewer=request.user,
                    account=cd["account"].pk,
                    destination_account=(cd["destination_account"].pk
                                         if cd.get("destination_account") else None),
                    suggested_category=(cd["suggested_category"].pk
                                        if cd.get("suggested_category") else None),
                    merchant=cd["merchant"],
                    description=cd["description"],
                    amount=cd["amount"],
                    currency=cd["currency"],
                    transaction_date=cd["transaction_date"],
                    transaction_type=cd["transaction_type"],
                )
            except services.DuplicateDraft as exc:
                messages.warning(
                    request,
                    _("Este borrador coincide con el #%(id)s y quedaria duplicado.")
                    % {"id": exc.existing.pk},
                )
            except services.ImportError as exc:
                messages.error(request, str(exc))
            else:
                messages.success(request, _("Borrador actualizado."))
                return redirect("imports:import_queue")
    else:
        form = DraftEditForm(instance=draft, user=request.user)

    return render(request, "finanzas/import_draft_form.html",
                  {"form": form, "draft": draft})


@login_required
@require_feature("transactions")
@require_http_methods(["POST"])
def draft_approve(request, pk):
    draft = get_object_or_404(TransactionDraft, pk=pk, user=request.user)
    try:
        tx = services.approve_draft(draft, reviewer=request.user)
    except services.InvalidTransition as exc:
        messages.error(request, str(exc))
    except services.ImportError as exc:
        messages.error(request, str(exc))
    else:
        messages.success(
            request,
            _("Borrador aprobado. Transaccion #%(id)s creada.") % {"id": tx.pk},
        )
    return redirect("imports:import_queue")


@login_required
@require_feature("transactions")
@require_http_methods(["POST"])
def draft_reject(request, pk):
    draft = get_object_or_404(TransactionDraft, pk=pk, user=request.user)
    try:
        services.reject_draft(
            draft, reviewer=request.user, reason=request.POST.get("reason", "")
        )
    except services.InvalidTransition as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, _("Borrador rechazado."))
    return redirect("imports:import_queue")
