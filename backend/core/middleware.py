"""
Tenant-scoping middleware.

Uses a lazy approach: since DRF's JWT authentication runs during view
dispatch (after Django middleware), we set request.tenant as a cached
property that resolves on first access.
"""
from django.utils.deprecation import MiddlewareMixin


class TenantScopingMiddleware(MiddlewareMixin):
    """
    Sets request.tenant lazily. Works with DRF's JWT auth which
    resolves request.user after middleware has already run.
    """

    def process_request(self, request):
        # Set a sentinel; actual tenant resolves lazily via _get_tenant
        request._tenant_cache = None
        request._tenant_resolved = False

    def process_view(self, request, view_func, view_args, view_kwargs):
        # By process_view, DRF may still not have authed.
        # So we attach a helper method instead.
        if not hasattr(request, "get_tenant"):
            request.get_tenant = lambda: self._resolve_tenant(request)

    @staticmethod
    def _resolve_tenant(request):
        if hasattr(request, "_tenant_resolved") and request._tenant_resolved:
            return request._tenant_cache
        if hasattr(request, "user") and request.user.is_authenticated:
            request._tenant_cache = getattr(request.user, "tenant", None)
            request._tenant_resolved = True
            return request._tenant_cache
        return None


def get_tenant(request):
    """
    Helper to get tenant from an authenticated DRF request.
    Works after DRF auth has run (i.e., inside view methods).
    """
    if hasattr(request, "user") and request.user.is_authenticated:
        return getattr(request.user, "tenant", None)
    return None
