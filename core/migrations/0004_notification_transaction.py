from django.db import migrations, models
import django.db.models.deletion


def backfill_transfer_notifications(apps, schema_editor):
    Transaction = apps.get_model("core", "Transaction")
    Notification = apps.get_model("core", "Notification")

    for transaction in Transaction.objects.filter(
        transaction_type="transfer",
        status="completed",
    ).exclude(reciever_id=None):
        Notification.objects.get_or_create(
            transaction_id=transaction.id,
            defaults={
                "user_id": transaction.reciever_id,
                "notification_type": "Credit Alert",
                "amount": transaction.amount,
            },
        )


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0008_alter_transaction_updated"),
    ]

    operations = [
        migrations.AddField(
            model_name="notification",
            name="transaction",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="notifications",
                to="core.transaction",
            ),
        ),
        migrations.RunPython(
            backfill_transfer_notifications,
            migrations.RunPython.noop,
        ),
    ]
