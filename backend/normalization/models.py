"""
Canonical Normalization Layer — CanonicalActivityRecord + NormalizationEvent.

Every ingested row resolves to a single CanonicalActivityRecord. This is the
record analysts review, emission calculations run against, and auditors lock.
The schema is deliberately source-agnostic.

NormalizationEvent provides the append-only transformation audit trail.
"""
import uuid
from django.db import models
from django.core.exceptions import PermissionDenied, ValidationError


class ScopeCategory(models.TextChoices):
    SCOPE_1 = "SCOPE_1", "Scope 1"
    SCOPE_2 = "SCOPE_2", "Scope 2"
    SCOPE_3 = "SCOPE_3", "Scope 3"


class ReviewStatus(models.TextChoices):
    PENDING = "PENDING", "Pending"
    UNDER_REVIEW = "UNDER_REVIEW", "Under Review"
    APPROVED = "APPROVED", "Approved"
    REJECTED = "REJECTED", "Rejected"
    AUDIT_LOCKED = "AUDIT_LOCKED", "Audit Locked"


class ReviewPriority(models.TextChoices):
    LOW = "LOW", "Low"
    MEDIUM = "MEDIUM", "Medium"
    HIGH = "HIGH", "High"
    CRITICAL = "CRITICAL", "Critical"


