from django.urls import path
from ingestion.views import FileUploadView, JobDetailView, JobListView

urlpatterns = [
    path("ingest/upload/", FileUploadView.as_view(), name="ingest-upload"),
    path("ingest/job/<uuid:id>/", JobDetailView.as_view(), name="job-detail"),
    path("ingest/jobs/", JobListView.as_view(), name="job-list"),
]
