from rest_framework import serializers
from .models import Role, Permission

class PermissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Permission
        fields = ['id', 'name', 'codename', 'module']

class RoleSerializer(serializers.ModelSerializer):
    # Saat GET, kita kasih info lengkap permission-nya
    # Saat POST/PATCH, kita cukup kirim list ID-nya saja
    permissions_detail = PermissionSerializer(source='permissions', many=True, read_only=True)

    class Meta:
        model = Role
        fields = ['id', 'brand', 'name', 'permissions', 'permissions_detail']