from rest_framework.views import exception_handler
from rest_framework import status as drf_status
from rest_framework.exceptions import (
    AuthenticationFailed,
    NotAuthenticated,
    PermissionDenied,
    NotFound,
    ValidationError,
    Throttled,
)
from django.core.exceptions import ObjectDoesNotExist


_CODE_MAP = {
    AuthenticationFailed: "AUTHENTICATION_REQUIRED",
    NotAuthenticated: "AUTHENTICATION_REQUIRED",
    PermissionDenied: "PERMISSION_DENIED",
    NotFound: "NOT_FOUND",
    ValidationError: "VALIDATION_ERROR",
    Throttled: "RATE_LIMITED",
}


def custom_exception_handler(exc, context):
    response = exception_handler(exc, context)

    if response is None:
        return None

    request = context.get("request")
    import uuid
    request_id = (
        getattr(request, "META", {}).get("HTTP_X_REQUEST_ID") or f"req_{uuid.uuid4().hex[:12]}"
        if request
        else f"req_{uuid.uuid4().hex[:12]}"
    )

    code = _CODE_MAP.get(type(exc), "ERROR")

    detail = exc.detail if hasattr(exc, "detail") else str(exc)

    if isinstance(detail, dict):
        errors = [
            {"field": field, "detail": str(msgs[0] if isinstance(msgs, list) else msgs)}
            for field, msgs in detail.items()
        ]
        message = "Validation error."
    elif isinstance(detail, list):
        errors = [{"detail": str(d)} for d in detail]
        message = str(detail[0]) if detail else "Error."
    else:
        errors = [{"detail": str(detail)}]
        message = str(detail)

    response.data = {
        "success": False,
        "code": code,
        "message": message,
        "errors": errors,
        "request_id": request_id,
    }
    return response
