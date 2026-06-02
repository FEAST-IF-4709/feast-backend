from django.db import migrations

SYSTEM_ROLE_RANKS = {
    "BRAND_OWNER": 1,
    "MANAGER": 2,
    "CASHIER": 3,
    "KITCHEN": 3,
}


def backfill_ranks(apps, schema_editor):
    Role = apps.get_model("rbac", "Role")
    for role_name, rank in SYSTEM_ROLE_RANKS.items():
        Role.objects.filter(name=role_name, is_system=True).update(rank=rank)


class Migration(migrations.Migration):

    dependencies = [
        ("rbac", "0002_role_rank"),
    ]

    operations = [
        migrations.RunPython(backfill_ranks, migrations.RunPython.noop),
    ]
