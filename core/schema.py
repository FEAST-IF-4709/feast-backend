from drf_spectacular.utils import OpenApiResponse

COMMON_ERROR_RESPONSES = {
    400: OpenApiResponse(description="Validation error"),
    401: OpenApiResponse(description="Authentication required"),
    403: OpenApiResponse(description="Permission denied"),
    404: OpenApiResponse(description="Not found"),
}

AUTH_ERROR_RESPONSES = {
    400: OpenApiResponse(description="Invalid credentials or validation error"),
    401: OpenApiResponse(description="Authentication required"),
    429: OpenApiResponse(description="Too many requests"),
}
