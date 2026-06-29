from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("authentication", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="DeviceToken",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("user_id", models.IntegerField(db_index=True)),
                ("token", models.CharField(max_length=500, unique=True)),
                ("platform", models.CharField(
                    choices=[("android", "Android"), ("ios", "iOS"), ("web", "Web")],
                    default="android",
                    max_length=10,
                )),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"indexes": [models.Index(fields=["user_id"], name="auth_device_user_id_idx")]},
        ),
    ]
