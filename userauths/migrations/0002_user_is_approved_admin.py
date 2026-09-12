from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("userauths", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="is_approved_admin",
            field=models.BooleanField(default=False),
        ),
    ]
