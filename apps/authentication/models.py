from django.db import models


class BlacklistedJTI(models.Model):
    """Stores blacklisted JWT JTI values for logout/invalidation."""

    jti = models.CharField(max_length=255, unique=True)
    blacklisted_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Blacklisted JTI {self.jti}"


class DeviceToken(models.Model):
    """FCM push notification tokens per user device."""

    class Platform(models.TextChoices):
        ANDROID = "android", "Android"
        IOS = "ios", "iOS"
        WEB = "web", "Web"

    user_id = models.CharField(max_length=64, db_index=True)
    token = models.CharField(max_length=500, unique=True)
    platform = models.CharField(max_length=10, choices=Platform.choices, default=Platform.ANDROID)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [models.Index(fields=["user_id"])]

    def __str__(self):
        return f"DeviceToken({self.platform}) user={self.user_id}"
