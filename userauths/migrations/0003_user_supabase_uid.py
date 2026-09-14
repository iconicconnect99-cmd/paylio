from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("userauths", "0002_user_is_approved_admin"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="supabase_uid",
            field=models.UUIDField(blank=True, editable=False, null=True, unique=True),
        ),
    ]
