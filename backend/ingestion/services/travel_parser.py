"""
Travel (Concur/Navan) CSV Parser — segment-level flight data.

Anomalies handled:
- Segment-level modeling (not trip-level)
- Status filter: only "flown" generates emissions
- Duplicate segments → flag DUPLICATE_SEGMENT, keep one
- Airport code enrichment → Haversine great-circle distance
- Missing distance → flag MISSING_DISTANCE
- City codes (is_city_code=true) → flag AMBIGUOUS_AIRPORT
- Cabin class → emission factor multiplier
- Null destination → flag MISSING_AIRPORT_CODE, block
- Ambiguous category "Misc Travel" → flag
"""
import math
from datetime import datetime
from decimal import Decimal
from ingestion.models import ParseStatus, SourceType
from ingestion.services.base_parser import BaseParser
from normalization.models import (
    CanonicalActivityRecord,
    NormalizationEventType,
    ScopeCategory,
)
from review.models import FlagType, Severity, ResolutionStatus
from reference.models import AirportReferenceTable, EmissionFactorTable

# Cabin class emission multipliers (relative to economy)
CABIN_MULTIPLIERS = {
    "ECONOMY": Decimal("1.0"),
    "PREMIUM ECONOMY": Decimal("1.5"),
    "PREMIUM_ECONOMY": Decimal("1.5"),
    "BUSINESS": Decimal("2.0"),
    "FIRST": Decimal("2.4"),
}


