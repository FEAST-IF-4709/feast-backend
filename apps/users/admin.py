from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from apps.users.models import BaseUser


@admin.register(BaseUser)
class BaseUserAdmin(UserAdmin):
    list_display = ["email", "is_active", "is_staff", "created_at"]
    search_fields = ["email"]
    ordering = ["email"]
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Permissions", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
    )
    add_fieldsets = (
        (None, {"classes": ("wide",), "fields": ("email", "password1", "password2")}),
    )
