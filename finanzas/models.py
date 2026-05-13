from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Sum
from django.db.models.functions import Lower
from django.utils import timezone


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Account(TimeStampedModel):
    class AccountType(models.TextChoices):
        CASH = "cash", "Efectivo"
        CHECKING = "checking", "Cuenta corriente"
        BANK = "bank", "Banco"
        SAVINGS = "savings", "Ahorro"
        INVESTMENT = "investment", "Inversion"
        CREDIT_CARD = "credit_card", "Tarjeta de credito"
        LOAN = "loan", "Prestamo"
        RECEIVABLE = "receivable", "Cuenta por cobrar"
        PAYABLE = "payable", "Cuenta por pagar"
        CAPITAL = "capital", "Capital"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    name = models.CharField(max_length=120)
    account_type = models.CharField(max_length=32, choices=AccountType.choices)
    currency = models.CharField(max_length=3, default="USD")
    opening_balance = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    current_balance = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["account_type", "name"]
        unique_together = ["user", "name"]
        constraints = [
            models.UniqueConstraint(
                "user",
                Lower("name"),
                name="unique_account_name_ci_per_user",
            )
        ]

    def __str__(self):
        return f"{self.name} ({self.get_account_type_display()})"

    @property
    def balance_delta(self):
        return self.current_balance - self.opening_balance


class Category(TimeStampedModel):
    class CategoryType(models.TextChoices):
        INCOME = "income", "Ingreso"
        EXPENSE = "expense", "Gasto"
        TRANSFER = "transfer", "Transferencia"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    name = models.CharField(max_length=120)
    category_type = models.CharField(max_length=16, choices=CategoryType.choices)
    monthly_limit = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)

    class Meta:
        ordering = ["category_type", "name"]
        unique_together = ["user", "name", "category_type"]
        verbose_name_plural = "categories"
        constraints = [
            models.UniqueConstraint(
                "user",
                "category_type",
                Lower("name"),
                name="unique_category_name_ci_per_user_type",
            )
        ]

    def __str__(self):
        return self.name


class FinancialTransaction(TimeStampedModel):
    class TransactionType(models.TextChoices):
        INCOME = "income", "Ingreso"
        EXPENSE = "expense", "Gasto"
        TRANSFER = "transfer", "Transferencia"
        CARD_PAYMENT = "card_payment", "Pago de tarjeta"
        COLLECTION = "collection", "Cobro"

    class Status(models.TextChoices):
        PENDING = "pending", "Pendiente"
        CLEARED = "cleared", "Confirmado"
        VOID = "void", "Anulado"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    account = models.ForeignKey(Account, on_delete=models.PROTECT, related_name="transactions")
    destination_account = models.ForeignKey(
        Account,
        on_delete=models.PROTECT,
        related_name="incoming_transfers",
        null=True,
        blank=True,
    )
    source_recurring = models.ForeignKey(
        "RecurringPayment",
        on_delete=models.SET_NULL,
        related_name="generated_transactions",
        null=True,
        blank=True,
    )
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True)
    related_credit_card = models.ForeignKey("CreditCard", on_delete=models.SET_NULL, null=True, blank=True)
    journal_entry = models.ForeignKey("JournalEntry", on_delete=models.SET_NULL, null=True, blank=True, related_name="transactions")
    transaction_type = models.CharField(max_length=24, choices=TransactionType.choices)
    description = models.CharField(max_length=180)
    counterparty = models.CharField(max_length=140, blank=True)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    date = models.DateField(default=timezone.localdate)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.CLEARED)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-date", "-created_at"]

    def __str__(self):
        return f"{self.description} - {self.amount}"

    def signed_amount(self):
        if self.transaction_type in {self.TransactionType.EXPENSE, self.TransactionType.CARD_PAYMENT}:
            return self.amount * Decimal("-1")
        return self.amount


