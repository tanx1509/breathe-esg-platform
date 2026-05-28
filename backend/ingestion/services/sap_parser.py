"""
SAP MM Flat File Parser — handles ALV-grid CSV exports (MB51 style).

Anomalies handled:
- Trailing minus: 500.00- → -500.00
- European number format: 1.500,50 → 1500.50
- Leading zero restoration: pad MATNR to 18 chars
- Multilingual headers: map DE → EN
- Duplicate header rows mid-file: detect and skip
- Movement type → scope assignment
- Missing cost_center on 201 → BLOCKING
- Cross-dimensional UoM → BLOCKING
- Virtual plant code (9999) → BLOCKING
"""
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation
from ingestion.models import ParseStatus, SourceType
from ingestion.services.base_parser import BaseParser
from normalization.models import (
    CanonicalActivityRecord,
    NormalizationEventType,
    ReviewStatus,
    ScopeCategory,
)
from review.models import FlagType, Severity, ResolutionStatus
from reference.models import PlantMaster, UoMSynonymMap, EmissionFactorTable


# Multilingual header mapping: German → canonical field names
HEADER_MAP = {
    # German headers
    "Buchungsdatum": "posting_date",
    "Belegdatum": "document_date",
    "Materialbeleg": "material_doc",
    "Material": "material_number",
    "Kurztext": "material_description",
    "Werks": "plant",
    "Lagerort": "storage_location",
    "Bewegungsart": "movement_type",
    "Menge": "quantity",
    "Meins": "unit",
    "Kostl": "cost_center",
    "LIFNR": "supplier",
    "Warengruppe": "material_group",
    # English headers (passthrough)
    "Posting Date": "posting_date",
    "Document Date": "document_date",
    "Material Document": "material_doc",
    "Material Number": "material_number",
    "Material Description": "material_description",
    "Plant": "plant",
    "Storage Location": "storage_location",
    "Movement Type": "movement_type",
    "Quantity": "quantity",
    "Unit": "unit",
    "Cost Center": "cost_center",
    "Supplier": "supplier",
    "Material Group": "material_group",
    # Also handle lowercase/mixed
    "MvT": "movement_type",
    "BUn": "unit",
    "Plnt": "plant",
}

# Movement type → scope mapping
MOVEMENT_SCOPE_MAP = {
    "201": {"scope": "SCOPE_1", "subcategory": "stationary_combustion", "activity": "fuel_combustion"},
    "261": {"scope": "SCOPE_1", "subcategory": "mobile_combustion", "activity": "fuel_combustion"},
    "101": {"scope": "SCOPE_3", "subcategory": "upstream_purchased_goods", "activity": "upstream_purchased_goods"},
    "102": {"scope": "SCOPE_3", "subcategory": "upstream_purchased_goods", "activity": "upstream_purchased_goods"},
    "122": {"scope": "SCOPE_3", "subcategory": "upstream_purchased_goods", "activity": "upstream_purchased_goods"},
    "551": {"scope": "SCOPE_3", "subcategory": "waste_generation", "activity": "waste_generation"},
    "301": {"scope": "SCOPE_3", "subcategory": "upstream_transport", "activity": "upstream_transport"},
    "311": {"scope": "SCOPE_3", "subcategory": "upstream_transport", "activity": "upstream_transport"},
}

# Fuel material groups (for scope 1 classification)
FUEL_MATERIAL_GROUPS = {"DIESEL", "PETROL", "LPG", "FURNACE_OIL", "NATURAL_GAS", "FUEL"}


