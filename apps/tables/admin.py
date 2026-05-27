from django.contrib import admin
from apps.tables.models import Table


@admin.register(Table)
class TableAdmin(admin.ModelAdmin):
    list_display = ["label", "outlet", "capacity", "is_active", "qr_token"]
    list_filter = ["outlet", "is_active"]
    search_fields = ["label", "outlet__name"]
    readonly_fields = ["qr_token", "created_at", "updated_at"]
