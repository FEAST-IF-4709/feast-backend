from django.contrib import admin
from apps.customers.models import Customer


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ["full_name", "phone", "email", "is_active", "created_at"]
    list_filter = ["is_active"]
    search_fields = ["full_name", "phone", "email"]
    readonly_fields = ["password", "created_at", "updated_at"]
