from django.db import migrations


def backfill_received_transaction_notifications(apps, schema_editor):
    Transaction = apps.get_model("core", "Transaction")
    Notification = apps.get_model("core", "Notification")

    for transaction in Transaction.objects.filter(
        transaction_type="recieved",
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
        ("core", "0005_backfill_transfer_notifications"),
    ]

    operations = [
        migrations.RunPython(
            backfill_received_transaction_notifications,
            migrations.RunPython.noop,
        ),
    ]
