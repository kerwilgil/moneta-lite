"""Forms for the human Import Queue review UI."""

from __future__ import annotations

from django import forms
from django.utils.translation import gettext_lazy as _

from finanzas.models import Account, Category
from finanzas.intelligence.imports.models import TransactionDraft


class DraftEditForm(forms.ModelForm):
    """Edit a pending draft before approval.

    Financial validation lives in the service layer; this form only scopes the
    selectable related objects to the owning user and does light field checks.
    """

    class Meta:
        model = TransactionDraft
        fields = [
            "merchant", "description", "amount", "currency", "transaction_date",
            "transaction_type", "account", "destination_account",
            "suggested_category",
        ]
        widgets = {
            "transaction_date": forms.DateInput(attrs={"type": "date"}),
            "description": forms.TextInput(),
        }
        labels = {
            "merchant": _("Comercio"),
            "description": _("Descripcion"),
            "amount": _("Monto"),
            "currency": _("Moneda"),
            "transaction_date": _("Fecha"),
            "transaction_type": _("Tipo"),
            "account": _("Cuenta"),
            "destination_account": _("Cuenta destino"),
            "suggested_category": _("Categoria"),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        if user is not None:
            accounts = Account.objects.filter(user=user).order_by("name")
            self.fields["account"].queryset = accounts
            self.fields["destination_account"].queryset = accounts
            self.fields["destination_account"].required = False
            self.fields["suggested_category"].queryset = (
                Category.objects.filter(user=user).order_by("name")
            )
            self.fields["suggested_category"].required = False
        for field in self.fields.values():
            css = field.widget.attrs.get("class", "")
            widget = field.widget
            if isinstance(widget, (forms.Select, forms.SelectMultiple)):
                field.widget.attrs["class"] = (css + " form-select").strip()
            else:
                field.widget.attrs["class"] = (css + " form-control").strip()

    def clean_currency(self):
        value = (self.cleaned_data.get("currency") or "").strip().upper()
        if len(value) != 3 or not value.isalpha():
            raise forms.ValidationError(_("Usa un codigo ISO de 3 letras."))
        return value
