"""
Analyst Review Layer — AnomalyFlag, ReviewEvent, AuditLock.

This layer enables human validation of suspicious operational records.
The review queue is the centerpiece of the entire product.

AnomalyFlag separates detection from resolution.
ReviewEvent makes analyst decisions append-only events.
AuditLock freezes approved records for reporting periods.
"""
import uuid
import hashlib
from django.db import models
from django.core.exceptions import PermissionDenied


class FlagType(models.TextChoices):
    MISSING_COST_CENTER = "MISSING_COST_CENTER", "Missing Cost Center"
    CROSS_DIMENSIONAL_UOM = "CROSS_DIMENSIONAL_UOM", "Cross-Dimensional UoM"
    LEADING_ZERO_TRUNCATION = "LEADING_ZERO_TRUNCATION", "Leading Zero Truncation"
    TRAILING_MINUS = "TRAILING_MINUS", "Trailing Minus"
    MULTILINGUAL_HEADER = "MULTILINGUAL_HEADER", "Multilingual Header Detected"
    DUPLICATE_TIMESTAMP = "DUPLICATE_TIMESTAMP", "Duplicate Timestamp"
    MISSING_INTERVAL = "MISSING_INTERVAL", "Missing Interval"
    UNIT_SHIFT_MWH = "UNIT_SHIFT_MWH", "Unit Shift MWh→kWh"
    ACTIVE_EXPORT_DETECTED = "ACTIVE_EXPORT_DETECTED", "Active Export Detected"
    REACTIVE_POWER_EXCLUDED = "REACTIVE_POWER_EXCLUDED", "Reactive Power Excluded"
    CANCELED_TICKET = "CANCELED_TICKET", "Canceled Ticket"
    DUPLICATE_SEGMENT = "DUPLICATE_SEGMENT", "Duplicate Segment"
    MISSING_AIRPORT_CODE = "MISSING_AIRPORT_CODE", "Missing Airport Code"
    MISSING_DISTANCE = "MISSING_DISTANCE", "Missing Distance"
    AMBIGUOUS_AIRPORT = "AMBIGUOUS_AIRPORT", "Ambiguous Airport (City Code)"
    AMBIGUOUS_TRAVEL_CATEGORY = "AMBIGUOUS_TRAVEL_CATEGORY", "Ambiguous Travel Category"
    ORPHANED_MATERIAL = "ORPHANED_MATERIAL", "Orphaned Material"
    VIRTUAL_PLANT_CODE = "VIRTUAL_PLANT_CODE", "Virtual Plant Code"
    MISSING_SUPPLIER_ON_REVERSAL = "MISSING_SUPPLIER_ON_REVERSAL", "Missing Supplier on Reversal"
    EUROPEAN_NUMBER_FORMAT = "EUROPEAN_NUMBER_FORMAT", "European Number Format"


class Severity(models.TextChoices):
    INFO = "INFO", "Info"
    WARNING = "WARNING", "Warning"
    BLOCKING = "BLOCKING", "Blocking"


class ResolutionStatus(models.TextChoices):
    OPEN = "OPEN", "Open"
    AUTO_RESOLVED = "AUTO_RESOLVED", "Auto-Resolved"
    ANALYST_RESOLVED = "ANALYST_RESOLVED", "Analyst Resolved"
    WAIVED = "WAIVED", "Waived"