class SAPParser(BaseParser):
    source_type = SourceType.SAP_MM

    def parse_and_normalize(self, rows, raw_uploads, job):
        records = []
        for i, (row, raw) in enumerate(zip(rows, raw_uploads)):
            # Detect and skip duplicate header rows
            if self._is_header_row(row):
                self.create_parsed_row(
                    raw, job, ParseStatus.FAILED,
                    errors=[{"field": "all", "raw_value": str(row), "error_type": "duplicate_header_row"}],
                    schema="SAP_MB51_DUPLICATE_HEADER",
                )
                continue

            # Map headers
            mapped = self._map_headers(row)
            locale = self._detect_locale(row)

            try:
                record = self._process_row(mapped, raw, job, locale)
                if record:
                    records.append(record)
                    self.create_parsed_row(
                        raw, job, ParseStatus.SUCCESS,
                        schema=f"SAP_MB51_{locale.upper().replace('-', '_')}",
                        locale=locale,
                        date_format="DD.MM.YYYY" if locale == "de-DE" else "YYYY-MM-DD",
                    )
                else:
                    self.create_parsed_row(
                        raw, job, ParseStatus.FAILED,
                        errors=[{"field": "processing", "raw_value": "", "error_type": "row_excluded"}],
                        schema=f"SAP_MB51_{locale.upper().replace('-', '_')}",
                        locale=locale,
                    )
            except Exception as e:
                self.create_parsed_row(
                    raw, job, ParseStatus.FAILED,
                    errors=[{"field": "processing", "raw_value": str(e), "error_type": "parse_exception"}],
                )
        return records

    def _is_header_row(self, row):
        """Detect duplicate header rows mid-file."""
        values = list(row.values())
        header_indicators = {"Buchungsdatum", "Posting Date", "Material", "Werks", "Plant", "Menge", "Quantity"}
        return any(v in header_indicators for v in values if v)

    def _map_headers(self, row):
        """Map multilingual headers to canonical field names."""
        mapped = {}
        for key, value in row.items():
            canonical = HEADER_MAP.get(key.strip(), key.strip().lower().replace(" ", "_"))
            mapped[canonical] = value.strip() if value else ""
        return mapped

    def _detect_locale(self, row):
        """Detect locale from header names or number formats."""
        keys = set(row.keys())
        german_headers = {"Buchungsdatum", "Werks", "Menge", "Meins", "Kostl", "Warengruppe"}
        if keys & german_headers:
            return "de-DE"
        return "en-US"

    def _process_row(self, mapped, raw, job, locale):
        """Process a single mapped row into a CanonicalActivityRecord."""
        # Extract raw quantity string
        raw_qty_str = mapped.get("quantity", "")
        raw_unit_str = mapped.get("unit", "")
        movement_type = mapped.get("movement_type", "")
        plant_code = mapped.get("plant", "")
        cost_center = mapped.get("cost_center", "")
        material_number = mapped.get("material_number", "")
        material_desc = mapped.get("material_description", "")
        material_group = mapped.get("material_group", "")
        supplier = mapped.get("supplier", "")
        material_doc = mapped.get("material_doc", "")
        posting_date_str = mapped.get("posting_date", "")

        # Skip if no movement type (empty row)
        if not movement_type:
            return None

        # Create canonical record
        record = CanonicalActivityRecord.objects.create(
            tenant=self.tenant,
            raw=raw,
            job=job,
            source_type=SourceType.SAP_MM,
            source_document_ref=material_doc,
            raw_quantity_string=raw_qty_str,
            raw_unit=raw_unit_str,
            facility_id=plant_code,
            cost_center=cost_center,
            supplier_id=supplier,
            material_group=material_group.upper() if material_group else "",
            immutable_hash=raw.immutable_hash,
            source_metadata={
                "movement_type": movement_type,
                "material_number": material_number,
                "material_description": material_desc,
                "storage_location": mapped.get("storage_location", ""),
                "locale_detected": locale,
            },
        )

        rules_applied = []

        # --- Normalization: Trailing minus ---
        quantity = self._handle_trailing_minus(record, raw_qty_str, rules_applied)

        # --- Normalization: European number format ---
        if quantity is None:
            quantity = self._handle_european_format(record, raw_qty_str, locale, rules_applied)

        # --- Normalization: Standard number parse ---
        if quantity is None:
            try:
                quantity = Decimal(raw_qty_str.replace(",", ""))
            except (InvalidOperation, ValueError):
                quantity = None

        if quantity is not None:
            record.raw_quantity = quantity
            record.normalized_quantity = abs(quantity)

        # --- Normalization: Leading zero restoration ---
        self._handle_leading_zeros(record, material_number, rules_applied)

        # --- Normalization: Unit mapping ---
        self._handle_unit_normalization(record, raw_unit_str, locale, material_group, rules_applied)

        # --- Normalization: Movement type → scope assignment ---
        self._handle_scope_assignment(record, movement_type, material_group, rules_applied)

        # --- Normalization: Date parsing ---
        self._handle_date_parsing(record, posting_date_str, locale, rules_applied)

        # --- Anomaly detection ---
        self._detect_anomalies(record, movement_type, plant_code, cost_center,
                                raw_unit_str, material_group, material_number, supplier)

        # --- Emission factor lookup ---
        self._apply_emission_factor(record, rules_applied)

        # Store normalization rules
        record.normalization_rules = rules_applied
        record.save()

        # Compute confidence score
        self.compute_confidence_and_priority(record)

        return record

    def _handle_trailing_minus(self, record, raw_qty_str, rules):
        """Handle SAP trailing minus: 500.00- → -500.00"""
        pattern = re.compile(r'^([\d.,]+)-$')
        match = pattern.match(raw_qty_str.strip())
        if match:
            number_part = match.group(1).replace(",", "")
            try:
                value = -Decimal(number_part)
                self.log_normalization_event(
                    record, NormalizationEventType.LEXICAL_CAST,
                    "raw_quantity", raw_qty_str, str(value),
                    "trailing_minus_regex"
                )
                self.create_anomaly_flag(
                    record, FlagType.TRAILING_MINUS, Severity.INFO, auto_resolvable=True
                )
                # Auto-resolve the INFO flag
                flag = record.anomaly_flag_records.filter(flag_type=FlagType.TRAILING_MINUS).first()
                if flag:
                    flag.resolution_status = ResolutionStatus.AUTO_RESOLVED
                    flag.resolution_note = "Trailing minus automatically converted to negative value"
                    flag.save()
                rules.append("trailing_minus_cast")
                return value
            except (InvalidOperation, ValueError):
                pass
        return None

    def _handle_european_format(self, record, raw_qty_str, locale, rules):
        """Handle European number format: 1.500,50 → 1500.50"""
        # Pattern: digits with dots as thousands separators and comma as decimal
        pattern = re.compile(r'^-?([\d.]+),(\d+)$')
        clean = raw_qty_str.strip().lstrip("-")
        match = pattern.match(raw_qty_str.strip())
        if match or (locale == "de-DE" and "," in raw_qty_str):
            try:
                is_negative = raw_qty_str.strip().startswith("-")
                # Remove thousand separators (dots), replace decimal comma with dot
                normalized = raw_qty_str.strip().lstrip("-")
                normalized = normalized.replace(".", "").replace(",", ".")
                value = Decimal(normalized)
                if is_negative:
                    value = -value
                self.log_normalization_event(
                    record, NormalizationEventType.LOCALE_PARSE,
                    "raw_quantity", raw_qty_str, str(value),
                    "european_number_format_de-DE"
                )
                self.create_anomaly_flag(
                    record, FlagType.EUROPEAN_NUMBER_FORMAT, Severity.INFO, auto_resolvable=True
                )
                flag = record.anomaly_flag_records.filter(flag_type=FlagType.EUROPEAN_NUMBER_FORMAT).first()
                if flag:
                    flag.resolution_status = ResolutionStatus.AUTO_RESOLVED
                    flag.resolution_note = "European number format auto-normalized"
                    flag.save()
                rules.append("european_number_format_normalized")
                return value
            except (InvalidOperation, ValueError):
                pass
        return None

    def _handle_leading_zeros(self, record, material_number, rules):
        """Restore leading zeros on material numbers — pad MATNR to 18 chars."""
        if material_number and len(material_number) < 18:
            original = material_number
            padded = material_number.zfill(18)
            record.source_metadata["material_number_original"] = original
            record.source_metadata["material_number_padded"] = padded
            self.log_normalization_event(
                record, NormalizationEventType.LEADING_ZERO_RESTORE,
                "material_number", original, padded,
                "leading_zero_restore_18char"
            )
            rules.append("leading_zero_restore_18char")

    def _handle_unit_normalization(self, record, raw_unit, locale, material_group, rules):
        """Normalize units using UoMSynonymMap."""
        lang = "DE" if locale == "de-DE" else "EN"
        uom = UoMSynonymMap.objects.filter(
            internal_code=raw_unit.upper(), language_key=lang
        ).first()

        if not uom:
            # Try with the other language
            uom = UoMSynonymMap.objects.filter(internal_code=raw_unit.upper()).first()

        if uom:
            record.normalized_unit = uom.base_unit
            record.unit_dimension = uom.dimension
            if uom.conversion_factor != 1 and record.normalized_quantity:
                original_qty = record.normalized_quantity
                record.normalized_quantity = record.normalized_quantity * uom.conversion_factor
                self.log_normalization_event(
                    record, NormalizationEventType.UOM_NORMALIZATION,
                    "normalized_quantity", str(original_qty),
                    str(record.normalized_quantity),
                    f"{raw_unit}_to_{uom.base_unit}_factor_{uom.conversion_factor}"
                )
                rules.append(f"uom_{raw_unit}_to_{uom.base_unit}")
        else:
            record.normalized_unit = raw_unit
            record.unit_dimension = "unknown"

    def _handle_scope_assignment(self, record, movement_type, material_group, rules):
        """Assign scope based on movement type and material group."""
        scope_info = MOVEMENT_SCOPE_MAP.get(str(movement_type))
        if scope_info:
            record.scope_category = scope_info["scope"]
            record.scope_subcategory = scope_info["subcategory"]
            record.activity_type = scope_info["activity"]

            # For 201/261, check if it's a fuel material
            if movement_type in ("201", "261"):
                mg_upper = (material_group or "").upper()
                if mg_upper in FUEL_MATERIAL_GROUPS:
                    record.scope_category = ScopeCategory.SCOPE_1
                    record.scope_subcategory = "stationary_combustion"
                    record.activity_type = "fuel_combustion"

            self.log_normalization_event(
                record, NormalizationEventType.SCOPE_ASSIGNMENT,
                "scope_category", "", record.scope_category,
                f"movement_type_{movement_type}_scope_assignment"
            )
            rules.append(f"movement_type_{movement_type}_scope_assignment")

            # GHG Protocol category for Scope 3
            if record.scope_category == ScopeCategory.SCOPE_3:
                ghg_map = {
                    "upstream_purchased_goods": "Category 1",
                    "waste_generation": "Category 5",
                    "upstream_transport": "Category 4",
                }
                record.ghg_protocol_category = ghg_map.get(record.scope_subcategory, "")

    def _handle_date_parsing(self, record, date_str, locale, rules):
        """Parse posting date based on detected locale."""
        if not date_str:
            return

        formats = [
            ("%d.%m.%Y", "DD.MM.YYYY"),
            ("%Y-%m-%d", "YYYY-MM-DD"),
            ("%m/%d/%Y", "MM/DD/YYYY"),
            ("%d/%m/%Y", "DD/MM/YYYY"),
        ]

        for fmt, label in formats:
            try:
                parsed = datetime.strptime(date_str.strip(), fmt).date()
                record.activity_date = parsed
                record.reporting_period_year = parsed.year
                record.reporting_period_month = parsed.month
                return
            except ValueError:
                continue

    def _detect_anomalies(self, record, movement_type, plant_code, cost_center,
                           raw_unit, material_group, material_number, supplier):
        """Detect and flag anomalies."""

        # Missing cost center on 201 movement (Scope 1 consumption)
        if movement_type in ("201", "261") and not cost_center:
            self.create_anomaly_flag(
                record, FlagType.MISSING_COST_CENTER, Severity.BLOCKING
            )

        # Virtual plant code
        try:
            plant = PlantMaster.objects.get(plant_id=plant_code, tenant=self.tenant)
            if plant.is_virtual:
                self.create_anomaly_flag(
                    record, FlagType.VIRTUAL_PLANT_CODE, Severity.BLOCKING
                )
        except PlantMaster.DoesNotExist:
            if plant_code:
                self.create_anomaly_flag(
                    record, FlagType.VIRTUAL_PLANT_CODE, Severity.BLOCKING
                )

        # Cross-dimensional UoM: KG for a fuel material that should be in liters
        if raw_unit.upper() == "KG" and (material_group or "").upper() in FUEL_MATERIAL_GROUPS:
            self.create_anomaly_flag(
                record, FlagType.CROSS_DIMENSIONAL_UOM, Severity.BLOCKING
            )

        # Orphaned material (leading zeros couldn't restore to known material)
        if material_number and len(material_number) < 10:
            self.create_anomaly_flag(
                record, FlagType.ORPHANED_MATERIAL, Severity.WARNING
            )

        # Missing supplier on reversal movement
        if movement_type in ("102", "122") and not supplier:
            self.create_anomaly_flag(
                record, FlagType.MISSING_SUPPLIER_ON_REVERSAL, Severity.WARNING
            )

        # 301/311 transport movements require review
        if movement_type in ("301", "311"):
            record.requires_human_review = True

    def _apply_emission_factor(self, record, rules):
        """Look up and apply emission factor."""
        if not record.material_group or not record.normalized_quantity:
            return

        factor = EmissionFactorTable.objects.filter(
            material_group=record.material_group,
            scope_category=record.scope_category,
            unit=record.normalized_unit,
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
                f"factor_{factor.source}_{factor.factor_value}"
            )
            rules.append(f"emission_factor_{factor.material_group}_{factor.source}")
