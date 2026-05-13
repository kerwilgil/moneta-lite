from decimal import Decimal

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.forms import formset_factory

from .models import Account, Category, CreditCard, FinancialTransaction, Invoice, JournalEntry, RecurringPayment


class UserScopedModelForm(forms.ModelForm):
    user_scoped_fields = ()

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        for field_name in self.user_scoped_fields:
            if field_name in self.fields:
                self.fields[field_name].queryset = self.fields[field_name].queryset.filter(user=user)
        self.apply_widget_classes()

    def apply_widget_classes(self):
        for field in self.fields.values():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.setdefault("class", "form-check-input")
            elif isinstance(field.widget, forms.Select):
                field.widget.attrs.setdefault("class", "form-select")
            else:
                field.widget.attrs.setdefault("class", "form-control")

    def save(self, commit=True):
        instance = super().save(commit=False)
        if self.user and hasattr(instance, "user_id"):
            instance.user = self.user
        if commit:
            instance.save()
            self.save_m2m()
        return instance


class AccountForm(UserScopedModelForm):
    def clean_name(self):
        name = (self.cleaned_data.get("name") or "").strip()
        queryset = Account.objects.filter(user=self.user, name__iexact=name)
        if self.instance and self.instance.pk:
            queryset = queryset.exclude(pk=self.instance.pk)
        if queryset.exists():
            raise forms.ValidationError("Ya tienes una cuenta con ese nombre. Usa un nombre distinto.")
        return name

    class Meta:
        model = Account
        fields = ["name", "account_type", "currency", "opening_balance", "current_balance", "is_active"]
        labels = {
            "name": "Nombre",
            "account_type": "Tipo de cuenta",
            "currency": "Moneda",
            "opening_balance": "Balance inicial",
            "current_balance": "Balance actual",
            "is_active": "Activa",
        }
        help_texts = {
            "opening_balance": "Valor base o saldo inicial de referencia.",
            "current_balance": "Valor actual. En inversiones sirve para medir ganancia o perdida contra el balance inicial.",
        }


class CategoryForm(UserScopedModelForm):
    def clean_name(self):
        name = (self.cleaned_data.get("name") or "").strip()
        category_type = self.cleaned_data.get("category_type") or self.data.get("category_type")
        queryset = Category.objects.filter(user=self.user, name__iexact=name, category_type=category_type)
        if self.instance and self.instance.pk:
            queryset = queryset.exclude(pk=self.instance.pk)
        if queryset.exists():
            raise forms.ValidationError("Ya tienes una categoria con ese nombre y tipo.")
        return name

    def clean_monthly_limit(self):
        monthly_limit = self.cleaned_data.get("monthly_limit")
        if monthly_limit is not None and monthly_limit <= 0:
            raise forms.ValidationError("El limite mensual debe ser mayor que cero.")
        return monthly_limit

    class Meta:
        model = Category
        fields = ["name", "category_type", "monthly_limit"]
        labels = {
            "name": "Nombre",
            "category_type": "Tipo",
            "monthly_limit": "Limite mensual",
        }


class TransactionForm(UserScopedModelForm):
    user_scoped_fields = ("account", "destination_account", "category", "related_credit_card")

    class Meta:
        model = FinancialTransaction
        fields = [
            "transaction_type",
            "description",
            "counterparty",
            "account",
            "destination_account",
            "related_credit_card",
            "category",
            "amount",
            "date",
            "status",
            "notes",
        ]
        labels = {
            "transaction_type": "Tipo",
            "description": "Descripcion",
            "counterparty": "Persona o comercio",
            "account": "Cuenta",
            "destination_account": "Cuenta destino",
            "related_credit_card": "Tarjeta relacionada",
            "category": "Categoria",
            "amount": "Monto",
            "date": "Fecha",
            "status": "Estado",
            "notes": "Notas",
        }
        widgets = {
            "date": forms.DateInput(attrs={"type": "date"}),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }

    def clean(self):
        cleaned_data = super().clean()
        tx_type = cleaned_data.get("transaction_type")
        category = cleaned_data.get("category")
        destination_account = cleaned_data.get("destination_account")
        related_card = cleaned_data.get("related_credit_card")
        account = cleaned_data.get("account")
        amount = cleaned_data.get("amount")

        if amount is not None and amount <= 0:
            self.add_error("amount", "El monto debe ser mayor que cero.")
        if tx_type == FinancialTransaction.TransactionType.TRANSFER and not destination_account:
            self.add_error("destination_account", "Selecciona la cuenta destino para la transferencia.")
        if tx_type == FinancialTransaction.TransactionType.TRANSFER and destination_account and account == destination_account:
            self.add_error("destination_account", "La cuenta destino debe ser distinta de la cuenta origen.")
        if tx_type == FinancialTransaction.TransactionType.CARD_PAYMENT and not related_card:
            self.add_error("related_credit_card", "Selecciona la tarjeta que se esta pagando.")
        if tx_type != FinancialTransaction.TransactionType.TRANSFER:
            cleaned_data["destination_account"] = None
        if tx_type != FinancialTransaction.TransactionType.CARD_PAYMENT:
            cleaned_data["related_credit_card"] = None
        expected_category_type = {
            FinancialTransaction.TransactionType.INCOME: Category.CategoryType.INCOME,
            FinancialTransaction.TransactionType.COLLECTION: Category.CategoryType.INCOME,
            FinancialTransaction.TransactionType.EXPENSE: Category.CategoryType.EXPENSE,
            FinancialTransaction.TransactionType.CARD_PAYMENT: Category.CategoryType.EXPENSE,
            FinancialTransaction.TransactionType.TRANSFER: Category.CategoryType.TRANSFER,
        }.get(tx_type)
        if category and expected_category_type and category.category_type != expected_category_type:
            self.add_error("category", "La categoria no corresponde al tipo de movimiento seleccionado.")
        return cleaned_data


