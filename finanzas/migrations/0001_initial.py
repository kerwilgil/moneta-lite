# Generated manually for the initial Moneta schema.
import decimal

import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="FinancialAdviceRule",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("code", models.SlugField(unique=True)),
                ("title", models.CharField(max_length=160)),
                ("message", models.TextField()),
                ("trigger_description", models.CharField(max_length=240)),
                ("is_active", models.BooleanField(default=True)),
            ],
            options={"ordering": ["code"]},
        ),
        migrations.CreateModel(
            name="Account",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("name", models.CharField(max_length=120)),
                (
                    "account_type",
                    models.CharField(
                        choices=[
                            ("cash", "Efectivo"),
                            ("bank", "Banco"),
                            ("savings", "Ahorro"),
                            ("investment", "Inversion"),
                            ("credit_card", "Tarjeta de credito"),
                            ("loan", "Prestamo"),
                            ("receivable", "Cuenta por cobrar"),
                            ("payable", "Cuenta por pagar"),
                            ("capital", "Capital"),
                        ],
                        max_length=32,
                    ),
                ),
                ("currency", models.CharField(default="USD", max_length=3)),
                ("opening_balance", models.DecimalField(decimal_places=2, default=0, max_digits=14)),
                ("current_balance", models.DecimalField(decimal_places=2, default=0, max_digits=14)),
                ("is_active", models.BooleanField(default=True)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["account_type", "name"], "unique_together": {("user", "name")}},
        ),
        migrations.CreateModel(
            name="Category",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("name", models.CharField(max_length=120)),
                (
                    "category_type",
                    models.CharField(
                        choices=[("income", "Ingreso"), ("expense", "Gasto"), ("transfer", "Transferencia")],
                        max_length=16,
                    ),
                ),
                ("monthly_limit", models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "verbose_name_plural": "categories",
                "ordering": ["category_type", "name"],
                "unique_together": {("user", "name", "category_type")},
            },
        ),
        migrations.CreateModel(
            name="CreditCard",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("credit_limit", models.DecimalField(decimal_places=2, max_digits=14)),
                ("current_debt", models.DecimalField(decimal_places=2, default=0, max_digits=14)),
                ("annual_interest_rate", models.DecimalField(decimal_places=2, help_text="Tasa anual en porcentaje", max_digits=5)),
                ("statement_day", models.PositiveSmallIntegerField(default=15)),
                ("payment_due_day", models.PositiveSmallIntegerField(default=30)),
                ("minimum_payment_percent", models.DecimalField(decimal_places=2, default=3, max_digits=5)),
                (
                    "account",
                    models.OneToOneField(
                        limit_choices_to={"account_type": "credit_card"},
                        on_delete=django.db.models.deletion.CASCADE,
                        to="finanzas.account",
                    ),
                ),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["account__name"]},
        ),
        migrations.CreateModel(
            name="FinancialTransaction",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "transaction_type",
                    models.CharField(
                        choices=[
                            ("income", "Ingreso"),
                            ("expense", "Gasto"),
                            ("transfer", "Transferencia"),
                            ("card_payment", "Pago de tarjeta"),
                            ("collection", "Cobro"),
                        ],
                        max_length=24,
                    ),
                ),
                ("description", models.CharField(max_length=180)),
                ("counterparty", models.CharField(blank=True, max_length=140)),
                ("amount", models.DecimalField(decimal_places=2, max_digits=14)),
                ("date", models.DateField(default=django.utils.timezone.localdate)),
                (
                    "status",
                    models.CharField(
                        choices=[("pending", "Pendiente"), ("cleared", "Confirmado"), ("void", "Anulado")],
                        default="cleared",
                        max_length=16,
                    ),
                ),
                ("notes", models.TextField(blank=True)),
                (
                    "account",
                    models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="transactions", to="finanzas.account"),
                ),
                ("category", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to="finanzas.category")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-date", "-created_at"]},
        ),
        migrations.CreateModel(
            name="Invoice",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("invoice_type", models.CharField(choices=[("issued", "Emitida"), ("received", "Recibida")], max_length=16)),
                ("number", models.CharField(max_length=40)),
                ("counterparty", models.CharField(max_length=160)),
                ("issue_date", models.DateField(default=django.utils.timezone.localdate)),
                ("due_date", models.DateField(blank=True, null=True)),
                ("subtotal", models.DecimalField(decimal_places=2, max_digits=14)),
                ("tax", models.DecimalField(decimal_places=2, default=0, max_digits=14)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("draft", "Borrador"),
                            ("pending", "Pendiente"),
                            ("paid", "Pagada"),
                            ("overdue", "Vencida"),
                            ("void", "Anulada"),
                        ],
                        default="pending",
                        max_length=16,
                    ),
                ),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-issue_date", "-created_at"], "unique_together": {("user", "number", "invoice_type")}},
        ),
        migrations.CreateModel(
            name="JournalEntry",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("date", models.DateField(default=django.utils.timezone.localdate)),
                ("description", models.CharField(max_length=200)),
                ("source", models.CharField(blank=True, max_length=80)),
                ("posted", models.BooleanField(default=True)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
            options={"verbose_name_plural": "journal entries", "ordering": ["-date", "-created_at"]},
        ),
        migrations.CreateModel(
            name="RecurringPayment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("name", models.CharField(max_length=140)),
                ("amount", models.DecimalField(decimal_places=2, max_digits=12)),
                (
                    "frequency",
                    models.CharField(
                        choices=[
                            ("weekly", "Semanal"),
                            ("biweekly", "Quincenal"),
                            ("monthly", "Mensual"),
                            ("quarterly", "Trimestral"),
                            ("yearly", "Anual"),
                        ],
                        default="monthly",
                        max_length=16,
                    ),
                ),
                ("next_due_date", models.DateField()),
                ("auto_create_transaction", models.BooleanField(default=False)),
                ("is_subscription", models.BooleanField(default=False)),
                ("is_active", models.BooleanField(default=True)),
                ("account", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="finanzas.account")),
                ("category", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to="finanzas.category")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["next_due_date", "name"]},
        ),
        migrations.CreateModel(
            name="JournalLine",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("memo", models.CharField(blank=True, max_length=180)),
                ("debit", models.DecimalField(decimal_places=2, default=0, max_digits=14)),
                ("credit", models.DecimalField(decimal_places=2, default=0, max_digits=14)),
                ("account", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="finanzas.account")),
                ("entry", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="lines", to="finanzas.journalentry")),
            ],
            options={"ordering": ["id"]},
        ),
    ]
