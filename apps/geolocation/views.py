import math

from django.db.models.expressions import RawSQL
from drf_spectacular.utils import extend_schema, inline_serializer, OpenApiParameter
from rest_framework import serializers as drf_serializers
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView

from apps.tenants.models import Outlet
from core.responses.standard import StandardResponse
from core.schema import COMMON_ERROR_RESPONSES

_EARTH_RADIUS_KM = 6371.0088

_HAVERSINE_SQL = """
    6371.0088 * acos(LEAST(1.0,
        cos(radians(%s)) * cos(radians("tenants_outlet"."latitude")) *
        cos(radians("tenants_outlet"."longitude") - radians(%s)) +
        sin(radians(%s)) * sin(radians("tenants_outlet"."latitude"))
    ))
"""


def _parse_float(value, name):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None, f"'{name}' must be a valid number."


class NearbyOutletsView(APIView):
    """GET /api/v1/outlets/nearby/"""

    permission_classes = [AllowAny]

    @extend_schema(
        tags=["Geolocation"],
        summary="Find nearby outlets",
        description="Returns active outlets within a given radius using Haversine distance. A bounding-box pre-filter is applied before the full distance calculation.",
        parameters=[
            OpenApiParameter("lat", float, required=True, description="Latitude of the search origin"),
            OpenApiParameter("lng", float, required=True, description="Longitude of the search origin"),
            OpenApiParameter("radius_km", float, description="Search radius in kilometres. Default: 10, max: 100"),
            OpenApiParameter("limit", int, description="Max results. Default: 20, max: 50"),
            OpenApiParameter("brand_id", str, description="Optional brand UUID to filter outlets"),
        ],
        responses={
            200: inline_serializer("NearbyOutlet", fields={
                "id": drf_serializers.UUIDField(),
                "name": drf_serializers.CharField(),
                "brand_name": drf_serializers.CharField(),
                "address": drf_serializers.CharField(),
                "latitude": drf_serializers.CharField(),
                "longitude": drf_serializers.CharField(),
                "distance_km": drf_serializers.FloatField(),
            }, many=True),
            **COMMON_ERROR_RESPONSES,
        },
    )
    def get(self, request):
        errors = {}

        raw_lat = request.query_params.get("lat")
        raw_lng = request.query_params.get("lng")

        if raw_lat is None:
            errors["lat"] = "Required."
        if raw_lng is None:
            errors["lng"] = "Required."

        if errors:
            return StandardResponse(
                success=False, code="VALIDATION_ERROR",
                message="Missing required parameters.", errors=errors,
                status=400, request=request,
            )

        try:
            lat = float(raw_lat)
        except (TypeError, ValueError):
            errors["lat"] = "'lat' must be a valid number."

        try:
            lng = float(raw_lng)
        except (TypeError, ValueError):
            errors["lng"] = "'lng' must be a valid number."

        if errors:
            return StandardResponse(
                success=False, code="VALIDATION_ERROR",
                message="Invalid parameters.", errors=errors,
                status=400, request=request,
            )

        if not (-90 <= lat <= 90):
            errors["lat"] = "Must be between -90 and 90."
        if not (-180 <= lng <= 180):
            errors["lng"] = "Must be between -180 and 180."

        try:
            radius_km = float(request.query_params.get("radius_km", 10))
        except (TypeError, ValueError):
            errors["radius_km"] = "Must be a valid number."
            radius_km = 10

        if not (0 < radius_km <= 100):
            errors["radius_km"] = "Must be between 0 (exclusive) and 100."

        if errors:
            return StandardResponse(
                success=False, code="VALIDATION_ERROR",
                message="Invalid parameters.", errors=errors,
                status=400, request=request,
            )

        try:
            limit = min(int(request.query_params.get("limit", 20)), 50)
        except (TypeError, ValueError):
            limit = 20

        # Bounding-box pre-filter to reduce rows before Haversine evaluation
        delta_lat = radius_km / 111.0
        cos_lat = math.cos(math.radians(lat))
        delta_lng = radius_km / (111.0 * cos_lat) if cos_lat != 0 else 180.0

        qs = Outlet.objects.filter(
            is_active=True,
            latitude__range=(lat - delta_lat, lat + delta_lat),
            longitude__range=(lng - delta_lng, lng + delta_lng),
        )

        brand_id = request.query_params.get("brand_id")
        if brand_id:
            qs = qs.filter(brand_id=brand_id)

        qs = (
            qs.annotate(distance=RawSQL(_HAVERSINE_SQL, (lat, lng, lat)))
            .filter(distance__lte=radius_km)
            .select_related("brand")
            .order_by("distance")[:limit]
        )

        data = [
            {
                "id": str(outlet.id),
                "name": outlet.name,
                "brand_name": outlet.brand.name,
                "address": outlet.address,
                "latitude": str(outlet.latitude),
                "longitude": str(outlet.longitude),
                "distance_km": round(float(outlet.distance), 2),
            }
            for outlet in qs
        ]

        return StandardResponse(data=data, request=request)