class AnomalyFlag(models.Model):
    """
    Not all anomalies are equal. Some can be resolved automatically with
    high confidence. Others require mandatory human review.

    severity=BLOCKING means the record CANNOT move to APPROVED until resolved.
    severity=WARNING means the record CAN be approved but the flag must be acknowledged.
    severity=INFO is logged for traceability but does not require action.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    record = models.ForeignKey(
        "normalization.CanonicalActivityRecord",
        on_delete=models.CASCADE,
        related_name="anomaly_flag_records",
    )
    tenant = models.ForeignKey(
        "core.Tenant", on_delete=models.CASCADE, related_name="anomaly_flags"
    )
    flag_type = models.CharField(max_length=35, choices=FlagType.choices)
    severity = models.CharField(max_length=10, choices=Severity.choices)
    auto_resolvable = models.BooleanField(default=False)
    resolution_status = models.CharField(
        max_length=20,
        choices=ResolutionStatus.choices,
        default=ResolutionStatus.OPEN,
    )
    resolution_note = models.TextField(blank=True, default="")
    resolved_by = models.ForeignKey(
        "core.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="resolved_flags",
    )
    resolved_at = models.DateTimeField(null=True, blank=True)
    detected_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "anomaly_flag"
        ordering = ["-detected_at"]

    def __str__(self):
        return f"{self.flag_type} ({self.severity}) — {self.resolution_status}"


class ReviewAction(models.TextChoices):
    CLAIM = "CLAIM", "Claim"
    APPROVE = "APPROVE", "Approve"
    REJECT = "REJECT", "Reject"
    REQUEST_MORE_INFO = "REQUEST_MORE_INFO", "Request More Info"
    EDIT_AND_APPROVE = "EDIT_AND_APPROVE", "Edit and Approve"
    ESCALATE = "ESCALATE", "Escalate"
    WAIVE_FLAG = "WAIVE_FLAG", "Waive Flag"


class ReviewEvent(models.Model):
    """
    Append-only analyst review log.

    Analyst decisions are events, not status fields. When an auditor asks
    "who approved this record?", the answer includes the person, timestamp,
    review notes, and state transition. A reviewed_by column cannot provide this.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    record = models.ForeignKey(
        "normalization.CanonicalActivityRecord",
        on_delete=models.CASCADE,
        related_name="review_events",
    )
    tenant = models.ForeignKey(
        "core.Tenant", on_delete=models.CASCADE, related_name="review_events"
    )
    action = models.CharField(max_length=20, choices=ReviewAction.choices)
    previous_status = models.CharField(
        max_length=15,
        choices=[
            ("PENDING", "Pending"),
            ("UNDER_REVIEW", "Under Review"),
            ("APPROVED", "Approved"),
            ("REJECTED", "Rejected"),
        ],
    )
    new_status = models.CharField(
        max_length=15,
        choices=[
            ("PENDING", "Pending"),
            ("UNDER_REVIEW", "Under Review"),
            ("APPROVED", "Approved"),
            ("REJECTED", "Rejected"),
            ("AUDIT_LOCKED", "Audit Locked"),
        ],
    )
    performed_by = models.ForeignKey(
        "core.User",
        on_delete=models.SET_NULL,
        null=True,
        related_name="review_events",
    )
    performed_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(
        blank=True,
        default="",
        help_text="Mandatory for REJECT, EDIT_AND_APPROVE, WAIVE_FLAG",
    )
    fields_edited = models.JSONField(
        null=True,
        blank=True,
        help_text="For EDIT_AND_APPROVE: which fields were changed and why",
    )

    class Meta:
        db_table = "review_event"
        ordering = ["performed_at"]

    def save(self, *args, **kwargs):
        if self.pk and ReviewEvent.objects.filter(pk=self.pk).exists():
            raise PermissionDenied(
                "ReviewEvent records are append-only. Updates not permitted."
            )
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise PermissionDenied(
            "ReviewEvent records are append-only. Deletion not permitted."
        )

    def __str__(self):
        return f"{self.action}: {self.previous_status} → {self.new_status}"


class AuditLock(models.Model):
    """
    Reporting-period freeze event.

    APPROVED is reversible. AUDIT_LOCKED is not. Once a reporting period is
    closed and submitted to auditors, records must be frozen.

    lock_hash is a tamper-evidence mechanism: SHA-256 of all individual record
    hashes in sorted order. If any record in the locked set were modified at
    the database level, the lock hash would no longer match.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        "core.Tenant", on_delete=models.CASCADE, related_name="audit_locks"
    )
    reporting_period = models.CharField(
        max_length=20, help_text='e.g. "FY2025", "FY2025-Q1"'
    )
    locked_by = models.ForeignKey(
        "core.User",
        on_delete=models.SET_NULL,
        null=True,
        related_name="audit_locks",
    )
    locked_at = models.DateTimeField(auto_now_add=True)
    record_count = models.IntegerField(
        help_text="How many records were locked in this batch"
    )
    total_emissions = models.DecimalField(
        max_digits=20,
        decimal_places=6,
        help_text="Sum of calculated_emissions at lock time (kgCO2e)",
    )
    lock_hash = models.CharField(
        max_length=64,
        help_text="SHA-256 of all record immutable_hashes in sorted order",
    )
    notes = models.TextField(blank=True, default="")

    class Meta:
        db_table = "audit_lock"
        ordering = ["-locked_at"]

    def save(self, *args, **kwargs):
        if self.pk and AuditLock.objects.filter(pk=self.pk).exists():
            raise PermissionDenied(
                "AuditLock records are immutable after creation."
            )
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise PermissionDenied(
            "AuditLock records are immutable. Deletion not permitted."
        )

    def __str__(self):
        return f"Lock {self.reporting_period} — {self.record_count} records"
