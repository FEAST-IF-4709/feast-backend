import uuid
import secrets
from django.db import models


class Table(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    outlet = models.ForeignKey("tenants.Outlet", on_delete=models.PROTECT, related_name="tables")
    label = models.CharField(max_length=20)
    capacity = models.PositiveSmallIntegerField()
    qr_token = models.CharField(max_length=43, unique=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["outlet", "label"], name="unique_table_label_per_outlet"),
        ]
        indexes = [
            models.Index(fields=["qr_token"]),
            models.Index(fields=["outlet", "is_active"]),
        ]

    def save(self, *args, **kwargs):
        if not self.qr_token:
            self.qr_token = secrets.token_urlsafe(32)
        super().save(*args, **kwargs)

    def rotate_qr(self):
        self.qr_token = secrets.token_urlsafe(32)
        self.save(update_fields=["qr_token"])

    def __str__(self):
        return f"Meja {self.label} — {self.outlet.name}"
