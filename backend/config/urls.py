"""
Root URL configuration for ESG platform.
"""
from django.contrib import admin
from django.urls import path, include
from django.http import JsonResponse
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView


def health_check(request):
    """Health endpoint — returns 200 for Railway/Render health checks."""
    return JsonResponse({"status": "ok"})


urlpatterns = [
    path("admin/", admin.site.urls),
    # Health
    path("api/health/", health_check, name="health-check"),
    # Auth
    path("api/auth/token/", TokenObtainPairView.as_view(), name="token-obtain"),
    path("api/auth/token/refresh/", TokenRefreshView.as_view(), name="token-refresh"),
    # App endpoints
    path("api/", include("ingestion.urls")),
    path("api/", include("review.urls")),
]
