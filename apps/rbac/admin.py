from django.contrib import admin
from apps.rbac.models import Permission, Role, RolePermission


@admin.register(Permission)
class PermissionAdmin(admin.ModelAdmin):
    list_display = ["codename", "module", "description"]
    search_fields = ["codename", "module"]
    list_filter = ["module"]


class RolePermissionInline(admin.TabularInline):
    model = RolePermission
    extra = 0
    autocomplete_fields = ["permission"]


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ["name", "brand", "is_system"]
    list_filter = ["brand", "is_system"]
    search_fields = ["name", "brand__name"]
    inlines = [RolePermissionInline]
