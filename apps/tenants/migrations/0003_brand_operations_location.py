from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tenants', '0002_extend_brand_fields'),
    ]

    operations = [
        migrations.RunSQL("SET lock_timeout = '3s'", migrations.RunSQL.noop),
        migrations.AddField(
            model_name='brand',
            name='is_accepting_orders',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='brand',
            name='is_auto_accept',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='brand',
            name='is_busy_mode',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='brand',
            name='latitude',
            field=models.DecimalField(blank=True, decimal_places=6, max_digits=9, null=True),
        ),
        migrations.AddField(
            model_name='brand',
            name='longitude',
            field=models.DecimalField(blank=True, decimal_places=6, max_digits=9, null=True),
        ),
    ]
