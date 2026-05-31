class TenantContextMiddleware:
    """
    Ensures request.tenant is initialized to None for unauthenticated requests.
    Authenticated requests have request.tenant populated by FeastJWTAuthentication.authenticate().
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not hasattr(request, "tenant"):
            request.tenant = None
        return self.get_response(request)
