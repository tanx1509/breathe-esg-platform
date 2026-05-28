"""
Ingestion layer models — IngestionJob, RawUpload, ParsedRow.

This layer preserves source-of-truth operational data exactly as received.
Raw payloads are immutable. Parsing is separated from normalization because
they fail for different reasons and require separate error handling.
"""
import uuid
import hashlib
import json
from django.db import models
from django.core.exceptions import PermissionDenied


class SourceType(models.TextChoices):
    SAP_MM = "SAP_MM", "SAP MM Export"
    UTILITY_INTERVAL = "UTILITY_INTERVAL", "Utility Interval"
    TRAVEL_CONCUR = "TRAVEL_CONCUR", "Travel (Concur/Navan)"


class JobStatus(models.TextChoices):
    QUEUED = "QUEUED", "Queued"
    PARSING = "PARSING", "Parsing"
    NORMALIZING = "NORMALIZING", "Normalizing"
    FAILED = "FAILED", "Failed"
    COMPLETE = "COMPLETE", "Complete"


class ParseStatus(models.TextChoices):
    SUCCESS = "SUCCESS", "Success"
    PARTIAL = "PARTIAL", "Partial"
    FAILED = "FAILED", "Failed"


class IngestionJob(models.Model):
    """
    A single CSV upload is not a row-level event. It is a job with a lifecycle.
    Jobs can partially succeed. Analysts need to know: what batch did this row
    arrive in, who triggered it, and did the parser encounter errors.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        "core.Tenant", on_delete=models.CASCADE, related_name="ingestion_jobs"
    )
    source_type = models.CharField(max_length=20, choices=SourceType.choices)
    triggered_by = models.ForeignKey(
        "core.User", on_delete=models.SET_NULL, null=True, related_name="triggered_jobs"
    )
    triggered_at = models.DateTimeField(auto_now_add=True)
    file_name = models.CharField(max_length=512)
    file_hash = models.CharField(
        max_length=64,
        help_text="SHA-256 of raw uploaded bytes. Prevents duplicate uploads.",
    )
    status = models.CharField(
        max_length=15, choices=JobStatus.choices, default=JobStatus.QUEUED
    )
    total_rows = models.IntegerField(default=0)
    parsed_rows = models.IntegerField(default=0)
    failed_rows = models.IntegerField(default=0)
    suspicious_rows = models.IntegerField(default=0)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "ingestion_job"
        ordering = ["-triggered_at"]

    def __str__(self):
        return f"{self.source_type} — {self.file_name} ({self.status})"


class RawUpload(models.Model):
    """
    Immutable source payload storage.

    The single most important architectural decision: raw source payloads are
    stored verbatim and never modified. When an auditor asks "what did the SAP
    system actually send you?", the answer must be retrievable without
    reconstruction.

    This model enforces immutability at the application layer:
    - save() raises PermissionDenied on updates
    - delete() raises PermissionDenied always
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    job = models.ForeignKey(
        IngestionJob, on_delete=models.CASCADE, related_name="raw_uploads"
    )
    tenant = models.ForeignKey(
        "core.Tenant", on_delete=models.CASCADE, related_name="raw_uploads"
    )
    row_number = models.IntegerField(help_text="Original line number in source file")
    raw_payload = models.JSONField(
        help_text="Verbatim key-value pairs as extracted from source row"
    )
    received_at = models.DateTimeField(auto_now_add=True)
    immutable_hash = models.CharField(
        max_length=64,
        help_text="SHA-256 of raw_payload JSON string. Cryptographic fingerprint "
        "for tamper detection.",
    )

    class Meta:
        db_table = "raw_upload"
        ordering = ["row_number"]

    def save(self, *args, **kwargs):
        if self.pk and RawUpload.objects.filter(pk=self.pk).exists():
            raise PermissionDenied(
                "RawUpload records are immutable. Updates are not permitted."
            )
        # Compute immutable hash on first save
        if not self.immutable_hash:
            payload_str = json.dumps(self.raw_payload, sort_keys=True)
            self.immutable_hash = hashlib.sha256(payload_str.encode()).hexdigest()
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise PermissionDenied(
            "RawUpload records are immutable. Deletion is not permitted."
        )

    def __str__(self):
        return f"Row {self.row_number} — Job {self.job_id}"


class ParsedRow(models.Model):
    """
    Structural parsing result — separate from normalization.

    Parsing detects headers, splits delimiters, casts types.
    Normalization converts units, restores leading zeros, maps scopes.
    These fail for different reasons. A ParsedRow can exist even when
    parsing partially fails (e.g., date parsing succeeded but quantity
    casting failed).
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    raw = models.OneToOneField(
        RawUpload, on_delete=models.CASCADE, related_name="parsed_row"
    )
    job = models.ForeignKey(
        IngestionJob, on_delete=models.CASCADE, related_name="parsed_row_set"
    )
    parse_status = models.CharField(max_length=10, choices=ParseStatus.choices)
    parse_errors = models.JSONField(
        default=list,
        blank=True,
        help_text="Array of {field, raw_value, error_type} objects",
    )
    detected_schema = models.CharField(
        max_length=100,
        blank=True,
        default="",
        help_text='e.g. "SAP_MB51_DE_LOCALE", "UTILITY_15MIN_KWH"',
    )
    locale_detected = models.CharField(
        max_length=10,
        blank=True,
        default="",
        help_text='e.g. "de-DE", "en-US"',
    )
    date_format_inferred = models.CharField(
        max_length=30,
        blank=True,
        default="",
        help_text='e.g. "DD.MM.YYYY", "MM/DD/YYYY"',
    )
    parsed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "parsed_row"

    def __str__(self):
        return f"Parsed {self.raw_id} — {self.parse_status}"
