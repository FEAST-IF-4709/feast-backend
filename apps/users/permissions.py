from rest_framework import permissions

class HasRolePermission(permissions.BasePermission):
    # Custom permission untuk mengecek apakah Role user punya codename tertentu.
    def __init__(self, required_perm):
        self.required_perm = required_perm

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        
        # Superuser kebal
        if request.user.is_superuser:
            return True

        try:
            # Ambil permissions dari Role si Employee
            user_perms = request.user.employee_profile.role.permission.all()
            return user_perms.filter(codename=self.required_perm).exists()
        except AttributeError:
            return False

def CheckPermission(codename):
    # Helper agar pemakaian di view lebih pendek
    return type(f"Has_{codename}", (HasRolePermission,), {"required_perm": codename})