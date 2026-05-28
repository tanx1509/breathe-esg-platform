"""
Seed sample data — runs all 3 sample CSVs through their respective parsers.

Creates the full chain: IngestionJob → RawUpload → ParsedRow →
CanonicalActivityRecord → NormalizationEvents → AnomalyFlags

Usage: python manage.py seed_sample_data
"""
import os
from django.core.management.base import BaseCommand
from core.models import Tenant, User
from ingestion.services.sap_parser import SAPParser
from ingestion.services.utility_parser import UtilityParser
from ingestion.services.travel_parser import TravelParser
from normalization.models import CanonicalActivityRecord, NormalizationEvent
from review.models import AnomalyFlag


class Command(BaseCommand):
    help = "Seed sample data by running all 3 CSVs through parsers"

    def handle(self, *args, **options):
        tenant = Tenant.objects.first()
        user = User.objects.filter(tenant=tenant, role="ANALYST").first()

        if not tenant or not user:
            self.stderr.write("Error: Run seed_reference_data first.")
            return

        from django.conf import settings
        sample_dir = os.path.join(settings.BASE_DIR, "sample_data")

        self.stdout.write(self.style.MIGRATE_HEADING("\n1. SAP MM Parser"))
        self._run_parser(
            SAPParser(tenant, user),
            os.path.join(sample_dir, "sap_mm_sample.csv"),
            "sap_mm_sample.csv",
        )

        self.stdout.write(self.style.MIGRATE_HEADING("\n2. Utility Interval Parser"))
        self._run_parser(
            UtilityParser(tenant, user),
            os.path.join(sample_dir, "utility_interval_sample.csv"),
            "utility_interval_sample.csv",
        )

        self.stdout.write(self.style.MIGRATE_HEADING("\n3. Travel Parser"))
        self._run_parser(
            TravelParser(tenant, user),
            os.path.join(sample_dir, "travel_concur_sample.csv"),
            "travel_concur_sample.csv",
        )

        # Summary
        self.stdout.write(self.style.MIGRATE_HEADING("\n--- Summary ---"))
        total_records = CanonicalActivityRecord.objects.filter(tenant=tenant).count()
        total_events = NormalizationEvent.objects.filter(tenant=tenant).count()
        total_flags = AnomalyFlag.objects.filter(tenant=tenant).count()
        review_required = CanonicalActivityRecord.objects.filter(
            tenant=tenant, requires_human_review=True
        ).count()

        self.stdout.write(f"  Total canonical records: {total_records}")
        self.stdout.write(f"  Total normalization events: {total_events}")
        self.stdout.write(f"  Total anomaly flags: {total_flags}")
        self.stdout.write(f"  Records requiring review: {review_required}")
        self.stdout.write(self.style.SUCCESS("\n✓ All sample data seeded."))

    def _run_parser(self, parser, file_path, file_name):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            job = parser.ingest_file(content, file_name)
            self.stdout.write(
                f"  Job {job.id}: {job.status} — "
                f"total={job.total_rows}, parsed={job.parsed_rows}, "
                f"failed={job.failed_rows}, suspicious={job.suspicious_rows}"
            )
        except Exception as e:
            self.stderr.write(f"  Error: {e}")
            import traceback
            traceback.print_exc()
