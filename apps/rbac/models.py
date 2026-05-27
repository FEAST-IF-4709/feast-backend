import uuid
from django.db import models


class Permission(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    codename = models.CharField(max_length=100, unique=True)
    module = models.CharField(max_length=50)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.codename


class Role(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    brand = models.ForeignKey("tenants.Brand", on_delete=models.CASCADE, related_name="roles")
    name = models.CharField(max_length=80)
    is_system = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["brand", "name"], name="unique_role_name_per_brand"),
        ]

    def __str__(self):
        return f"{self.name} ({self.brand.name})"


class RolePermission(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    role = models.ForeignKey(Role, on_delete=models.CASCADE, related_name="rolepermissions")
    permission = models.ForeignKey(Permission, on_delete=models.PROTECT, related_name="rolepermissions")

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["role", "permission"], name="unique_role_permission"),
        ]

    def __str__(self):
        return f"{self.role.name} → {self.permission.codename}"
