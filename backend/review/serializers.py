"""
Serializers for the review and ingestion API.

These serializers power the analyst review queue, provenance drawer,
and ingestion status views.
"""
from rest_framework import serializers
from normalization.models import CanonicalActivityRecord, NormalizationEvent
from review.models import AnomalyFlag, ReviewEvent, AuditLock
from ingestion.models import IngestionJob, RawUpload, ParsedRow


# ---------------------------------------------------------------------------
# Ingestion serializers
# ---------------------------------------------------------------------------

class IngestionJobSerializer(serializers.ModelSerializer):
    class Meta:
        model = IngestionJob
        fields = [
            "id", "tenant_id", "source_type", "triggered_by", "triggered_at",
            "file_name", "file_hash", "status", "total_rows", "parsed_rows",
            "failed_rows", "suspicious_rows", "completed_at",
        ]


class IngestionJobListSerializer(serializers.ModelSerializer):
    """Lightweight version for job lists."""
    class Meta:
        model = IngestionJob
        fields = [
            "id", "source_type", "file_name", "status", "total_rows",
            "parsed_rows", "failed_rows", "suspicious_rows", "triggered_at",
            "completed_at",
        ]


class RawUploadSerializer(serializers.ModelSerializer):
    class Meta:
        model = RawUpload
        fields = ["id", "row_number", "raw_payload", "received_at", "immutable_hash"]


class ParsedRowSerializer(serializers.ModelSerializer):
    class Meta:
        model = ParsedRow
        fields = [
            "id", "parse_status", "parse_errors", "detected_schema",
            "locale_detected", "date_format_inferred", "parsed_at",
        ]


# ---------------------------------------------------------------------------
# Normalization serializers
# ---------------------------------------------------------------------------

class NormalizationEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = NormalizationEvent
        fields = [
            "id", "event_type", "field_name", "before_value", "after_value",
            "rule_applied", "applied_by", "applied_by_user", "applied_at", "notes",
        ]


# ---------------------------------------------------------------------------
# Review serializers
# ---------------------------------------------------------------------------

class AnomalyFlagSerializer(serializers.ModelSerializer):
    class Meta:
        model = AnomalyFlag
        fields = [
            "id", "flag_type", "severity", "auto_resolvable",
            "resolution_status", "resolution_note", "resolved_by",
            "resolved_at", "detected_at",
        ]


class ReviewEventSerializer(serializers.ModelSerializer):
    performed_by_email = serializers.SerializerMethodField()

    class Meta:
        model = ReviewEvent
        fields = [
            "id", "action", "previous_status", "new_status",
            "performed_by", "performed_by_email", "performed_at",
            "notes", "fields_edited",
        ]

    def get_performed_by_email(self, obj):
        if obj.performed_by:
            return obj.performed_by.email
        return None


# ---------------------------------------------------------------------------
# Canonical record serializers
# ---------------------------------------------------------------------------

class ReviewQueueSerializer(serializers.ModelSerializer):
    """Lightweight serializer for the review queue table view."""
    anomaly_summary = serializers.SerializerMethodField()
    blocking_count = serializers.SerializerMethodField()
    warning_count = serializers.SerializerMethodField()

    class Meta:
        model = CanonicalActivityRecord
        fields = [
            "id", "source_type", "source_document_ref", "scope_category",
            "scope_subcategory", "activity_type", "activity_date",
            "raw_quantity_string", "raw_unit", "normalized_quantity",
            "normalized_unit", "confidence_score", "review_priority",
            "review_status", "requires_human_review",
            "anomaly_summary", "blocking_count", "warning_count",
            "normalization_rules", "facility_id", "cost_center",
            "calculated_emissions", "created_at",
        ]

    def get_anomaly_summary(self, obj):
        flags = obj.anomaly_flag_records.all()
        return [
            {
                "id": str(f.id),
                "type": f.flag_type,
                "severity": f.severity,
                "status": f.resolution_status,
            }
            for f in flags
        ]

    def get_blocking_count(self, obj):
        return obj.anomaly_flag_records.filter(
            severity="BLOCKING", resolution_status="OPEN"
        ).count()

    def get_warning_count(self, obj):
        return obj.anomaly_flag_records.filter(severity="WARNING").count()


class RecordDetailSerializer(serializers.ModelSerializer):
    """Full detail serializer for provenance drawer."""
    raw_payload = serializers.SerializerMethodField()
    parsed_row = serializers.SerializerMethodField()
    normalization_events = serializers.SerializerMethodField()
    anomaly_flags = serializers.SerializerMethodField()
    review_events = serializers.SerializerMethodField()

    class Meta:
        model = CanonicalActivityRecord
        fields = [
            # Identity
            "id", "source_type", "source_document_ref", "activity_type",
            # Scope
            "scope_category", "scope_subcategory", "ghg_protocol_category",
            # Temporal
            "activity_date", "reporting_period_year", "reporting_period_month",
            # Raw quantity
            "raw_quantity", "raw_unit", "raw_quantity_string",
            # Normalized quantity
            "normalized_quantity", "normalized_unit", "unit_dimension",
            # Emissions
            "emission_factor_id", "emission_factor_value", "emission_factor_unit",
            "calculated_emissions", "emissions_locked",
            # Context
            "facility_id", "cost_center", "supplier_id", "material_group",
            # Trust
            "confidence_score", "review_priority", "requires_human_review",
            "review_status", "normalization_rules",
            # Provenance
            "immutable_hash", "approved_by", "approved_at", "audit_locked_at",
            # Metadata
            "source_metadata", "created_at", "updated_at",
            # Related data
            "raw_payload", "parsed_row", "normalization_events",
            "anomaly_flags", "review_events",
        ]

    def get_raw_payload(self, obj):
        try:
            raw = obj.raw
            return RawUploadSerializer(raw).data
        except RawUpload.DoesNotExist:
            return None

    def get_parsed_row(self, obj):
        try:
            parsed = obj.raw.parsed_row
            return ParsedRowSerializer(parsed).data
        except (ParsedRow.DoesNotExist, AttributeError):
            return None

    def get_normalization_events(self, obj):
        events = obj.normalization_events.order_by("applied_at")
        return NormalizationEventSerializer(events, many=True).data

    def get_anomaly_flags(self, obj):
        flags = obj.anomaly_flag_records.order_by("-detected_at")
        return AnomalyFlagSerializer(flags, many=True).data

    def get_review_events(self, obj):
        events = obj.review_events.order_by("performed_at")
        return ReviewEventSerializer(events, many=True).data


# ---------------------------------------------------------------------------
# Ingestion stats serializer
# ---------------------------------------------------------------------------

class IngestionStatsSerializer(serializers.Serializer):
    source_type = serializers.CharField()
    total_jobs = serializers.IntegerField()
    total_rows = serializers.IntegerField()
    failed_rows = serializers.IntegerField()
    suspicious_rows = serializers.IntegerField()
    pending_review = serializers.IntegerField()
