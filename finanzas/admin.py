from django.contrib import admin
from django.core.exceptions import ValidationError
from django.forms.models import BaseInlineFormSet
from django.db import transaction

from .accounting import (
    delete_invoice_journal, delete_transaction_journal, lock_financial_user,
    rebuild_account_balances, sync_credit_card_account_balance,
    sync_invoice_journal, sync_transaction_journal,
)

from .models import (
    Account,
    Category,
    CreditCard,
    FinancialAdviceRule,
    FinancialTransaction,
    Invoice,
    JournalEntry,
    JournalLine,
    RecurringPayment,
)


class TenantAdminMixin:
    """Model permissions grant access to the actor's records, not all tenants.

    Installation superusers remain trusted administrators. Ordinary staff use
    the same ownership boundary as the application, including related choices
    and bulk actions (which consume get_queryset).
    """

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs if request.user.is_superuser else qs.filter(user=request.user)

    def get_exclude(self, request, obj=None):
        excluded = list(super().get_exclude(request, obj) or [])
        if not request.user.is_superuser:
            excluded.append("user")
        return excluded

    def get_readonly_fields(self, request, obj=None):
        fields = list(super().get_readonly_fields(request, obj))
        if obj and request.user.is_superuser:
            fields.append("user")
        return fields

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        related = db_field.remote_field.model
        if not request.user.is_superuser and any(f.name == "user" for f in related._meta.fields):
            kwargs["queryset"] = related.objects.filter(user=request.user)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    @staticmethod
    def _account_ids(obj):
        if isinstance(obj, Account):
            return {obj.pk}
        ids = {getattr(obj, "account_id", None), getattr(obj, "destination_account_id", None)}
        if getattr(obj, "related_credit_card_id", None):
            ids.add(obj.related_credit_card.account_id)
        return ids - {None}

    @transaction.atomic
    def save_model(self, request, obj, form, change):
        if not request.user.is_superuser:
            obj.user = request.user
        lock_financial_user(obj.user)
        account_ids = self._account_ids(obj)
        if change:
            previous = self.model.objects.get(pk=obj.pk)
            account_ids |= self._account_ids(previous)
        obj.full_clean()
        super().save_model(request, obj, form, change)
        if isinstance(obj, FinancialTransaction):
            sync_transaction_journal(obj)
            rebuild_account_balances(obj.user, force_account_ids=account_ids)
        elif isinstance(obj, Invoice):
            sync_invoice_journal(obj)
        elif isinstance(obj, Account):
            sync_credit_card_account_balance(obj)
            rebuild_account_balances(obj.user, force_account_ids=[obj.pk])
        elif isinstance(obj, CreditCard):
            rebuild_account_balances(obj.user, force_account_ids=account_ids)
            sync_credit_card_account_balance(obj)

    @transaction.atomic
    def delete_model(self, request, obj):
        lock_financial_user(obj.user)
        user = obj.user
        account_ids = self._account_ids(obj)
        if isinstance(obj, FinancialTransaction):
            delete_transaction_journal(obj)
        elif isinstance(obj, Invoice):
            delete_invoice_journal(obj)
        super().delete_model(request, obj)
        if isinstance(obj, (FinancialTransaction, CreditCard)):
            rebuild_account_balances(user, force_account_ids=account_ids)

    @transaction.atomic
    def delete_queryset(self, request, queryset):
        # Bulk deletion must preserve the financial hooks and scoped queryset.
        for obj in queryset:
            self.delete_model(request, obj)


class BalancedJournalLineFormSet(BaseInlineFormSet):
    def clean(self):
        super().clean()
        if any(self.errors):
            return
        debit_total = 0
        credit_total = 0
        line_count = 0
        for form in self.forms:
            data = getattr(form, "cleaned_data", {})
            if not data or data.get("DELETE"):
                continue
            account = data.get("account")
            if not account:
                continue
            if self.instance.user_id and account.user_id != self.instance.user_id:
                raise ValidationError("Todas las cuentas deben pertenecer al usuario del asiento.")
            debit_total += data.get("debit") or 0
            credit_total += data.get("credit") or 0
            line_count += 1
        if line_count < 2:
            raise ValidationError("El asiento necesita al menos dos lineas.")
        if debit_total != credit_total:
            raise ValidationError("El asiento debe mantener Debe y Haber iguales.")


class JournalLineInline(admin.TabularInline):
    model = JournalLine
    formset = BalancedJournalLineFormSet
    extra = 2

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "account" and not request.user.is_superuser:
            kwargs["queryset"] = Account.objects.filter(user=request.user)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(JournalEntry)
class JournalEntryAdmin(TenantAdminMixin, admin.ModelAdmin):
    list_display = ("date", "description", "source", "posted", "debit_total", "credit_total", "is_balanced")
    list_filter = ("posted", "date")
    search_fields = ("description", "source")
    inlines = [JournalLineInline]


@admin.register(Account)
class AccountAdmin(TenantAdminMixin, admin.ModelAdmin):
    list_display = ("name", "account_type", "currency", "current_balance", "is_active")
    list_filter = ("account_type", "currency", "is_active")
    search_fields = ("name",)


@admin.register(Category)
class CategoryAdmin(TenantAdminMixin, admin.ModelAdmin):
    list_display = ("name", "category_type", "monthly_limit")
    list_filter = ("category_type",)
    search_fields = ("name",)


@admin.register(FinancialTransaction)
class FinancialTransactionAdmin(TenantAdminMixin, admin.ModelAdmin):
    list_display = ("date", "description", "transaction_type", "account", "category", "amount", "status")
    list_filter = ("transaction_type", "status", "date")
    list_select_related = ("account", "category")
    search_fields = ("description", "counterparty")
    date_hierarchy = "date"


@admin.register(RecurringPayment)
class RecurringPaymentAdmin(TenantAdminMixin, admin.ModelAdmin):
    list_display = ("name", "amount", "frequency", "next_due_date", "is_subscription", "is_active")
    list_filter = ("frequency", "is_subscription", "is_active")
    list_select_related = ("account", "category")
    search_fields = ("name",)


@admin.register(Invoice)
class InvoiceAdmin(TenantAdminMixin, admin.ModelAdmin):
    list_display = ("number", "counterparty", "invoice_type", "issue_date", "due_date", "total", "status")
    list_filter = ("invoice_type", "status")
    search_fields = ("number", "counterparty")


@admin.register(CreditCard)
class CreditCardAdmin(TenantAdminMixin, admin.ModelAdmin):
    list_display = ("account", "credit_limit", "current_debt", "annual_interest_rate", "utilization_percent", "minimum_payment")
    list_select_related = ("account",)


@admin.register(FinancialAdviceRule)
class FinancialAdviceRuleAdmin(admin.ModelAdmin):
    list_display = ("code", "title", "is_active")
    list_filter = ("is_active",)
    search_fields = ("code", "title", "message")
