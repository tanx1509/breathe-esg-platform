"""
Core models — Tenant and User.

Tenant scopes all operational data. User extends AbstractUser with tenant
membership and role assignment. These are the two entities that every other
model in the system references.
"""
import uuid
from django.contrib.auth.models import AbstractUser
from django.db import models


class Tenant(models.Model):
    """
    Multi-tenant isolation boundary.

    Every query in the system is scoped to a tenant. A consulting firm
    onboarding multiple clients, or a parent company managing subsidiaries
    with separate reporting boundaries, cannot share canonical records.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    reporting_currency = models.CharField(
        max_length=3,
        default="INR",
        help_text="ISO 4217 currency code, e.g. INR, USD",
    )
    fiscal_year_start = models.DateField(
        help_text="Carbon reporting year boundary. A company with March 31 "
        "fiscal year end needs interval records sliced at that boundary.",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "tenant"

    def __str__(self):
        return self.name


class UserRole(models.TextChoices):
    ADMIN = "ADMIN", "Admin"
    ANALYST = "ANALYST", "Analyst"
    VIEWER = "VIEWER", "Viewer"


class User(AbstractUser):
    """
    Custom user with tenant membership and role.

    All API access is scoped to the user's tenant via middleware.
    Role determines permissions:
    - ADMIN: full access including audit lock
    - ANALYST: review, approve, reject, edit records
    - VIEWER: read-only access to review queue and provenance
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name="users",
        null=True,
        blank=True,
    )
    role = models.CharField(
        max_length=10,
        choices=UserRole.choices,
        default=UserRole.VIEWER,
    )

    class Meta:
        db_table = "user"

    def __str__(self):
        return f"{self.email} ({self.role})"
