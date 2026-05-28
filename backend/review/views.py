"""
Review API views — the core product endpoints.

Endpoints:
- GET  /api/review/queue/           — paginated review queue
- GET  /api/review/record/{id}/     — full record detail (provenance)
- POST /api/review/record/{id}/approve/   — approve record
- POST /api/review/record/{id}/reject/    — reject record
- POST /api/review/record/{id}/edit/      — edit and approve
- POST /api/review/flag/{flag_id}/resolve/ — resolve anomaly flag
"""
from django.utils import timezone
from django.db.models import Q
from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from core.permissions import IsAnalystOrAdmin
from normalization.models import (
    CanonicalActivityRecord,
    NormalizationEvent,
    NormalizationEventType,
    AppliedBy,
    ReviewStatus,
)
from review.models import (
    AnomalyFlag,
    ReviewEvent,
    ReviewAction,
    Severity,
    ResolutionStatus,
)
from review.serializers import (
    ReviewQueueSerializer,
    RecordDetailSerializer,
    AnomalyFlagSerializer,
    ReviewEventSerializer,
)


class ReviewQueueView(generics.ListAPIView):
    """
    GET /api/review/queue/

    Paginated review queue. Returns CanonicalActivityRecords sorted by
    confidence_score ASC (worst records first).

    Filters:
    - source_type: SAP_MM, UTILITY_INTERVAL, TRAVEL_CONCUR
    - scope_category: SCOPE_1, SCOPE_2, SCOPE_3
    - review_status: PENDING, UNDER_REVIEW, APPROVED, REJECTED, AUDIT_LOCKED
    - review_priority: LOW, MEDIUM, HIGH, CRITICAL
    - anomaly_flag_type: any FlagType value
    - date_from, date_to: YYYY-MM-DD
    - requires_review: true/false
    """

    serializer_class = ReviewQueueSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = CanonicalActivityRecord.objects.filter(tenant=self.request.user.tenant)

        # Filters
        source_type = self.request.query_params.get("source_type")
        if source_type:
            qs = qs.filter(source_type=source_type)

        scope = self.request.query_params.get("scope_category")
        if scope:
            qs = qs.filter(scope_category=scope)

        review_status = self.request.query_params.get("review_status")
        if review_status:
            qs = qs.filter(review_status=review_status)

        priority = self.request.query_params.get("review_priority")
        if priority:
            qs = qs.filter(review_priority=priority)

        flag_type = self.request.query_params.get("anomaly_flag_type")
        if flag_type:
            qs = qs.filter(anomaly_flag_records__flag_type=flag_type).distinct()

        date_from = self.request.query_params.get("date_from")
        if date_from:
            qs = qs.filter(activity_date__gte=date_from)

        date_to = self.request.query_params.get("date_to")
        if date_to:
            qs = qs.filter(activity_date__lte=date_to)

        requires_review = self.request.query_params.get("requires_review")
        if requires_review == "true":
            qs = qs.filter(requires_human_review=True)

        # Default sort: confidence ASC (worst first), then by date
        return qs.order_by("confidence_score", "-created_at")


class RecordDetailView(generics.RetrieveAPIView):
    """
    GET /api/review/record/{id}/

    Full record detail including:
    - Raw payload from RawUpload (side-by-side view)
    - Full NormalizationEvent history (transformation timeline)
    - All AnomalyFlags with resolution status
    - ReviewEvent history
    """

    serializer_class = RecordDetailSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "id"

    def get_queryset(self):
        return CanonicalActivityRecord.objects.filter(tenant=self.request.user.tenant)


