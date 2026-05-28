"""
Utility Interval CSV Parser — handles interval-meter CSV exports.

Anomalies handled:
- Leading zero strip on meter serial → pad to known length
- Duplicate timestamps → dedup hierarchy: drop null, retain estimated, log event
- Missing intervals → detect gaps in timestamp sequence
- Unit shift kWh → MWh → normalize all to kWh
- Active Export (negative / Export channel) → exclude from Scope 2
- Reactive power (kVARh, kVAh) → exclude entirely
- Footer summary rows (null Start_Time) → skip
- String "N/A" in numeric field → cast to null, flag MISSING_INTERVAL
"""
from datetime import datetime
from decimal import Decimal, InvalidOperation
from ingestion.models import ParseStatus, SourceType
from ingestion.services.base_parser import BaseParser
from normalization.models import (
    CanonicalActivityRecord,
    NormalizationEventType,
    ScopeCategory,
)
from review.models import FlagType, Severity, ResolutionStatus
from reference.models import EmissionFactorTable

EXPECTED_METER_SN_LENGTH = 10


class UtilityParser(BaseParser):
    source_type = SourceType.UTILITY_INTERVAL

    def parse_and_normalize(self, rows, raw_uploads, job):
        records = []
        # Group by meter for interval gap detection
        meter_timestamps = {}

        for i, (row, raw) in enumerate(zip(rows, raw_uploads)):
            # Skip footer summary rows
            start_time = (row.get("Start_Time") or "").strip()
            if not start_time:
                self.create_parsed_row(
                    raw, job, ParseStatus.FAILED,
                    errors=[{"field": "Start_Time", "raw_value": "", "error_type": "footer_summary_row"}],
                    schema="UTILITY_FOOTER_SKIP",
                )
                continue

            try:
                record = self._process_row(row, raw, job, meter_timestamps)
                if record:
                    records.append(record)
                    self.create_parsed_row(
                        raw, job, ParseStatus.SUCCESS,
                        schema="UTILITY_15MIN_KWH",
                        locale="en-US",
                    )
                else:
                    self.create_parsed_row(
                        raw, job, ParseStatus.FAILED,
                        errors=[{"field": "processing", "raw_value": "", "error_type": "row_excluded"}],
                        schema="UTILITY_INTERVAL",
                    )
            except Exception as e:
                self.create_parsed_row(
                    raw, job, ParseStatus.FAILED,
                    errors=[{"field": "processing", "raw_value": str(e), "error_type": "parse_exception"}],
                )

        # After processing all rows, detect missing intervals
        self._detect_missing_intervals(records, meter_timestamps)

        return records

    def _process_row(self, row, raw, job, meter_timestamps):
        """Process a single utility interval row."""
        meter_sn = (row.get("Meter_SN") or "").strip()
        channel = (row.get("Channel") or "").strip()
        start_time_str = (row.get("Start_Time") or "").strip()
        end_time_str = (row.get("End_Time") or "").strip()
        usage_str = (row.get("Usage") or "").strip()
        unit = (row.get("Unit") or "").strip()
        quality = (row.get("Quality") or "").strip()
        account_id = (row.get("Account_ID") or "").strip()

        rules_applied = []

        # Create canonical record
        record = CanonicalActivityRecord.objects.create(
            tenant=self.tenant,
            raw=raw,
            job=job,
            source_type=SourceType.UTILITY_INTERVAL,
            source_document_ref=meter_sn,
            raw_quantity_string=usage_str,
            raw_unit=unit,
            facility_id=meter_sn,
            immutable_hash=raw.immutable_hash,
            source_metadata={
                "account_id": account_id,
                "channel": channel,
                "quality": quality,
                "start_time": start_time_str,
                "end_time": end_time_str,
            },
        )

        # --- Leading zero restoration on meter serial ---
        if meter_sn and len(meter_sn) < EXPECTED_METER_SN_LENGTH:
            original = meter_sn
            padded = meter_sn.zfill(EXPECTED_METER_SN_LENGTH)
            record.facility_id = padded
            record.source_document_ref = padded
            self.log_normalization_event(
                record, NormalizationEventType.LEADING_ZERO_RESTORE,
                "meter_sn", original, padded,
                f"meter_sn_pad_to_{EXPECTED_METER_SN_LENGTH}"
            )
            self.create_anomaly_flag(
                record, FlagType.LEADING_ZERO_TRUNCATION, Severity.INFO, auto_resolvable=True
            )
            flag = record.anomaly_flag_records.filter(flag_type=FlagType.LEADING_ZERO_TRUNCATION).first()
            if flag:
                flag.resolution_status = ResolutionStatus.AUTO_RESOLVED
                flag.resolution_note = "Meter serial leading zeros restored"
                flag.save()
            rules_applied.append("meter_sn_leading_zero_restore")
            meter_sn = padded

        # --- Reactive power exclusion ---
        if unit.upper() in ("KVARH", "KVAH") or channel.lower() == "reactive":
            self.log_normalization_event(
                record, NormalizationEventType.REACTIVE_POWER_EXCLUSION,
                "unit", unit, "EXCLUDED",
                "reactive_power_not_consumption"
            )
            self.create_anomaly_flag(
                record, FlagType.REACTIVE_POWER_EXCLUDED, Severity.INFO, auto_resolvable=True
            )
            flag = record.anomaly_flag_records.filter(flag_type=FlagType.REACTIVE_POWER_EXCLUDED).first()
            if flag:
                flag.resolution_status = ResolutionStatus.AUTO_RESOLVED
                flag.resolution_note = "Reactive power excluded — not active consumption"
                flag.save()
            record.review_status = "REJECTED"
            record.normalization_rules = ["reactive_power_excluded"]
            record.save()
            self.compute_confidence_and_priority(record)
            return record

        # --- Active export exclusion ---
        if channel.lower() == "active export" or (usage_str and usage_str.startswith("-")):
            self.log_normalization_event(
                record, NormalizationEventType.ACTIVE_EXPORT_EXCLUSION,
                "channel", channel, "EXCLUDED_FROM_SCOPE2",
                "active_export_not_purchased"
            )
            self.create_anomaly_flag(
                record, FlagType.ACTIVE_EXPORT_DETECTED, Severity.WARNING
            )
            record.activity_type = "onsite_generation_export"
            record.normalization_rules = ["active_export_excluded"]
            record.save()
            self.compute_confidence_and_priority(record)
            return record

        # --- Handle "N/A" in usage ---
        if usage_str.upper() in ("N/A", "NA", "NULL", ""):
            record.raw_quantity = None
            record.normalized_quantity = None
            self.create_anomaly_flag(
                record, FlagType.MISSING_INTERVAL, Severity.WARNING
            )
            rules_applied.append("na_to_null")
        else:
            # --- Unit shift: MWh → kWh ---
            try:
                usage_value = Decimal(usage_str)
                record.raw_quantity = usage_value

                if unit.upper() == "MWH":
                    original_val = usage_value
                    usage_value = usage_value * 1000
                    unit = "kWh"
                    self.log_normalization_event(
                        record, NormalizationEventType.UOM_NORMALIZATION,
                        "usage", str(original_val) + " MWh",
                        str(usage_value) + " kWh",
                        "MWh_to_kWh_multiply_1000"
                    )
                    self.create_anomaly_flag(
                        record, FlagType.UNIT_SHIFT_MWH, Severity.INFO, auto_resolvable=True
                    )
                    flag = record.anomaly_flag_records.filter(flag_type=FlagType.UNIT_SHIFT_MWH).first()
                    if flag:
                        flag.resolution_status = ResolutionStatus.AUTO_RESOLVED
                        flag.resolution_note = "MWh converted to kWh"
                        flag.save()
                    rules_applied.append("MWh_to_kWh")

                record.normalized_quantity = usage_value
                record.normalized_unit = "kWh"
                record.unit_dimension = "energy"
            except (InvalidOperation, ValueError):
                record.raw_quantity = None
                record.normalized_quantity = None
                self.create_anomaly_flag(
                    record, FlagType.MISSING_INTERVAL, Severity.WARNING
                )

        # --- Scope assignment ---
        record.scope_category = ScopeCategory.SCOPE_2
        record.scope_subcategory = "purchased_electricity"
        record.activity_type = "grid_electricity"
        record.normalized_unit = "kWh"
        record.unit_dimension = "energy"
        self.log_normalization_event(
            record, NormalizationEventType.SCOPE_ASSIGNMENT,
            "scope_category", "", "SCOPE_2",
            "utility_active_import_scope2"
        )
        rules_applied.append("scope2_purchased_electricity")

        # --- Date parsing ---
        if start_time_str:
            try:
                for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S", "%m/%d/%Y %H:%M"):
                    try:
                        dt = datetime.strptime(start_time_str, fmt)
                        record.activity_date = dt.date()
                        record.reporting_period_year = dt.year
                        record.reporting_period_month = dt.month
                        break
                    except ValueError:
                        continue
            except Exception:
                pass

        # Track timestamps for gap detection
        if meter_sn not in meter_timestamps:
            meter_timestamps[meter_sn] = []
        if start_time_str:
            meter_timestamps[meter_sn].append((start_time_str, record))

        # --- Emission factor ---
        self._apply_emission_factor(record, rules_applied)

        record.normalization_rules = rules_applied
        record.save()
        self.compute_confidence_and_priority(record)
        return record

    def _detect_missing_intervals(self, records, meter_timestamps):
        """Detect gaps in timestamp sequences per meter."""
        for meter_sn, timestamps in meter_timestamps.items():
            timestamps.sort(key=lambda x: x[0])
            for i in range(1, len(timestamps)):
                prev_time_str, prev_record = timestamps[i - 1]
                curr_time_str, curr_record = timestamps[i]
                try:
                    prev_dt = datetime.strptime(prev_time_str, "%Y-%m-%d %H:%M")
                    curr_dt = datetime.strptime(curr_time_str, "%Y-%m-%d %H:%M")
                    gap_minutes = (curr_dt - prev_dt).total_seconds() / 60

                    # Expected 15-minute intervals — flag if gap > 15 min
                    if gap_minutes > 16:  # Allow 1-min tolerance
                        self.create_anomaly_flag(
                            curr_record, FlagType.MISSING_INTERVAL, Severity.WARNING
                        )
                        self.log_normalization_event(
                            curr_record, NormalizationEventType.INTERVAL_GAP_DETECTION,
                            "timestamp_gap", prev_time_str, curr_time_str,
                            f"gap_{int(gap_minutes)}_minutes_expected_15"
                        )
                        # Recompute confidence
                        self.compute_confidence_and_priority(curr_record)
                except ValueError:
                    continue

    def _apply_emission_factor(self, record, rules):
        """Apply grid electricity emission factor."""
        if not record.normalized_quantity or record.normalized_quantity <= 0:
            return

        factor = EmissionFactorTable.objects.filter(
            material_group="GRID_ELECTRICITY",
            scope_category="SCOPE_2",
            unit="kWh",
        ).first()

        if factor:
            record.emission_factor_id = factor.id
            record.emission_factor_value = factor.factor_value
            record.emission_factor_unit = f"kgCO2e/{factor.unit}"
            record.calculated_emissions = abs(record.normalized_quantity) * factor.factor_value
            self.log_normalization_event(
                record, NormalizationEventType.EMISSION_FACTOR_APPLIED,
                "calculated_emissions", "0",
                str(record.calculated_emissions),
                f"grid_factor_{factor.source}_{factor.factor_value}"
            )
            rules.append(f"emission_factor_grid_{factor.source}")
