from django.contrib import admin
from apps.authentication.models import BlacklistedJTI


@admin.register(BlacklistedJTI)
class BlacklistedJTIAdmin(admin.ModelAdmin):
    list_display = ["jti", "blacklisted_at"]
    search_fields = ["jti"]
    readonly_fields = ["blacklisted_at"]