class ApproveRecordView(APIView):
    """
    POST /api/review/record/{id}/approve/

    Creates ReviewEvent with action=APPROVE.
    Validates: no unresolved BLOCKING flags.
    Validates: record is processable.
    """

    permission_classes = [IsAuthenticated, IsAnalystOrAdmin]

    def post(self, request, id):
        try:
            record = CanonicalActivityRecord.objects.get(
                id=id, tenant=request.user.tenant
            )
        except CanonicalActivityRecord.DoesNotExist:
            return Response(
                {"error": "Record not found"}, status=status.HTTP_404_NOT_FOUND
            )

        # Validate: no unresolved BLOCKING flags
        blocking = AnomalyFlag.objects.filter(
            record=record,
            severity=Severity.BLOCKING,
            resolution_status=ResolutionStatus.OPEN,
        ).count()

        if blocking > 0:
            return Response(
                {
                    "error": f"Cannot approve: {blocking} unresolved BLOCKING anomaly flag(s)",
                    "blocking_flags": AnomalyFlagSerializer(
                        AnomalyFlag.objects.filter(
                            record=record,
                            severity=Severity.BLOCKING,
                            resolution_status=ResolutionStatus.OPEN,
                        ),
                        many=True,
                    ).data,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Validate: cannot approve AUDIT_LOCKED
        if record.review_status == ReviewStatus.AUDIT_LOCKED:
            return Response(
                {"error": "Record is audit-locked and cannot be modified"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        previous_status = record.review_status

        # Create ReviewEvent
        ReviewEvent.objects.create(
            record=record,
            tenant=request.user.tenant,
            action=ReviewAction.APPROVE,
            previous_status=previous_status,
            new_status=ReviewStatus.APPROVED,
            performed_by=request.user,
            notes=request.data.get("notes", ""),
        )

        # Update record
        record.review_status = ReviewStatus.APPROVED
        record.approved_by = request.user
        record.approved_at = timezone.now()
        record.save()

        return Response(
            {"status": "approved", "record_id": str(record.id)},
            status=status.HTTP_200_OK,
        )


class RejectRecordView(APIView):
    """
    POST /api/review/record/{id}/reject/

    Creates ReviewEvent with action=REJECT.
    Notes field is required.
    """

    permission_classes = [IsAuthenticated, IsAnalystOrAdmin]

    def post(self, request, id):
        try:
            record = CanonicalActivityRecord.objects.get(
                id=id, tenant=request.user.tenant
            )
        except CanonicalActivityRecord.DoesNotExist:
            return Response(
                {"error": "Record not found"}, status=status.HTTP_404_NOT_FOUND
            )

        notes = request.data.get("notes", "")
        if not notes:
            return Response(
                {"error": "Notes are required for rejection"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if record.review_status == ReviewStatus.AUDIT_LOCKED:
            return Response(
                {"error": "Record is audit-locked and cannot be modified"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        previous_status = record.review_status

        ReviewEvent.objects.create(
            record=record,
            tenant=request.user.tenant,
            action=ReviewAction.REJECT,
            previous_status=previous_status,
            new_status=ReviewStatus.REJECTED,
            performed_by=request.user,
            notes=notes,
        )

        record.review_status = ReviewStatus.REJECTED
        record.save()

        return Response(
            {"status": "rejected", "record_id": str(record.id)},
            status=status.HTTP_200_OK,
        )


class EditRecordView(APIView):
    """
    POST /api/review/record/{id}/edit/

    Creates ReviewEvent with action=EDIT_AND_APPROVE.
    Creates NormalizationEvent for each changed field.
    fields_edited must list what changed and why.
    """

    permission_classes = [IsAuthenticated, IsAnalystOrAdmin]

    def post(self, request, id):
        try:
            record = CanonicalActivityRecord.objects.get(
                id=id, tenant=request.user.tenant
            )
        except CanonicalActivityRecord.DoesNotExist:
            return Response(
                {"error": "Record not found"}, status=status.HTTP_404_NOT_FOUND
            )

        if record.review_status == ReviewStatus.AUDIT_LOCKED:
            return Response(
                {"error": "Record is audit-locked and cannot be modified"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        fields_edited = request.data.get("fields_edited", {})
        notes = request.data.get("notes", "")

        if not fields_edited:
            return Response(
                {"error": "fields_edited is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not notes:
            return Response(
                {"error": "Notes are required for edit-and-approve"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Apply edits and log normalization events
        for field_name, change in fields_edited.items():
            old_value = str(getattr(record, field_name, ""))
            new_value = str(change.get("value", ""))

            if hasattr(record, field_name):
                setattr(record, field_name, change.get("value"))

                NormalizationEvent.objects.create(
                    record=record,
                    tenant=request.user.tenant,
                    event_type=NormalizationEventType.MANUAL_CORRECTION,
                    field_name=field_name,
                    before_value=old_value,
                    after_value=new_value,
                    rule_applied="analyst_manual_correction",
                    applied_by=AppliedBy.ANALYST,
                    applied_by_user=request.user,
                    notes=change.get("reason", notes),
                )

        previous_status = record.review_status

        ReviewEvent.objects.create(
            record=record,
            tenant=request.user.tenant,
            action=ReviewAction.EDIT_AND_APPROVE,
            previous_status=previous_status,
            new_status=ReviewStatus.APPROVED,
            performed_by=request.user,
            notes=notes,
            fields_edited=fields_edited,
        )

        record.review_status = ReviewStatus.APPROVED
        record.approved_by = request.user
        record.approved_at = timezone.now()
        record.save()

        return Response(
            {"status": "edit_and_approved", "record_id": str(record.id)},
            status=status.HTTP_200_OK,
        )


class ResolveFlagView(APIView):
    """
    POST /api/review/flag/{flag_id}/resolve/

    Updates AnomalyFlag resolution_status.
    For BLOCKING flags: triggers confidence_score recalculation.
    """

    permission_classes = [IsAuthenticated, IsAnalystOrAdmin]

    def post(self, request, flag_id):
        try:
            flag = AnomalyFlag.objects.get(id=flag_id, tenant=request.user.tenant)
        except AnomalyFlag.DoesNotExist:
            return Response(
                {"error": "Flag not found"}, status=status.HTTP_404_NOT_FOUND
            )

        resolution_status = request.data.get("resolution_status", "ANALYST_RESOLVED")
        resolution_note = request.data.get("resolution_note", "")

        if not resolution_note:
            return Response(
                {"error": "Resolution note is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        flag.resolution_status = resolution_status
        flag.resolution_note = resolution_note
        flag.resolved_by = request.user
        flag.resolved_at = timezone.now()
        flag.save()

        # Recalculate confidence score on the parent record
        record = flag.record
        from ingestion.services.base_parser import BaseParser
        parser = BaseParser(request.user.tenant, request.user)
        parser.compute_confidence_and_priority(record)

        # Check if record still requires human review
        blocking_open = AnomalyFlag.objects.filter(
            record=record,
            severity=Severity.BLOCKING,
            resolution_status=ResolutionStatus.OPEN,
        ).count()
        record.requires_human_review = blocking_open > 0
        record.save()

        return Response(
            {
                "status": "resolved",
                "flag_id": str(flag.id),
                "new_confidence_score": str(record.confidence_score),
                "new_priority": record.review_priority,
                "still_requires_review": record.requires_human_review,
            },
            status=status.HTTP_200_OK,
        )


class IngestionStatsView(APIView):
    """
    GET /api/ingest/stats/

    Returns ingestion stats grouped by source type for the command center.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        from ingestion.models import IngestionJob
        from django.db.models import Sum, Count

        stats = []
        for source_type in ["SAP_MM", "UTILITY_INTERVAL", "TRAVEL_CONCUR"]:
            jobs = IngestionJob.objects.filter(
                tenant=request.user.tenant, source_type=source_type
            )
            total_jobs = jobs.count()
            agg = jobs.aggregate(
                total_rows=Sum("total_rows"),
                failed_rows=Sum("failed_rows"),
                suspicious_rows=Sum("suspicious_rows"),
            )

            pending_review = CanonicalActivityRecord.objects.filter(
                tenant=request.user.tenant,
                source_type=source_type,
                review_status__in=["PENDING", "UNDER_REVIEW"],
            ).count()

            stats.append({
                "source_type": source_type,
                "total_jobs": total_jobs,
                "total_rows": agg["total_rows"] or 0,
                "failed_rows": agg["failed_rows"] or 0,
                "suspicious_rows": agg["suspicious_rows"] or 0,
                "pending_review": pending_review,
            })

        return Response(stats)
