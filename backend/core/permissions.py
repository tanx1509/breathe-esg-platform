"""
RBAC permission classes for the ESG platform.

Role hierarchy:
- ADMIN:   Full access including audit lock
- ANALYST: Review, approve, reject, edit records, resolve flags
- VIEWER:  Read-only access to review queue and provenance data
"""
from rest_framework.permissions import BasePermission


class IsAnalystOrAdmin(BasePermission):
    """
    Allows access only to users with ANALYST or ADMIN role.
    Used for: approve, reject, edit, resolve flag endpoints.
    """
    message = "This action requires ANALYST or ADMIN role."

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return request.user.role in ("ANALYST", "ADMIN")


class IsAdmin(BasePermission):
    """
    Allows access only to users with ADMIN role.
    Used for: audit lock, tenant management, user management.
    """
    message = "This action requires ADMIN role."

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return request.user.role == "ADMIN"
