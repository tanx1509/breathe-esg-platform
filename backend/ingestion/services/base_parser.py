"""
Base parser class — provides common infrastructure for all source parsers.

Handles:
- IngestionJob lifecycle management
- RawUpload creation (immutable)
- ParsedRow creation
- NormalizationEvent logging
- AnomalyFlag creation
- Confidence score computation
- Error aggregation
"""
import csv
import hashlib
import io
import uuid
from datetime import date
from decimal import Decimal, InvalidOperation
from django.utils import timezone
from ingestion.models import IngestionJob, RawUpload, ParsedRow, JobStatus, ParseStatus, SourceType
from normalization.models import (
    CanonicalActivityRecord,
    NormalizationEvent,
    NormalizationEventType,
    AppliedBy,
    ReviewStatus,
    ReviewPriority,
)
from review.models import AnomalyFlag, Severity, ResolutionStatus


class BaseParser:
    """
    Abstract base for all source parsers.

    Subclasses must implement:
    - parse_and_normalize(rows, job, tenant) -> list of CanonicalActivityRecord
    """

    source_type = None  # Override in subclass

    def __init__(self, tenant, user):
        self.tenant = tenant
        self.user = user
        self.errors = []
        self.normalization_events = []

    def ingest_file(self, file_content, file_name):
        """
        Main entry point. Creates IngestionJob, parses file, normalizes rows.
        Returns the IngestionJob instance.
        """
        file_hash = hashlib.sha256(file_content.encode("utf-8")).hexdigest()

        # Check for duplicate upload
        if IngestionJob.objects.filter(
            tenant=self.tenant, file_hash=file_hash
        ).exists():
            raise ValueError(
                f"Duplicate file detected. A file with hash {file_hash[:12]}... "
                f"has already been uploaded."
            )

        job = IngestionJob.objects.create(
            tenant=self.tenant,
            source_type=self.source_type,
            triggered_by=self.user,
            file_name=file_name,
            file_hash=file_hash,
            status=JobStatus.PARSING,
        )

        try:
            rows = self._read_csv(file_content)
            job.total_rows = len(rows)
            job.save()

            raw_uploads = self._create_raw_uploads(rows, job)
            records = self.parse_and_normalize(rows, raw_uploads, job)

            # Update job stats
            job.parsed_rows = ParsedRow.objects.filter(
                job=job, parse_status=ParseStatus.SUCCESS
            ).count()
            job.failed_rows = ParsedRow.objects.filter(
                job=job, parse_status=ParseStatus.FAILED
            ).count()
            job.suspicious_rows = CanonicalActivityRecord.objects.filter(
                job=job, requires_human_review=True
            ).count()
            job.status = JobStatus.COMPLETE
            job.completed_at = timezone.now()
            job.save()

        except Exception as e:
            job.status = JobStatus.FAILED
            job.completed_at = timezone.now()
            job.save()
            raise

        return job

    def parse_and_normalize(self, rows, raw_uploads, job):
        """Override in subclass."""
        raise NotImplementedError

    def _read_csv(self, file_content):
        """Read CSV content into list of dicts."""
        reader = csv.DictReader(io.StringIO(file_content))
        return [row for row in reader]

    def _create_raw_uploads(self, rows, job):
        """Create immutable RawUpload records for each source row."""
        uploads = []
        for i, row in enumerate(rows, start=1):
            # Filter None keys (can happen with malformed CSVs / extra columns)
            clean_row = {k: v for k, v in dict(row).items() if k is not None}
            raw = RawUpload(
                job=job,
                tenant=self.tenant,
                row_number=i,
                raw_payload=clean_row,
            )
            import json
            payload_str = json.dumps(clean_row, sort_keys=True)
            raw.immutable_hash = hashlib.sha256(payload_str.encode()).hexdigest()
            raw.save()
            uploads.append(raw)
        return uploads

    def create_parsed_row(self, raw, job, status, errors=None, schema="", locale="", date_format=""):
        """Create a ParsedRow for a source row."""
        return ParsedRow.objects.create(
            raw=raw,
            job=job,
            parse_status=status,
            parse_errors=errors or [],
            detected_schema=schema,
            locale_detected=locale,
            date_format_inferred=date_format,
        )

    def create_anomaly_flag(self, record, flag_type, severity, auto_resolvable=False):
        """Create an AnomalyFlag for a canonical record."""
        flag = AnomalyFlag.objects.create(
            record=record,
            tenant=self.tenant,
            flag_type=flag_type,
            severity=severity,
            auto_resolvable=auto_resolvable,
        )
        # Update the record's anomaly_flags list
        flags = record.anomaly_flags or []
        flags.append(str(flag.id))
        record.anomaly_flags = flags
        if severity == Severity.BLOCKING:
            record.requires_human_review = True
        record.save()
        return flag

    def log_normalization_event(self, record, event_type, field_name, before, after, rule=""):
        """Log a NormalizationEvent."""
        return NormalizationEvent.objects.create(
            record=record,
            tenant=self.tenant,
            event_type=event_type,
            field_name=field_name,
            before_value=str(before),
            after_value=str(after),
            rule_applied=rule,
            applied_by=AppliedBy.SYSTEM,
        )

    def compute_confidence_and_priority(self, record):
        """
        Deterministic confidence score computation.

        Score starts at 1.000 and is reduced by specific deduction triggers.
        Priority bands: ≥0.85=LOW, 0.60-0.84=MEDIUM, 0.35-0.59=HIGH, <0.35=CRITICAL
        """
        score = Decimal("1.000")
        flags = AnomalyFlag.objects.filter(record=record)

        deductions = {
            "MISSING_COST_CENTER": Decimal("0.300"),
            "CROSS_DIMENSIONAL_UOM": Decimal("0.500"),
            "LEADING_ZERO_TRUNCATION": Decimal("0.400"),
            "VIRTUAL_PLANT_CODE": Decimal("0.350"),
            "MISSING_SUPPLIER_ON_REVERSAL": Decimal("0.200"),
            "EUROPEAN_NUMBER_FORMAT": Decimal("0.050"),
            "MISSING_INTERVAL": Decimal("0.150"),
            "UNIT_SHIFT_MWH": Decimal("0.050"),
            "ACTIVE_EXPORT_DETECTED": Decimal("0.100"),
            "MISSING_AIRPORT_CODE": Decimal("0.250"),
            "MISSING_DISTANCE": Decimal("0.250"),
            "CANCELED_TICKET": Decimal("0.400"),
            "DUPLICATE_SEGMENT": Decimal("0.200"),
            "AMBIGUOUS_AIRPORT": Decimal("0.150"),
            "AMBIGUOUS_TRAVEL_CATEGORY": Decimal("0.300"),
            "ORPHANED_MATERIAL": Decimal("0.400"),
            "DUPLICATE_TIMESTAMP": Decimal("0.100"),
            "TRAILING_MINUS": Decimal("0.050"),
            "REACTIVE_POWER_EXCLUDED": Decimal("0.050"),
        }

        for flag in flags:
            deduction = deductions.get(flag.flag_type, Decimal("0.100"))
            score -= deduction

        score = max(score, Decimal("0.000"))
        record.confidence_score = score

        if score >= Decimal("0.850"):
            record.review_priority = ReviewPriority.LOW
        elif score >= Decimal("0.600"):
            record.review_priority = ReviewPriority.MEDIUM
        elif score >= Decimal("0.350"):
            record.review_priority = ReviewPriority.HIGH
        else:
            record.review_priority = ReviewPriority.CRITICAL

        record.save()
        return score
