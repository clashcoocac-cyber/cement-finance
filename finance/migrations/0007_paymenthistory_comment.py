# Generated manually for adding comment field to PaymentHistory

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('finance', '0006_paymenthistory_payment_type'),
    ]

    operations = [
        migrations.AddField(
            model_name='paymenthistory',
            name='comment',
            field=models.TextField(blank=True, null=True, verbose_name='Izoh'),
        ),
    ]
