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


class PublicBrandSerializer(serializers.ModelSerializer):
    """Read-only public brand info — no sensitive fields (owner_email, subscription_status)."""

    class Meta:
        model = Brand
        fields = [
            "id", "name", "slug", "description", "cuisine_type",
            "logo_url", "banner_url", "phone", "location_address",
            "operating_hours", "is_accepting_orders", "is_busy_mode",
            "latitude", "longitude",
        ]


class BrandSerializer(serializers.ModelSerializer):
    logo = serializers.ImageField(write_only=True, required=False, allow_null=True)
    banner = serializers.ImageField(write_only=True, required=False, allow_null=True)

    class Meta:
        model = Brand
        fields = [
            "id", "name", "slug", "owner_email",
            "subscription_status", "is_active",
            "description", "phone", "cuisine_type",
            "logo_url", "logo", "banner_url", "banner",
            "location_address", "operating_hours",
            "is_accepting_orders", "is_auto_accept", "is_busy_mode",
            "tax_rate",
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

    def _save_image(self, image_file, folder):
        ext = os.path.splitext(image_file.name)[1].lower() or ".jpg"
        filename = f"{folder}/{uuid_module.uuid4()}{ext}"
        saved_path = default_storage.save(filename, image_file)
        request = self.context.get("request")
        if request:
            return request.build_absolute_uri(
                "/" + django_settings.MEDIA_URL.lstrip("/") + saved_path
            )
        return "/" + django_settings.MEDIA_URL.lstrip("/") + saved_path

    def update(self, instance, validated_data):
        logo_file = validated_data.pop("logo", None)
        banner_file = validated_data.pop("banner", None)
        if logo_file:
            validated_data["logo_url"] = self._save_image(logo_file, "brand_logos")
        if banner_file:
            validated_data["banner_url"] = self._save_image(banner_file, "brand_banners")
        return super().update(instance, validated_data)

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        request = self.context.get("request")
        for field in ("logo_url", "banner_url"):
            url = ret.get(field)
            if url and not url.startswith("http") and request:
                ret[field] = request.build_absolute_uri("/" + url.lstrip("/"))
        return ret


class BrandAdminSerializer(serializers.ModelSerializer):
    """Full read-write serializer for SuperAdmin brand management."""

    class Meta:
        model = Brand
        fields = [
            "id", "name", "slug", "owner_email",
            "subscription_status", "is_active",
            "description", "phone", "cuisine_type",
            "logo_url", "banner_url", "location_address", "operating_hours",
            "is_accepting_orders", "is_auto_accept", "is_busy_mode",
            "tax_rate",
            "latitude", "longitude",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate_name(self, value):
        qs = Brand.objects.filter(name=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("Brand name already exists.")
        return value

    def validate_slug(self, value):
        qs = Brand.objects.filter(slug=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("Brand slug already exists.")
        return value

    def validate_owner_email(self, value):
        qs = Brand.objects.filter(owner_email=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("Owner email already registered to another brand.")
        return value

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


class PublicOutletSerializer(serializers.ModelSerializer):
    """Read-only public outlet info for customer-facing views."""

    class Meta:
        model = Outlet
        fields = [
            "id", "brand_id", "name", "address",
            "latitude", "longitude", "phone", "opening_hours",
        ]


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
