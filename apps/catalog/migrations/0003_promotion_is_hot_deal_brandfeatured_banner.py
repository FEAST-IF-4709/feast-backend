from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0002_add_category_sequence"),
        ("tenants", "0005_brand_tax_rate"),
    ]

    operations = [
        migrations.AddField(
            model_name="promotion",
            name="is_hot_deal",
            field=models.BooleanField(default=False, db_index=True),
        ),
        migrations.CreateModel(
            name="BrandFeaturedBanner",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=120)),
                ("subtitle", models.CharField(blank=True, default="", max_length=200)),
                ("image_url", models.URLField(max_length=500)),
                ("is_active", models.BooleanField(default=False)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "brand",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="featured_banner",
                        to="tenants.brand",
                    ),
                ),
                (
                    "target_outlet",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="featured_banners",
                        to="tenants.outlet",
                    ),
                ),
            ],
        ),
    ]