class InvoiceForm(UserScopedModelForm):
    class Meta:
        model = Invoice
        fields = ["invoice_type", "number", "counterparty", "issue_date", "due_date", "subtotal", "tax", "status"]
        labels = {
            "invoice_type": "Tipo",
            "number": "Numero",
            "counterparty": "Cliente o proveedor",
            "issue_date": "Fecha de emision",
            "due_date": "Fecha de vencimiento",
            "subtotal": "Subtotal",
            "tax": "Impuesto",
            "status": "Estado",
        }
        widgets = {
            "issue_date": forms.DateInput(attrs={"type": "date"}),
            "due_date": forms.DateInput(attrs={"type": "date"}),
        }

    def clean(self):
        cleaned_data = super().clean()
        subtotal = cleaned_data.get("subtotal")
        tax = cleaned_data.get("tax")
        if subtotal is not None and subtotal <= 0:
            self.add_error("subtotal", "El subtotal debe ser mayor que cero.")
        if tax is not None and tax < 0:
            self.add_error("tax", "El impuesto no puede ser negativo.")
        return cleaned_data


class RecurringPaymentForm(UserScopedModelForm):
    user_scoped_fields = ("account", "category")

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, user=user, **kwargs)
        self.fields["category"].queryset = self.fields["category"].queryset.filter(
            category_type=Category.CategoryType.EXPENSE
        )

    class Meta:
        model = RecurringPayment
        fields = ["name", "account", "category", "amount", "frequency", "next_due_date", "auto_create_transaction", "is_active"]
        labels = {
            "name": "Nombre",
            "account": "Cuenta",
            "category": "Categoria",
            "amount": "Monto",
            "frequency": "Frecuencia",
            "next_due_date": "Proximo vencimiento",
            "auto_create_transaction": "Crear movimiento automaticamente",
            "is_active": "Activo",
        }
        widgets = {
            "next_due_date": forms.DateInput(attrs={"type": "date"}),
        }

    def clean_category(self):
        category = self.cleaned_data.get("category")
        if category and category.category_type != Category.CategoryType.EXPENSE:
            raise forms.ValidationError("Los pagos recurrentes y suscripciones deben usar categorias de gasto.")
        return category

    def clean_amount(self):
        amount = self.cleaned_data.get("amount")
        if amount is not None and amount <= 0:
            raise forms.ValidationError("El monto debe ser mayor que cero.")
        return amount


