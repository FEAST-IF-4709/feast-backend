import logging
import threading
import uuid

_local = threading.local()


class RequestIdMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request_id = request.META.get("HTTP_X_REQUEST_ID") or f"req_{uuid.uuid4().hex[:12]}"
        request.request_id = request_id
        _local.request_id = request_id
        response = self.get_response(request)
        response["X-Request-Id"] = request_id
        _local.request_id = None
        return response


class RequestIdFilter(logging.Filter):
    def filter(self, record):
        record.request_id = getattr(_local, "request_id", "-")
        return True
