import redis
from django.conf import settings
from django.db import connection
from drf_spectacular.utils import extend_schema
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView


class HealthCheckView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(
        tags=["Health"],
        summary="Health check",
        description="Returns the health status of DB and Redis. Returns 503 if any dependency is down.",
        responses={
            200: {"type": "object", "properties": {"status": {"type": "string"}, "checks": {"type": "object"}}},
            503: {"type": "object", "properties": {"status": {"type": "string"}, "checks": {"type": "object"}}},
        },
    )
    def get(self, request):
        checks = {}
        try:
            connection.ensure_connection()
            checks["db"] = "ok"
        except Exception:
            checks["db"] = "error"
        try:
            r = redis.from_url(settings.CACHES["default"]["LOCATION"])
            r.ping()
            checks["redis"] = "ok"
        except Exception:
            checks["redis"] = "error"

        all_ok = all(v == "ok" for v in checks.values())
        return Response(
            {"status": "ok" if all_ok else "degraded", "checks": checks},
            status=200 if all_ok else 503,
        )
