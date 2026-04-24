from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("finanzas", "0003_recurring_automation_fields"),
    ]

    operations = [
        migrations.AlterField(
            model_name="account",
            name="account_type",
            field=models.CharField(
                choices=[
                    ("cash", "Efectivo"),
                    ("checking", "Cuenta corriente"),
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
    ]
