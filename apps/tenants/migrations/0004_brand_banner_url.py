from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tenants", "0003_brand_operations_location"),
    ]

    operations = [
        migrations.AddField(
            model_name="brand",
            name="banner_url",
            field=models.URLField(blank=True, default="", max_length=500),
        ),
    ]
