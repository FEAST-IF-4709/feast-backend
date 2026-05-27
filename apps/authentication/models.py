from django.db import models


class BlacklistedJTI(models.Model):
    """Stores blacklisted JWT JTI values for logout/invalidation."""

    jti = models.CharField(max_length=255, unique=True)
    blacklisted_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Blacklisted JTI {self.jti}"
