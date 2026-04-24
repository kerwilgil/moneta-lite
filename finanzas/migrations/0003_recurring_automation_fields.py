from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("finanzas", "0002_transaction_invoice_journal_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="financialtransaction",
            name="source_recurring",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="generated_transactions",
                to="finanzas.recurringpayment",
            ),
        ),
        migrations.AddField(
            model_name="recurringpayment",
            name="last_execution_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="recurringpayment",
            name="last_execution_message",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name="recurringpayment",
            name="last_execution_status",
            field=models.CharField(
                blank=True,
                choices=[("success", "Correcto"), ("skipped", "Sin cambios"), ("error", "Error")],
                default="",
                max_length=16,
            ),
        ),
    ]
