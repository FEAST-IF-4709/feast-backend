from django.contrib import admin
from apps.staff.models import Employee


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ["full_name", "email", "brand", "outlet", "role", "is_active"]
    list_filter = ["brand", "outlet", "role", "is_active"]
    search_fields = ["full_name", "email", "brand__name"]
    readonly_fields = ["created_at", "updated_at"]
