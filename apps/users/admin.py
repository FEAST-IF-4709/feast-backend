from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import BaseUser, Employee, Role, Customer
# Register your models here.


@admin.register(BaseUser)
class BaseUserAdmin(UserAdmin):
    # Mengatur tampilan kolom di dashboard
    list_display = ('email', 'user_type', 'is_staff', 'is_active')
    ordering = ('email',)
    
    # Supaya tidak error saat edit user, kita sesuaikan fieldset-nya
    fieldsets = UserAdmin.fieldsets + (
        ('Extra Info', {'fields': ('user_type', 'auth_provider')}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Extra Info', {'fields': ('user_type', 'auth_provider')}),
    )

admin.site.register(Role)
admin.site.register(Employee)
admin.site.register(Customer)