class CreditCardForm(UserScopedModelForm):
    class Meta:
        model = CreditCard
        fields = [
            "account",
            "credit_limit",
            "current_debt",
            "annual_interest_rate",
            "monthly_service_rate",
            "previous_interest",
            "statement_number",
            "statement_balance",
            "statement_minimum_payment",
            "statement_cash_payment",
            "global_limit",
            "global_available",
            "global_balance",
            "statement_day",
            "payment_due_day",
            "minimum_payment_percent",
        ]
        labels = {
            "account": "Cuenta de tarjeta",
            "credit_limit": "Limite",
            "current_debt": "Deuda actual",
            "annual_interest_rate": "Tasa anual",
            "monthly_service_rate": "Tasa mensual estado",
            "previous_interest": "Interes anterior",
            "statement_number": "No. estado",
            "statement_balance": "Saldo estado",
            "statement_minimum_payment": "Pago minimo estado",
            "statement_cash_payment": "Pago contado estado",
            "global_limit": "Limite global",
            "global_available": "Disponible global",
            "global_balance": "Saldo global",
            "statement_day": "Dia de corte",
            "payment_due_day": "Dia limite de pago",
            "minimum_payment_percent": "Porcentaje de pago minimo",
        }
        help_texts = {
            "credit_limit": "Limite aprobado de la tarjeta.",
            "current_debt": "Monto usado o deuda pendiente. El disponible se calcula como limite menos deuda.",
            "monthly_service_rate": "Si tu estado indica tasa mensual, colocala aqui. Ejemplo: 1.53.",
            "statement_minimum_payment": "Si lo colocas, reemplaza el minimo estimado.",
            "statement_cash_payment": "Pago de contado exacto del estado.",
            "global_available": "Si lo colocas, reemplaza el disponible calculado.",
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, user=user, **kwargs)
        used_account_ids = list(CreditCard.objects.filter(user=user).values_list("account_id", flat=True))
        queryset = Account.objects.filter(
            user=user,
            account_type=Account.AccountType.CREDIT_CARD,
        )
        if self.instance and self.instance.pk:
            queryset = queryset.exclude(id__in=[account_id for account_id in used_account_ids if account_id != self.instance.account_id])
        else:
            queryset = queryset.exclude(id__in=used_account_ids)
        self.fields["account"].queryset = queryset

    def clean(self):
        cleaned_data = super().clean()
        credit_limit = cleaned_data.get("credit_limit")
        current_debt = cleaned_data.get("current_debt")
        annual_interest_rate = cleaned_data.get("annual_interest_rate")
        monthly_service_rate = cleaned_data.get("monthly_service_rate")
        minimum_payment_percent = cleaned_data.get("minimum_payment_percent")
        statement_day = cleaned_data.get("statement_day")
        payment_due_day = cleaned_data.get("payment_due_day")

        if credit_limit is not None and credit_limit <= 0:
            self.add_error("credit_limit", "El limite debe ser mayor que cero.")
        if current_debt is not None and current_debt < 0:
            self.add_error("current_debt", "La deuda actual no puede ser negativa.")
        if annual_interest_rate is not None and annual_interest_rate < 0:
            self.add_error("annual_interest_rate", "La tasa anual no puede ser negativa.")
        if monthly_service_rate is not None and monthly_service_rate < 0:
            self.add_error("monthly_service_rate", "La tasa mensual no puede ser negativa.")
        if minimum_payment_percent is not None and minimum_payment_percent <= 0:
            self.add_error("minimum_payment_percent", "El porcentaje de pago minimo debe ser mayor que cero.")
        if statement_day is not None and not 1 <= statement_day <= 31:
            self.add_error("statement_day", "El dia de corte debe estar entre 1 y 31.")
        if payment_due_day is not None and not 1 <= payment_due_day <= 31:
            self.add_error("payment_due_day", "El dia limite debe estar entre 1 y 31.")
        for field_name in (
            "previous_interest",
            "statement_balance",
            "statement_minimum_payment",
            "statement_cash_payment",
            "global_limit",
            "global_available",
            "global_balance",
        ):
            value = cleaned_data.get(field_name)
            if value is not None and value < 0:
                self.add_error(field_name, "Este valor no puede ser negativo.")
        return cleaned_data


class JournalEntryForm(UserScopedModelForm):
    class Meta:
        model = JournalEntry
        fields = ["date", "description", "source", "posted"]
        labels = {
            "date": "Fecha",
            "description": "Descripcion",
            "source": "Origen",
            "posted": "Publicado",
        }
        widgets = {
            "date": forms.DateInput(attrs={"type": "date"}),
        }


class JournalLineForm(forms.Form):
    account = forms.ModelChoiceField(queryset=Account.objects.none(), label="Cuenta")
    memo = forms.CharField(max_length=180, required=False, label="Memo")
    debit = forms.DecimalField(max_digits=14, decimal_places=2, required=False, min_value=0, label="Debe")
    credit = forms.DecimalField(max_digits=14, decimal_places=2, required=False, min_value=0, label="Haber")

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["account"].queryset = Account.objects.filter(user=user, is_active=True)
        for field in self.fields.values():
            if isinstance(field.widget, forms.Select):
                field.widget.attrs.setdefault("class", "form-select")
            else:
                field.widget.attrs.setdefault("class", "form-control")

    def clean(self):
        cleaned_data = super().clean()
        debit = cleaned_data.get("debit") or Decimal("0.00")
        credit = cleaned_data.get("credit") or Decimal("0.00")
        account = cleaned_data.get("account")
        if account and debit and credit:
            raise forms.ValidationError("Una linea no puede tener Debe y Haber al mismo tiempo.")
        if account and not debit and not credit:
            raise forms.ValidationError("Indica un valor en Debe o Haber.")
        return cleaned_data

    def is_empty(self):
        return not any(self.cleaned_data.get(field) for field in ("account", "memo", "debit", "credit"))


JournalLineFormSet = formset_factory(JournalLineForm, extra=4, min_num=2, validate_min=False)


class InitialSuperuserForm(forms.Form):
    username = forms.CharField(max_length=150, label="Usuario")
    email = forms.EmailField(required=False, label="Correo")
    password = forms.CharField(widget=forms.PasswordInput, label="Clave")
    password_confirm = forms.CharField(widget=forms.PasswordInput, label="Confirmar clave")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")

    def clean_username(self):
        username = self.cleaned_data["username"].strip()
        User = get_user_model()
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError("Ese usuario ya existe.")
        return username

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        password_confirm = cleaned_data.get("password_confirm")
        if password and password_confirm and password != password_confirm:
            self.add_error("password_confirm", "Las claves no coinciden.")
        if password:
            try:
                validate_password(password)
            except forms.ValidationError as exc:
                self.add_error("password", exc)
        return cleaned_data
