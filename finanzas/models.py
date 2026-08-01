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


class SetupState(models.Model):
    """Single row used to claim browser-based bootstrap exactly once."""

    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    consumed_at = models.DateTimeField(null=True, blank=True)


class LoginThrottle(models.Model):
    """Persistent account+network throttle without raw identifiers at rest."""

    network_hash = models.CharField(max_length=64)
    identity_hash = models.CharField(max_length=64)
    attempts = models.PositiveSmallIntegerField(default=0)
    locked_until = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["network_hash", "identity_hash"],
                name="unique_login_throttle_identity_network",
            )
        ]
        indexes = [models.Index(fields=["locked_until"])]


class Account(TimeStampedModel):
    """A user-owned financial account whose balance can be rebuilt from transactions."""

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
    """A user-owned classification for income, expenses or transfers."""

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
            ),
            models.CheckConstraint(
                condition=models.Q(monthly_limit__isnull=True) | models.Q(monthly_limit__gt=0),
                name="category_monthly_limit_positive",
            ),
        ]

    def __str__(self):
        return self.name


class FinancialTransaction(TimeStampedModel):
    """A money movement that may affect balances and automatic journal entries."""

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
        indexes = [
            models.Index(fields=["user", "-date"]),
            models.Index(fields=["user", "status"]),
        ]
        constraints = [
            models.CheckConstraint(condition=models.Q(amount__gt=0), name="transaction_amount_positive"),
            models.UniqueConstraint(
                fields=["source_recurring", "date"],
                condition=models.Q(source_recurring__isnull=False) & ~models.Q(status="void"),
                name="unique_active_recurring_occurrence",
            ),
        ]

    def __str__(self):
        return f"{self.description} - {self.amount}"

    def signed_amount(self):
        if self.transaction_type in {self.TransactionType.EXPENSE, self.TransactionType.CARD_PAYMENT}:
            return self.amount * Decimal("-1")
        return self.amount

    def clean(self):
        super().clean()
        errors = {}
        if self.account_id and self.user_id and self.account.user_id != self.user_id:
            errors["account"] = "La cuenta debe pertenecer al mismo usuario."
        if self.destination_account_id and self.user_id and self.destination_account.user_id != self.user_id:
            errors["destination_account"] = "La cuenta destino debe pertenecer al mismo usuario."
        if self.category_id and self.user_id and self.category.user_id != self.user_id:
            errors["category"] = "La categoria debe pertenecer al mismo usuario."
        if self.related_credit_card_id and self.user_id and self.related_credit_card.user_id != self.user_id:
            errors["related_credit_card"] = "La tarjeta debe pertenecer al mismo usuario."
        if self.journal_entry_id and self.user_id and self.journal_entry.user_id != self.user_id:
            errors["journal_entry"] = "El asiento debe pertenecer al mismo usuario."
        if self.source_recurring_id and self.user_id and self.source_recurring.user_id != self.user_id:
            errors["source_recurring"] = "El recurrente debe pertenecer al mismo usuario."
        if self.amount is not None and self.amount <= 0:
            errors["amount"] = "El monto debe ser mayor que cero."
        if self.transaction_type == self.TransactionType.TRANSFER:
            if not self.destination_account_id:
                errors["destination_account"] = "Selecciona una cuenta destino."
            elif self.destination_account_id == self.account_id:
                errors["destination_account"] = "La cuenta destino debe ser distinta."
        elif self.destination_account_id:
            errors["destination_account"] = "Solo las transferencias pueden tener cuenta destino."
        if self.transaction_type == self.TransactionType.CARD_PAYMENT:
            if not self.related_credit_card_id:
                errors["related_credit_card"] = "Selecciona la tarjeta pagada."
        elif self.related_credit_card_id:
            errors["related_credit_card"] = "Solo los pagos de tarjeta pueden vincular una tarjeta."
        if errors:
            raise ValidationError(errors)


class JournalEntry(TimeStampedModel):
    """Accounting entry header for manual or automatic Debe/Haber lines."""

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

    def save(self, *args, **kwargs):
        if self.pk and not kwargs.get("update_fields"):
            if self.lines.exists() and not self.is_balanced:
                raise ValidationError("El asiento contable debe tener Debe y Haber iguales.")
        super().save(*args, **kwargs)


class JournalLine(models.Model):
    """One debit or credit line inside a journal entry."""

    entry = models.ForeignKey(JournalEntry, on_delete=models.CASCADE, related_name="lines")
    account = models.ForeignKey(Account, on_delete=models.PROTECT)
    memo = models.CharField(max_length=180, blank=True)
    debit = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    credit = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    class Meta:
        ordering = ["id"]
        constraints = [
            models.CheckConstraint(
                condition=(models.Q(debit__gt=0, credit=0) | models.Q(credit__gt=0, debit=0)),
                name="journal_line_exactly_one_side",
            )
        ]

    def clean(self):
        super().clean()
        if self.debit and self.credit:
            raise ValidationError("Una linea no puede tener Debe y Haber al mismo tiempo.")
        if not self.debit and not self.credit:
            raise ValidationError("Una linea debe tener Debe o Haber.")
        if self.entry_id and self.account_id and self.entry.user_id != self.account.user_id:
            raise ValidationError({"account": "La cuenta y el asiento deben pertenecer al mismo usuario."})

    def __str__(self):
        return f"{self.account}: D {self.debit} / H {self.credit}"


