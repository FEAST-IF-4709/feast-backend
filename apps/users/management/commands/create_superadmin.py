from django.core.management.base import BaseCommand, CommandError
from apps.users.models import SuperAdmin


class Command(BaseCommand):
    help = "Create a SuperAdmin account (system-level, not tied to any brand)."

    def add_arguments(self, parser):
        parser.add_argument("--email", required=True)
        parser.add_argument("--password", required=True)
        parser.add_argument("--name", default="Super Administrator")

    def handle(self, *args, **options):
        email = options["email"]
        password = options["password"]
        full_name = options["name"]

        if SuperAdmin.objects.filter(email=email).exists():
            raise CommandError(f"SuperAdmin with email '{email}' already exists.")

        sa = SuperAdmin(email=email, full_name=full_name)
        sa.set_password(password)
        sa.save()

        self.stdout.write(self.style.SUCCESS(
            f"SuperAdmin created: {full_name} <{email}>"
        ))
