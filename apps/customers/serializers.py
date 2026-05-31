from rest_framework import serializers

from apps.customers.models import Customer


class CustomerPublicSerializer(serializers.ModelSerializer):
    """Read-only serializer for staff-side customer lookup (cashier link flow)."""

    class Meta:
        model = Customer
        fields = ["id", "phone", "full_name"]
