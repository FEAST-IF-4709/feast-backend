import os
import re
import uuid as uuid_module

from django.conf import settings as django_settings
from django.core.files.storage import default_storage
from rest_framework import serializers

from .models import Brand, Outlet

_VALID_DAYS = {"mon", "tue", "wed", "thu", "fri", "sat", "sun"}
_TIME_RE = re.compile(r"^\d{2}:\d{2}$")
_PHONE_RE = re.compile(r"^(\+62|08)\d{7,13}$")


class BrandSerializer(serializers.ModelSerializer):
    # Write-only: accepts an uploaded image file; result is stored in logo_url.
    logo = serializers.ImageField(write_only=True, required=False, allow_null=True)

    class Meta:
        model = Brand
        fields = [
            "id", "name", "slug", "owner_email",
            "subscription_status", "is_active",
            "description", "phone", "cuisine_type",
            "logo_url", "logo", "location_address", "operating_hours",
            "is_accepting_orders", "is_auto_accept", "is_busy_mode",
            "latitude", "longitude",
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

    def update(self, instance, validated_data):
        logo_file = validated_data.pop("logo", None)
        if logo_file:
            ext = os.path.splitext(logo_file.name)[1].lower() or ".jpg"
            filename = f"brand_logos/{uuid_module.uuid4()}{ext}"
            saved_path = default_storage.save(filename, logo_file)
            request = self.context.get("request")
            if request:
                validated_data["logo_url"] = request.build_absolute_uri(
                    "/" + django_settings.MEDIA_URL.lstrip("/") + saved_path
                )
            else:
                validated_data["logo_url"] = "/" + django_settings.MEDIA_URL.lstrip("/") + saved_path
        return super().update(instance, validated_data)

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        logo_url = ret.get("logo_url")
        if logo_url and not logo_url.startswith("http"):
            request = self.context.get("request")
            if request:
                ret["logo_url"] = request.build_absolute_uri(
                    "/" + logo_url.lstrip("/")
                )
        return ret


class OutletSerializer(serializers.ModelSerializer):
    class Meta:
        model = Outlet
        fields = [
            "id", "brand_id", "name", "address",
            "latitude", "longitude", "phone", "opening_hours",
            "is_active", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "brand_id", "created_at", "updated_at"]


class OutletCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Outlet
        fields = ["name", "address", "latitude", "longitude", "phone", "opening_hours", "is_active"]