class RecurringPayment(TimeStampedModel):
    """A scheduled expense; subscriptions are represented with is_subscription."""

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

    class SubscriptionCatalog(models.TextChoices):
        SERVICE = "service", "Servicio"
        INSURANCE = "insurance", "Seguro"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    name = models.CharField(max_length=140)
    account = models.ForeignKey(Account, on_delete=models.PROTECT)
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    transaction_type = models.CharField(
        max_length=24,
        choices=[
            (FinancialTransaction.TransactionType.INCOME, "Ingreso"),
            (FinancialTransaction.TransactionType.EXPENSE, "Gasto"),
        ],
        default=FinancialTransaction.TransactionType.EXPENSE,
    )
    frequency = models.CharField(max_length=16, choices=Frequency.choices, default=Frequency.MONTHLY)
    next_due_date = models.DateField()
    auto_create_transaction = models.BooleanField(default=False)
    is_subscription = models.BooleanField(default=False)
    subscription_catalog = models.CharField(
        max_length=16,
        choices=SubscriptionCatalog.choices,
        default=SubscriptionCatalog.SERVICE,
    )
    is_active = models.BooleanField(default=True)
    last_execution_at = models.DateTimeField(null=True, blank=True)
    last_execution_status = models.CharField(max_length=16, choices=ExecutionStatus.choices, blank=True, default="")
    last_execution_message = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["next_due_date", "name"]
        indexes = [
            models.Index(fields=["user", "is_subscription", "next_due_date"]),
        ]
        constraints = [models.CheckConstraint(condition=models.Q(amount__gt=0), name="recurring_amount_positive")]

    def __str__(self):
        return self.name

    def clean(self):
        super().clean()
        errors = {}
        if self.account_id and self.user_id and self.account.user_id != self.user_id:
            errors["account"] = "La cuenta debe pertenecer al mismo usuario."
        if self.category_id and self.user_id and self.category.user_id != self.user_id:
            errors["category"] = "La categoria debe pertenecer al mismo usuario."
        if self.amount is not None and self.amount <= 0:
            errors["amount"] = "El monto debe ser mayor que cero."
        expected_category = {
            FinancialTransaction.TransactionType.INCOME: Category.CategoryType.INCOME,
            FinancialTransaction.TransactionType.EXPENSE: Category.CategoryType.EXPENSE,
        }.get(self.transaction_type)
        if self.category_id and expected_category and self.category.category_type != expected_category:
            errors["category"] = "La categoria no corresponde al tipo de movimiento."
        if errors:
            raise ValidationError(errors)


class Invoice(TimeStampedModel):
    """An issued or received invoice with optional automatic accounting entry."""

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
        constraints = [
            models.CheckConstraint(condition=models.Q(subtotal__gt=0), name="invoice_subtotal_positive"),
            models.CheckConstraint(condition=models.Q(tax__gte=0), name="invoice_tax_nonnegative"),
        ]

    @property
    def total(self):
        return self.subtotal + self.tax

    def __str__(self):
        return f"{self.number} - {self.counterparty}"

    def clean(self):
        super().clean()
        errors = {}
        if self.subtotal is not None and self.subtotal <= 0:
            errors["subtotal"] = "El subtotal debe ser mayor que cero."
        if self.tax is not None and self.tax < 0:
            errors["tax"] = "El impuesto no puede ser negativo."
        if self.due_date and self.issue_date and self.due_date < self.issue_date:
            errors["due_date"] = "El vencimiento no puede ser anterior a la emision."
        if self.journal_entry_id and self.user_id and self.journal_entry.user_id != self.user_id:
            errors["journal_entry"] = "El asiento debe pertenecer al mismo usuario."
        if errors:
            raise ValidationError(errors)


class CreditCard(TimeStampedModel):
    """Credit card configuration and statement-derived finance calculations."""

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
        constraints = [
            models.CheckConstraint(condition=models.Q(credit_limit__gt=0), name="credit_card_limit_positive"),
            models.CheckConstraint(condition=models.Q(current_debt__gte=0), name="credit_card_debt_nonnegative"),
            models.CheckConstraint(condition=models.Q(annual_interest_rate__gte=0), name="credit_card_interest_nonnegative"),
            models.CheckConstraint(condition=models.Q(statement_day__gte=1, statement_day__lte=31), name="credit_card_statement_day_range"),
            models.CheckConstraint(condition=models.Q(payment_due_day__gte=1, payment_due_day__lte=31), name="credit_card_due_day_range"),
        ]

    def clean(self):
        super().clean()
        errors = {}
        if self.account_id and self.user_id and self.account.user_id != self.user_id:
            errors["account"] = "La cuenta debe pertenecer al mismo usuario."
        if self.account_id and self.account.account_type != Account.AccountType.CREDIT_CARD:
            errors["account"] = "La cuenta vinculada debe ser de tipo tarjeta de credito."
        if errors:
            raise ValidationError(errors)

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
        try:
            configured_rate = getattr(settings, "MONETA_FECI_ANNUAL_RATE_PERCENT", Decimal("1.00"))
            return Decimal(str(configured_rate)).quantize(Decimal("0.01"))
        except Exception:
            return Decimal("1.00")

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
    """Configurable metadata for financial advice rules."""

    code = models.SlugField(unique=True)
    title = models.CharField(max_length=160)
    message = models.TextField()
    trigger_description = models.CharField(max_length=240)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["code"]

    def __str__(self):
        return self.title
