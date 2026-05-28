"""
Ingestion API views — file upload and job status.

Endpoints:
- POST /api/ingest/upload/     — upload file + source_type
- GET  /api/ingest/job/{id}/   — job status + row counts
- GET  /api/ingest/jobs/       — recent jobs list
"""
import hashlib
from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser
from core.permissions import IsAnalystOrAdmin
from ingestion.models import IngestionJob
from ingestion.services.sap_parser import SAPParser
from ingestion.services.utility_parser import UtilityParser
from ingestion.services.travel_parser import TravelParser
from review.serializers import IngestionJobSerializer, IngestionJobListSerializer


PARSER_MAP = {
    "SAP_MM": SAPParser,
    "UTILITY_INTERVAL": UtilityParser,
    "TRAVEL_CONCUR": TravelParser,
}


class FileUploadView(APIView):
    """
    POST /api/ingest/upload/

    Accepts file upload + source_type.
    Creates IngestionJob, runs parser, returns job_id.
    """

    permission_classes = [IsAuthenticated, IsAnalystOrAdmin]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        source_type = request.data.get("source_type")
        file = request.FILES.get("file")

        if not source_type or source_type not in PARSER_MAP:
            return Response(
                {"error": f"Invalid source_type. Must be one of: {list(PARSER_MAP.keys())}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not file:
            return Response(
                {"error": "No file provided"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            content = file.read().decode("utf-8")
        except UnicodeDecodeError:
            return Response(
                {"error": "File must be UTF-8 encoded CSV"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        parser_class = PARSER_MAP[source_type]
        parser = parser_class(request.user.tenant, request.user)

        try:
            job = parser.ingest_file(content, file.name)
            return Response(
                IngestionJobSerializer(job).data,
                status=status.HTTP_201_CREATED,
            )
        except ValueError as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_409_CONFLICT,
            )
        except Exception as e:
            return Response(
                {"error": f"Ingestion failed: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class JobDetailView(generics.RetrieveAPIView):
    """
    GET /api/ingest/job/{id}/

    Returns job status + row counts.
    """

    serializer_class = IngestionJobSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "id"

    def get_queryset(self):
        return IngestionJob.objects.filter(tenant=self.request.user.tenant)


class JobListView(generics.ListAPIView):
    """
    GET /api/ingest/jobs/

    Returns recent jobs list with status.
    """

    serializer_class = IngestionJobListSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = IngestionJob.objects.filter(tenant=self.request.user.tenant)
        source_type = self.request.query_params.get("source_type")
        if source_type:
            qs = qs.filter(source_type=source_type)
        return qs.order_by("-triggered_at")
