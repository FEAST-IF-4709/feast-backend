import uuid
from django.db import models
from django.contrib.auth.hashers import make_password, check_password as django_check_password
from django.core.exceptions import ValidationError


class Employee(models.Model):
    """
    Standalone employee model. Authenticates independently of Django's BaseUser.
    Implements the duck-type interface required by DRF (is_authenticated, is_anonymous).
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    brand = models.ForeignKey("tenants.Brand", on_delete=models.PROTECT, related_name="employees")
    outlet = models.ForeignKey(
        "tenants.Outlet",
        on_delete=models.PROTECT,
        related_name="employees",
        null=True,
        blank=True,
    )
    role = models.ForeignKey("rbac.Role", on_delete=models.PROTECT, related_name="employees")
    email = models.EmailField()
    password = models.CharField(max_length=128)
    full_name = models.CharField(max_length=150)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # DRF duck-type interface
    is_authenticated = True
    is_anonymous = False

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["brand", "email"], name="unique_employee_email_per_brand"),
        ]
        indexes = [
            models.Index(fields=["brand", "email"]),
        ]

    def clean(self):
        if self.role_id and self.brand_id and self.role.brand_id != self.brand_id:
            raise ValidationError("Role must belong to the same brand as the employee.")

    def set_password(self, raw_password):
        self.password = make_password(raw_password)

    def check_password(self, raw_password):
        return django_check_password(raw_password, self.password)

    def __str__(self):
        return f"{self.full_name} <{self.email}> — {self.brand.name}"
