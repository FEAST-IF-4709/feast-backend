import re
from rest_framework import serializers
from .models import Brand

_VALID_DAYS = {"mon", "tue", "wed", "thu", "fri", "sat", "sun"}
_TIME_RE = re.compile(r"^\d{2}:\d{2}$")
_PHONE_RE = re.compile(r"^(\+62|08)\d{7,13}$")


class BrandSerializer(serializers.ModelSerializer):
    class Meta:
        model = Brand
        fields = [
            "id", "name", "slug", "owner_email",
            "subscription_status", "is_active",
            "description", "phone", "cuisine_type",
            "logo_url", "location_address", "operating_hours",
            "created_at", "updated_at",
        ]
        read_only_fields = [
            "id", "name", "slug", "owner_email",
            "subscription_status", "is_active",
            "created_at", "updated_at",
        ]

    def validate_phone(self, value):
        if value and not _PHONE_RE.match(value):
            raise serializers.ValidationError(
                "Phone must be Indonesian format (+62xxx or 08xxx), 9-15 digits."
            )
        return value

    def validate_operating_hours(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError("Must be an object.")
        for day, hours in value.items():
            if day not in _VALID_DAYS:
                raise serializers.ValidationError(
                    f"Invalid day key: '{day}'. Use mon/tue/wed/thu/fri/sat/sun."
                )
            if not isinstance(hours, dict) or "open" not in hours or "close" not in hours:
                raise serializers.ValidationError(
                    f"'{day}' must have 'open' and 'close' keys."
                )
            if not _TIME_RE.match(hours["open"]) or not _TIME_RE.match(hours["close"]):
                raise serializers.ValidationError(
                    f"'{day}' times must be HH:MM format."
                )
        return value
