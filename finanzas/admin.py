from django.contrib import admin

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


class JournalLineInline(admin.TabularInline):
    model = JournalLine
    extra = 2


@admin.register(JournalEntry)
class JournalEntryAdmin(admin.ModelAdmin):
    list_display = ("date", "description", "source", "posted", "debit_total", "credit_total", "is_balanced")
    list_filter = ("posted", "date")
    search_fields = ("description", "source")
    inlines = [JournalLineInline]


@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    list_display = ("name", "account_type", "currency", "current_balance", "is_active")
    list_filter = ("account_type", "currency", "is_active")
    search_fields = ("name",)


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "category_type", "monthly_limit")
    list_filter = ("category_type",)
    search_fields = ("name",)


@admin.register(FinancialTransaction)
class FinancialTransactionAdmin(admin.ModelAdmin):
    list_display = ("date", "description", "transaction_type", "account", "category", "amount", "status")
    list_filter = ("transaction_type", "status", "date")
    list_select_related = ("account", "category")
    search_fields = ("description", "counterparty")
    date_hierarchy = "date"


@admin.register(RecurringPayment)
class RecurringPaymentAdmin(admin.ModelAdmin):
    list_display = ("name", "amount", "frequency", "next_due_date", "is_subscription", "is_active")
    list_filter = ("frequency", "is_subscription", "is_active")
    list_select_related = ("account", "category")
    search_fields = ("name",)


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ("number", "counterparty", "invoice_type", "issue_date", "due_date", "total", "status")
    list_filter = ("invoice_type", "status")
    search_fields = ("number", "counterparty")


@admin.register(CreditCard)
class CreditCardAdmin(admin.ModelAdmin):
    list_display = ("account", "credit_limit", "current_debt", "annual_interest_rate", "utilization_percent", "minimum_payment")
    list_select_related = ("account",)


@admin.register(FinancialAdviceRule)
class FinancialAdviceRuleAdmin(admin.ModelAdmin):
    list_display = ("code", "title", "is_active")
    list_filter = ("is_active",)
    search_fields = ("code", "title", "message")
