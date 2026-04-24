from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("finanzas", "0004_checking_account_type"),
    ]

    operations = [
        migrations.AddField(
            model_name="creditcard",
            name="monthly_service_rate",
            field=models.DecimalField(blank=True, decimal_places=2, help_text="Tasa mensual del estado de cuenta", max_digits=5, null=True),
        ),
        migrations.AddField(
            model_name="creditcard",
            name="previous_interest",
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=14, null=True),
        ),
        migrations.AddField(
            model_name="creditcard",
            name="statement_number",
            field=models.CharField(blank=True, max_length=20),
        ),
        migrations.AddField(
            model_name="creditcard",
            name="statement_balance",
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=14, null=True),
        ),
        migrations.AddField(
            model_name="creditcard",
            name="statement_minimum_payment",
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=14, null=True),
        ),
        migrations.AddField(
            model_name="creditcard",
            name="statement_cash_payment",
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=14, null=True),
        ),
        migrations.AddField(
            model_name="creditcard",
            name="global_limit",
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=14, null=True),
        ),
        migrations.AddField(
            model_name="creditcard",
            name="global_available",
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=14, null=True),
        ),
        migrations.AddField(
            model_name="creditcard",
            name="global_balance",
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=14, null=True),
        ),
    ]
