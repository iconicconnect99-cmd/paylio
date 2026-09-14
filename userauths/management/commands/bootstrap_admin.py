import os

from django.core.management.base import BaseCommand, CommandError

from userauths.models import User


class Command(BaseCommand):
    help = "Create or repair the production Paylio superuser from environment variables."

    def add_arguments(self, parser):
        parser.add_argument(
            "--if-configured",
            action="store_true",
            help="Skip instead of failing when admin environment variables are absent.",
        )

    def handle(self, *args, **options):
        email = (
            os.environ.get("PAYLIO_ADMIN_EMAIL")
            or os.environ.get("DJANGO_SUPERUSER_EMAIL", "")
        ).strip().lower()
        password = (
            os.environ.get("PAYLIO_ADMIN_PASSWORD")
            or os.environ.get("DJANGO_SUPERUSER_PASSWORD", "")
        )
        username = (
            os.environ.get("PAYLIO_ADMIN_USERNAME")
            or os.environ.get("DJANGO_SUPERUSER_USERNAME", "")
        ).strip()

        missing = [
            name
            for name, value in (
                ("PAYLIO_ADMIN_EMAIL", email),
                ("PAYLIO_ADMIN_PASSWORD", password),
                ("PAYLIO_ADMIN_USERNAME", username),
            )
            if not value
        ]
        if missing:
            if options["if_configured"]:
                self.stdout.write("Production admin variables are not configured; skipping.")
                return
            raise CommandError("Missing required environment variables: " + ", ".join(missing))

        user, created = User.objects.get_or_create(
            email=email,
            defaults={"username": username},
        )
        user.username = username
        user.is_active = True
        user.is_staff = True
        user.is_superuser = True
        user.set_password(password)
        user.save(
            update_fields=[
                "username",
                "password",
                "is_active",
                "is_staff",
                "is_superuser",
            ]
        )

        action = "Created" if created else "Updated"
        self.stdout.write(self.style.SUCCESS(f"{action} production superuser {email}."))
