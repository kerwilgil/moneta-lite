from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("finanzas", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="financialtransaction",
            name="destination_account",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="incoming_transfers",
                to="finanzas.account",
            ),
        ),
        migrations.AddField(
            model_name="financialtransaction",
            name="journal_entry",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="transactions",
                to="finanzas.journalentry",
            ),
        ),
        migrations.AddField(
            model_name="financialtransaction",
            name="related_credit_card",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                to="finanzas.creditcard",
            ),
        ),
        migrations.AddField(
            model_name="invoice",
            name="journal_entry",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="invoices",
                to="finanzas.journalentry",
            ),
        ),
    ]