def haversine_distance(lat1, lon1, lat2, lon2):
    """Compute great-circle distance in km using Haversine formula."""
    R = 6371.0  # Earth radius in km
    lat1_r, lon1_r = math.radians(float(lat1)), math.radians(float(lon1))
    lat2_r, lon2_r = math.radians(float(lat2)), math.radians(float(lon2))
    dlat = lat2_r - lat1_r
    dlon = lon2_r - lon1_r
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1_r) * math.cos(lat2_r) * math.sin(dlon / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return round(R * c, 2)


class TravelParser(BaseParser):
    source_type = SourceType.TRAVEL_CONCUR

    def parse_and_normalize(self, rows, raw_uploads, job):
        records = []
        seen_segments = set()

        for i, (row, raw) in enumerate(zip(rows, raw_uploads)):
            try:
                record = self._process_row(row, raw, job, seen_segments)
                if record:
                    records.append(record)
                    self.create_parsed_row(
                        raw, job, ParseStatus.SUCCESS,
                        schema="TRAVEL_CONCUR_SEGMENT",
                        locale="en-US",
                    )
                else:
                    self.create_parsed_row(
                        raw, job, ParseStatus.FAILED,
                        errors=[{"field": "processing", "raw_value": "", "error_type": "row_excluded"}],
                        schema="TRAVEL_CONCUR_SEGMENT",
                    )
            except Exception as e:
                self.create_parsed_row(
                    raw, job, ParseStatus.FAILED,
                    errors=[{"field": "processing", "raw_value": str(e), "error_type": "parse_exception"}],
                )
        return records

    def _process_row(self, row, raw, job, seen_segments):
        """Process a single travel segment."""
        booking_ref = (row.get("Booking_Ref") or "").strip()
        traveler = (row.get("Traveler_Name") or "").strip()
        travel_date_str = (row.get("Travel_Date") or "").strip()
        origin = (row.get("Origin") or "").strip().upper()
        destination = (row.get("Destination") or "").strip().upper()
        cabin_class = (row.get("Cabin_Class") or "").strip()
        status = (row.get("Status") or "").strip().lower()
        category = (row.get("Category") or "").strip()
        cost_center = (row.get("Cost_Center") or "").strip()
        airline = (row.get("Airline") or "").strip()

        rules_applied = []

        # Create canonical record
        record = CanonicalActivityRecord.objects.create(
            tenant=self.tenant,
            raw=raw,
            job=job,
            source_type=SourceType.TRAVEL_CONCUR,
            source_document_ref=booking_ref,
            raw_unit="segment",
            cost_center=cost_center,
            supplier_id=airline,
            immutable_hash=raw.immutable_hash,
            source_metadata={
                "traveler_name": traveler,
                "cabin_class": cabin_class,
                "status": status,
                "category": category,
                "origin": origin,
                "destination": destination,
            },
        )

        # --- Status filter ---
        if status not in ("flown",):
            status_label = status.upper()
            self.log_normalization_event(
                record, NormalizationEventType.STATUS_FILTER,
                "status", status, "EXCLUDED",
                f"status_{status}_not_flown"
            )
            self.create_anomaly_flag(
                record, FlagType.CANCELED_TICKET, Severity.WARNING
            )
            record.activity_type = "air_travel_excluded"
            record.normalization_rules = [f"status_{status}_excluded"]
            record.save()
            self.compute_confidence_and_priority(record)
            return record

        # --- Ambiguous travel category ---
        if category.lower() in ("misc travel", "misc", "ground transport", "other"):
            self.create_anomaly_flag(
                record, FlagType.AMBIGUOUS_TRAVEL_CATEGORY, Severity.BLOCKING
            )
            rules_applied.append("expense_category_ambiguity_flagged")

        # --- Duplicate segment detection ---
        segment_key = f"{origin}_{destination}_{travel_date_str}_{traveler}"
        if segment_key in seen_segments:
            self.create_anomaly_flag(
                record, FlagType.DUPLICATE_SEGMENT, Severity.WARNING
            )
            rules_applied.append("duplicate_segment_flagged")
        seen_segments.add(segment_key)

        # --- Missing destination ---
        if not destination:
            self.create_anomaly_flag(
                record, FlagType.MISSING_AIRPORT_CODE, Severity.BLOCKING
            )
            record.requires_human_review = True
            record.activity_type = "air_travel"
            record.scope_category = ScopeCategory.SCOPE_3
            record.scope_subcategory = "business_travel"
            record.ghg_protocol_category = "Category 6"
            record.normalization_rules = rules_applied + ["missing_destination_blocked"]
            record.save()
            self.compute_confidence_and_priority(record)
            return record

        # --- Airport enrichment + distance calculation ---
        origin_airport = AirportReferenceTable.objects.filter(iata_code=origin).first()
        dest_airport = AirportReferenceTable.objects.filter(iata_code=destination).first()

        distance = None

        # Check for city codes
        if origin_airport and origin_airport.is_city_code:
            self.create_anomaly_flag(
                record, FlagType.AMBIGUOUS_AIRPORT, Severity.WARNING
            )
            rules_applied.append(f"ambiguous_city_code_{origin}")

        if dest_airport and dest_airport.is_city_code:
            self.create_anomaly_flag(
                record, FlagType.AMBIGUOUS_AIRPORT, Severity.WARNING
            )
            rules_applied.append(f"ambiguous_city_code_{destination}")

        if origin_airport and dest_airport:
            distance = haversine_distance(
                origin_airport.latitude, origin_airport.longitude,
                dest_airport.latitude, dest_airport.longitude,
            )
            self.log_normalization_event(
                record, NormalizationEventType.DISTANCE_CALCULATION,
                "distance_km", f"{origin}→{destination}",
                str(distance),
                "haversine_great_circle"
            )
            record.raw_quantity = Decimal(str(distance))
            record.normalized_quantity = Decimal(str(distance))
            record.normalized_unit = "km"
            record.unit_dimension = "distance"
            record.raw_quantity_string = f"{origin}→{destination}: {distance} km"
            rules_applied.append("haversine_distance_calculated")

            # Airport enrichment event
            self.log_normalization_event(
                record, NormalizationEventType.AIRPORT_ENRICHMENT,
                "origin", origin, origin_airport.airport_name,
                f"iata_lookup_{origin}"
            )
            self.log_normalization_event(
                record, NormalizationEventType.AIRPORT_ENRICHMENT,
                "destination", destination, dest_airport.airport_name,
                f"iata_lookup_{destination}"
            )
        else:
            self.create_anomaly_flag(
                record, FlagType.MISSING_DISTANCE, Severity.WARNING
            )
            record.requires_human_review = True
            rules_applied.append("distance_enrichment_failed")

        # --- Cabin class multiplier ---
        cabin_upper = cabin_class.upper()
        multiplier = CABIN_MULTIPLIERS.get(cabin_upper, Decimal("1.0"))
        if multiplier != Decimal("1.0"):
            self.log_normalization_event(
                record, NormalizationEventType.CABIN_CLASS_MULTIPLIER,
                "cabin_multiplier", "1.0", str(multiplier),
                f"cabin_{cabin_upper}_multiplier"
            )
            rules_applied.append(f"cabin_class_{cabin_upper}_{multiplier}x")

        # --- Scope assignment ---
        record.scope_category = ScopeCategory.SCOPE_3
        record.scope_subcategory = "business_travel"
        record.activity_type = "air_travel"
        record.ghg_protocol_category = "Category 6"
        self.log_normalization_event(
            record, NormalizationEventType.SCOPE_ASSIGNMENT,
            "scope_category", "", "SCOPE_3",
            "travel_flown_scope3_business_travel"
        )
        rules_applied.append("scope3_business_travel")

        # --- Date parsing ---
        if travel_date_str:
            try:
                dt = datetime.strptime(travel_date_str, "%Y-%m-%d").date()
                record.activity_date = dt
                record.reporting_period_year = dt.year
                record.reporting_period_month = dt.month
            except ValueError:
                pass

        # --- Emission factor ---
        self._apply_emission_factor(record, distance, multiplier, rules_applied)

        record.normalization_rules = rules_applied
        record.save()
        self.compute_confidence_and_priority(record)
        return record

    def _apply_emission_factor(self, record, distance, cabin_multiplier, rules):
        """Apply flight emission factor with cabin class multiplier."""
        if not distance or not record.normalized_quantity:
            return

        # Determine flight distance category
        if distance < 500:
            material_group = "FLIGHT_DOMESTIC"
        elif distance < 3700:
            material_group = "FLIGHT_SHORT_HAUL"
        else:
            material_group = "FLIGHT_LONG_HAUL"

        factor = EmissionFactorTable.objects.filter(
            material_group=material_group,
            scope_category="SCOPE_3",
            unit="km",
        ).first()

        if factor:
            base_emissions = abs(record.normalized_quantity) * factor.factor_value
            adjusted_emissions = base_emissions * cabin_multiplier

            record.emission_factor_id = factor.id
            record.emission_factor_value = factor.factor_value
            record.emission_factor_unit = f"kgCO2e/{factor.unit}"
            record.calculated_emissions = adjusted_emissions
            record.material_group = material_group

            self.log_normalization_event(
                record, NormalizationEventType.EMISSION_FACTOR_APPLIED,
                "calculated_emissions", "0",
                str(adjusted_emissions),
                f"factor_{factor.source}_{factor.factor_value}_x{cabin_multiplier}"
            )
            rules.append(f"emission_factor_{material_group}_{factor.source}")
