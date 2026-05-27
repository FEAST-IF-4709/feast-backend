import uuid
from rest_framework.response import Response


def StandardResponse(
    data=None,
    message="",
    code="OK",
    success=True,
    status=200,
    meta=None,
    errors=None,
    request=None,
):
    request_id = (
        getattr(request, "META", {}).get("HTTP_X_REQUEST_ID") or f"req_{uuid.uuid4().hex[:12]}"
        if request
        else f"req_{uuid.uuid4().hex[:12]}"
    )
    body = {
        "success": success,
        "code": code,
        "message": message,
        "data": data,
        "request_id": request_id,
    }
    if meta is not None:
        body["meta"] = meta
    if errors is not None:
        body["errors"] = errors
    return Response(body, status=status)
