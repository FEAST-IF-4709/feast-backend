from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0002_order_grandtotal_check"),
    ]

    operations = [
        migrations.CreateModel(
            name="DailyOrderCounter",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False)),
                ("date", models.DateField(unique=True)),
                ("last_sequence", models.PositiveIntegerField(default=0)),
            ],
            options={
                "db_table": "orders_dailyordercounter",
            },
        ),
    ]
