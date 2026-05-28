from django.urls import path
from review.views import (
    ReviewQueueView,
    RecordDetailView,
    ApproveRecordView,
    RejectRecordView,
    EditRecordView,
    ResolveFlagView,
    IngestionStatsView,
)

urlpatterns = [
    path("review/queue/", ReviewQueueView.as_view(), name="review-queue"),
    path("review/record/<uuid:id>/", RecordDetailView.as_view(), name="record-detail"),
    path("review/record/<uuid:id>/approve/", ApproveRecordView.as_view(), name="record-approve"),
    path("review/record/<uuid:id>/reject/", RejectRecordView.as_view(), name="record-reject"),
    path("review/record/<uuid:id>/edit/", EditRecordView.as_view(), name="record-edit"),
    path("review/flag/<uuid:flag_id>/resolve/", ResolveFlagView.as_view(), name="flag-resolve"),
    path("ingest/stats/", IngestionStatsView.as_view(), name="ingest-stats"),
]