class CanonicalActivityRecord(models.Model):
    """
    The system's heart. Every ingested row — regardless of source — resolves
    to one canonical record. This is the single entity that analysts review,
    emission calculations run against, and that gets audit-locked.

    State machine: PENDING → UNDER_REVIEW → APPROVED → AUDIT_LOCKED
    AUDIT_LOCKED is terminal. Corrections require a new record.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        "core.Tenant", on_delete=models.CASCADE, related_name="activity_records"
    )
    raw = models.ForeignKey(
        "ingestion.RawUpload",
        on_delete=models.CASCADE,
        related_name="canonical_records",
    )
    job = models.ForeignKey(
        "ingestion.IngestionJob",
        on_delete=models.CASCADE,
        related_name="canonical_records",
    )

    # --- Source classification ---
    source_type = models.CharField(
        max_length=20, choices=[
            ("SAP_MM", "SAP MM Export"),
            ("UTILITY_INTERVAL", "Utility Interval"),
            ("TRAVEL_CONCUR", "Travel (Concur/Navan)"),
        ]
    )
    source_document_ref = models.CharField(
        max_length=255,
        blank=True,
        default="",
        help_text="SAP material doc number, booking locator, meter serial",
    )
    activity_type = models.CharField(
        max_length=100,
        blank=True,
        default="",
        help_text='e.g. "fuel_combustion", "grid_electricity", "air_travel"',
    )

    # --- Scope classification ---
    scope_category = models.CharField(
        max_length=10,
        choices=ScopeCategory.choices,
        blank=True,
        default="",
    )
    scope_subcategory = models.CharField(
        max_length=100,
        blank=True,
        default="",
        help_text='e.g. "stationary_combustion", "purchased_electricity"',
    )
    ghg_protocol_category = models.CharField(
        max_length=100,
        blank=True,
        default="",
        help_text="GHG Protocol Category 1-15 for Scope 3",
    )

    # --- Temporal ---
    activity_date = models.DateField(null=True, blank=True)
    reporting_period_year = models.IntegerField(null=True, blank=True)
    reporting_period_month = models.IntegerField(null=True, blank=True)

    # --- Physical quantity (raw, preserved verbatim) ---
    raw_quantity = models.DecimalField(
        max_digits=20, decimal_places=6, null=True, blank=True
    )
    raw_unit = models.CharField(
        max_length=20,
        blank=True,
        default="",
        help_text="Exactly as it appeared in source",
    )
    raw_quantity_string = models.CharField(
        max_length=50,
        blank=True,
        default="",
        help_text='Original string, e.g. "500.00-" or "1.500,50"',
    )

    # --- Physical quantity (normalized) ---
    normalized_quantity = models.DecimalField(
        max_digits=20, decimal_places=6, null=True, blank=True
    )
    normalized_unit = models.CharField(
        max_length=20,
        blank=True,
        default="",
        help_text='ISO standard unit, e.g. "L", "kWh", "km"',
    )
    unit_dimension = models.CharField(
        max_length=20,
        blank=True,
        default="",
        help_text='"volume", "mass", "energy", "distance"',
    )

    # --- Emission calculation ---
    emission_factor_id = models.UUIDField(null=True, blank=True)
    emission_factor_value = models.DecimalField(
        max_digits=20, decimal_places=8, null=True, blank=True
    )
    emission_factor_unit = models.CharField(
        max_length=50,
        blank=True,
        default="",
        help_text='e.g. "kgCO2e/L"',
    )
    calculated_emissions = models.DecimalField(
        max_digits=20, decimal_places=6, null=True, blank=True,
        help_text="In kgCO2e",
    )
    emissions_locked = models.BooleanField(default=False)

    # --- Organizational context ---
    facility_id = models.CharField(
        max_length=100,
        blank=True,
        default="",
        help_text="SAP plant code, meter account, entity name",
    )
    cost_center = models.CharField(max_length=50, blank=True, default="")
    supplier_id = models.CharField(
        max_length=100,
        blank=True,
        default="",
        help_text="SAP LIFNR, vendor, airline code",
    )
    material_group = models.CharField(max_length=50, blank=True, default="")

    # --- Trust and quality ---
    confidence_score = models.DecimalField(
        max_digits=4,
        decimal_places=3,
        default=1.000,
        help_text="0.000 to 1.000, computed deterministically",
    )
    review_priority = models.CharField(
        max_length=10,
        choices=ReviewPriority.choices,
        default=ReviewPriority.LOW,
    )
    anomaly_flags = models.JSONField(
        default=list,
        blank=True,
        help_text="Array of AnomalyFlag references",
    )
    normalization_rules = models.JSONField(
        default=list,
        blank=True,
        help_text="Ordered array of applied rule identifiers",
    )
    requires_human_review = models.BooleanField(default=False)
    review_status = models.CharField(
        max_length=15,
        choices=ReviewStatus.choices,
        default=ReviewStatus.PENDING,
    )

    # --- Provenance ---
    immutable_hash = models.CharField(
        max_length=64,
        blank=True,
        default="",
        help_text="SHA-256 of raw_payload at ingestion",
    )
    approved_by = models.ForeignKey(
        "core.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_records",
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    audit_locked_at = models.DateTimeField(null=True, blank=True)

    # --- Overflow ---
    source_metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Source-specific fields that don't generalize",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "canonical_activity_record"
        ordering = ["confidence_score", "-created_at"]

    def __str__(self):
        return (
            f"{self.source_type} | {self.activity_type} | "
            f"{self.normalized_quantity} {self.normalized_unit} | "
            f"{self.review_status}"
        )


class NormalizationEventType(models.TextChoices):
    LEXICAL_CAST = "LEXICAL_CAST", "Lexical Cast"
    UOM_NORMALIZATION = "UOM_NORMALIZATION", "UoM Normalization"
    LEADING_ZERO_RESTORE = "LEADING_ZERO_RESTORE", "Leading Zero Restore"
    LOCALE_PARSE = "LOCALE_PARSE", "Locale Parse"
    MOVEMENT_TYPE_CLASSIFICATION = "MOVEMENT_TYPE_CLASSIFICATION", "Movement Type Classification"
    DENSITY_CONVERSION_MANUAL = "DENSITY_CONVERSION_MANUAL", "Density Conversion (Manual)"
    SCOPE_ASSIGNMENT = "SCOPE_ASSIGNMENT", "Scope Assignment"
    EMISSION_FACTOR_APPLIED = "EMISSION_FACTOR_APPLIED", "Emission Factor Applied"
    MANUAL_CORRECTION = "MANUAL_CORRECTION", "Manual Correction"
    DUPLICATE_REMOVAL = "DUPLICATE_REMOVAL", "Duplicate Removal"
    INTERVAL_GAP_DETECTION = "INTERVAL_GAP_DETECTION", "Interval Gap Detection"
    AIRPORT_ENRICHMENT = "AIRPORT_ENRICHMENT", "Airport Enrichment"
    DISTANCE_CALCULATION = "DISTANCE_CALCULATION", "Distance Calculation"
    CABIN_CLASS_MULTIPLIER = "CABIN_CLASS_MULTIPLIER", "Cabin Class Multiplier"
    STATUS_FILTER = "STATUS_FILTER", "Status Filter"
    REACTIVE_POWER_EXCLUSION = "REACTIVE_POWER_EXCLUSION", "Reactive Power Exclusion"
    ACTIVE_EXPORT_EXCLUSION = "ACTIVE_EXPORT_EXCLUSION", "Active Export Exclusion"


class AppliedBy(models.TextChoices):
    SYSTEM = "SYSTEM", "System"
    ANALYST = "ANALYST", "Analyst"


class NormalizationEvent(models.Model):
    """
    Append-only transformation audit trail.

    normalization_rules on the canonical record tells you WHAT happened.
    NormalizationEvent tells you WHEN, BY WHAT SYSTEM, and EXACTLY WHAT
    the before/after values were.

    No updates. No deletes.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    record = models.ForeignKey(
        CanonicalActivityRecord,
        on_delete=models.CASCADE,
        related_name="normalization_events",
    )
    tenant = models.ForeignKey(
        "core.Tenant", on_delete=models.CASCADE, related_name="normalization_events"
    )
    event_type = models.CharField(
        max_length=30, choices=NormalizationEventType.choices
    )
    field_name = models.CharField(
        max_length=100, help_text="Which field was transformed"
    )
    before_value = models.TextField(
        blank=True, default="", help_text="Original value as string"
    )
    after_value = models.TextField(
        blank=True, default="", help_text="Transformed value as string"
    )
    rule_applied = models.CharField(
        max_length=255,
        blank=True,
        default="",
        help_text='e.g. "trailing_minus_regex", "T006A_ST_to_EA"',
    )
    applied_by = models.CharField(
        max_length=10, choices=AppliedBy.choices, default=AppliedBy.SYSTEM
    )
    applied_by_user = models.ForeignKey(
        "core.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="normalization_events",
    )
    applied_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(
        blank=True,
        default="",
        help_text="Required when applied_by = ANALYST",
    )

    class Meta:
        db_table = "normalization_event"
        ordering = ["applied_at"]

    def save(self, *args, **kwargs):
        if self.pk and NormalizationEvent.objects.filter(pk=self.pk).exists():
            raise PermissionDenied(
                "NormalizationEvent records are append-only. Updates not permitted."
            )
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise PermissionDenied(
            "NormalizationEvent records are append-only. Deletion not permitted."
        )

    def __str__(self):
        return f"{self.event_type} on {self.field_name}: {self.before_value} → {self.after_value}"