class JournalEntry(TimeStampedModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    date = models.DateField(default=timezone.localdate)
    description = models.CharField(max_length=200)
    source = models.CharField(max_length=80, blank=True)
    posted = models.BooleanField(default=True)

    class Meta:
        ordering = ["-date", "-created_at"]
        verbose_name_plural = "journal entries"

    def __str__(self):
        return self.description

    @property
    def debit_total(self):
        return self.lines.aggregate(total=Sum("debit"))["total"] or Decimal("0.00")

    @property
    def credit_total(self):
        return self.lines.aggregate(total=Sum("credit"))["total"] or Decimal("0.00")

    @property
    def is_balanced(self):
        return self.debit_total == self.credit_total

    def clean(self):
        super().clean()
        if self.pk and self.lines.exists() and not self.is_balanced:
            raise ValidationError("El asiento contable debe tener Debe y Haber iguales.")


class JournalLine(models.Model):
    entry = models.ForeignKey(JournalEntry, on_delete=models.CASCADE, related_name="lines")
    account = models.ForeignKey(Account, on_delete=models.PROTECT)
    memo = models.CharField(max_length=180, blank=True)
    debit = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    credit = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    class Meta:
        ordering = ["id"]

    def clean(self):
        super().clean()
        if self.debit and self.credit:
            raise ValidationError("Una linea no puede tener Debe y Haber al mismo tiempo.")
        if not self.debit and not self.credit:
            raise ValidationError("Una linea debe tener Debe o Haber.")

    def __str__(self):
        return f"{self.account}: D {self.debit} / H {self.credit}"


class RecurringPayment(TimeStampedModel):
    class ExecutionStatus(models.TextChoices):
        SUCCESS = "success", "Correcto"
        SKIPPED = "skipped", "Sin cambios"
        ERROR = "error", "Error"

    class Frequency(models.TextChoices):
        WEEKLY = "weekly", "Semanal"
        BIWEEKLY = "biweekly", "Quincenal"
        MONTHLY = "monthly", "Mensual"
        QUARTERLY = "quarterly", "Trimestral"
        YEARLY = "yearly", "Anual"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    name = models.CharField(max_length=140)
    account = models.ForeignKey(Account, on_delete=models.PROTECT)
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    frequency = models.CharField(max_length=16, choices=Frequency.choices, default=Frequency.MONTHLY)
    next_due_date = models.DateField()
    auto_create_transaction = models.BooleanField(default=False)
    is_subscription = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    last_execution_at = models.DateTimeField(null=True, blank=True)
    last_execution_status = models.CharField(max_length=16, choices=ExecutionStatus.choices, blank=True, default="")
    last_execution_message = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["next_due_date", "name"]

    def __str__(self):
        return self.name


class Invoice(TimeStampedModel):
    class InvoiceType(models.TextChoices):
        ISSUED = "issued", "Emitida"
        RECEIVED = "received", "Recibida"

    class Status(models.TextChoices):
        DRAFT = "draft", "Borrador"
        PENDING = "pending", "Pendiente"
        PAID = "paid", "Pagada"
        OVERDUE = "overdue", "Vencida"
        VOID = "void", "Anulada"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    invoice_type = models.CharField(max_length=16, choices=InvoiceType.choices)
    number = models.CharField(max_length=40)
    counterparty = models.CharField(max_length=160)
    issue_date = models.DateField(default=timezone.localdate)
    due_date = models.DateField(null=True, blank=True)
    subtotal = models.DecimalField(max_digits=14, decimal_places=2)
    tax = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    journal_entry = models.ForeignKey("JournalEntry", on_delete=models.SET_NULL, null=True, blank=True, related_name="invoices")

    class Meta:
        ordering = ["-issue_date", "-created_at"]
        unique_together = ["user", "number", "invoice_type"]

    @property
    def total(self):
        return self.subtotal + self.tax

    def __str__(self):
        return f"{self.number} - {self.counterparty}"


class CreditCard(TimeStampedModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    account = models.OneToOneField(Account, on_delete=models.CASCADE, limit_choices_to={"account_type": Account.AccountType.CREDIT_CARD})
    credit_limit = models.DecimalField(max_digits=14, decimal_places=2)
    current_debt = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    annual_interest_rate = models.DecimalField(max_digits=5, decimal_places=2, help_text="Tasa anual en porcentaje")
    monthly_service_rate = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, help_text="Tasa mensual del estado de cuenta")
    previous_interest = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    statement_number = models.CharField(max_length=20, blank=True)
    statement_balance = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    statement_minimum_payment = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    statement_cash_payment = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    global_limit = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    global_available = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    global_balance = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    statement_day = models.PositiveSmallIntegerField(default=15)
    payment_due_day = models.PositiveSmallIntegerField(default=30)
    minimum_payment_percent = models.DecimalField(max_digits=5, decimal_places=2, default=3)

    class Meta:
        ordering = ["account__name"]

    @property
    def utilization_percent(self):
        if not self.effective_limit:
            return Decimal("0.00")
        return (self.effective_balance / self.effective_limit * Decimal("100")).quantize(Decimal("0.01"))

    @property
    def available_credit(self):
        if self.global_available is not None:
            return self.global_available.quantize(Decimal("0.01"))
        return (self.effective_limit - self.effective_balance).quantize(Decimal("0.01"))

    @property
    def effective_limit(self):
        return (self.global_limit if self.global_limit is not None else self.credit_limit).quantize(Decimal("0.01"))

    @property
    def effective_balance(self):
        return (self.global_balance if self.global_balance is not None else self.current_debt).quantize(Decimal("0.01"))

    @property
    def monthly_interest_rate(self):
        if self.monthly_service_rate is not None:
            return (self.monthly_service_rate / Decimal("100")).quantize(Decimal("0.0001"))
        return (self.annual_interest_rate / Decimal("12") / Decimal("100")).quantize(Decimal("0.0001"))

    @property
    def monthly_interest_percent(self):
        if self.monthly_service_rate is not None:
            return self.monthly_service_rate.quantize(Decimal("0.01"))
        return (self.annual_interest_rate / Decimal("12")).quantize(Decimal("0.01"))

    @property
    def interest_basis(self):
        if self.statement_balance is not None:
            return self.statement_balance.quantize(Decimal("0.01"))
        return self.current_debt.quantize(Decimal("0.01"))

    @property
    def monthly_interest_amount(self):
        return (self.interest_basis * self.monthly_interest_rate).quantize(Decimal("0.01"))

    @property
    def feci_applies(self):
        return self.interest_basis > Decimal("5000.00")

    @property
    def feci_annual_rate_percent(self):
        configured_rate = getattr(settings, "MONETA_FECI_ANNUAL_RATE_PERCENT", Decimal("1.00"))
        return Decimal(str(configured_rate)).quantize(Decimal("0.01"))

    @property
    def monthly_feci_amount(self):
        if not self.feci_applies:
            return Decimal("0.00")
        monthly_rate = (self.feci_annual_rate_percent / Decimal("100")) / Decimal("12")
        return (self.interest_basis * monthly_rate).quantize(Decimal("0.01"))

    @property
    def monthly_finance_charges(self):
        return (self.monthly_interest_amount + self.monthly_feci_amount).quantize(Decimal("0.01"))

    @property
    def minimum_payment(self):
        if self.statement_minimum_payment is not None:
            return self.statement_minimum_payment.quantize(Decimal("0.01"))
        balance = self.effective_balance
        amount = balance * (self.minimum_payment_percent / Decimal("100"))
        return max(amount, Decimal("25.00")).quantize(Decimal("0.01")) if balance else Decimal("0.00")

    @property
    def cash_payment(self):
        if self.statement_cash_payment is not None:
            return self.statement_cash_payment.quantize(Decimal("0.01"))
        if self.statement_balance is not None:
            return self.statement_balance.quantize(Decimal("0.01"))
        return self.current_debt.quantize(Decimal("0.01"))

    def recommended_payment(self):
        if not self.interest_basis:
            return Decimal("0.00")
        principal_target = self.interest_basis * Decimal("0.08")
        return (self.monthly_finance_charges + principal_target).quantize(Decimal("0.01"))

    def __str__(self):
        return self.account.name


class FinancialAdviceRule(TimeStampedModel):
    code = models.SlugField(unique=True)
    title = models.CharField(max_length=160)
    message = models.TextField()
    trigger_description = models.CharField(max_length=240)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["code"]

    def __str__(self):
        return self.title
