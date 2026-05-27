import uuid
from django.db import models
from django.contrib.auth.hashers import make_password, check_password as django_check_password


class Customer(models.Model):
    """
    Global customer model. Standalone auth — not linked to Django BaseUser.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    phone = models.CharField(max_length=20, unique=True)
    email = models.EmailField(null=True, blank=True)
    password = models.CharField(max_length=128)
    full_name = models.CharField(max_length=150)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # DRF duck-type interface
    is_authenticated = True
    is_anonymous = False

    class Meta:
        indexes = [
            models.Index(fields=["phone"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["email"],
                condition=models.Q(email__isnull=False),
                name="unique_customer_email_when_set",
            ),
        ]

    def set_password(self, raw_password):
        self.password = make_password(raw_password)

    def check_password(self, raw_password):
        return django_check_password(raw_password, self.password)

    def __str__(self):
        return f"{self.full_name} ({self.phone})"
