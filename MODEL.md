# MODEL.md — ESG Activity Ingestion & Analyst Review Platform

---

## Philosophy

This data model exists to answer one question under audit:

> *"How did this emissions figure get here, and can you prove every transformation that touched it?"*

Everything else is downstream of that.

The model is not organized around emissions. It is organized around **activity records** — the physical events that generate emissions. Emissions are derived values. Activity records are ground truth. This distinction matters because:

- Emission factors change retroactively (regulatory updates, methodology revisions)
- Auditors verify physical quantities, not carbon math
- Reversal events (SAP movement type 102, 122) net against physical quantities, not against emission totals

The architecture has three non-negotiable properties:

1. **Raw data is immutable.** Source payloads are never mutated after ingestion. Transformations live in a separate layer with their own audit trail.
2. **Every transformation is attributed.** Each normalization step records what changed, why, which rule was applied, and whether a human was involved.
3. **Review and approval are first-class entities.** Analyst decisions are not status flags on a record. They are events with actors, timestamps, and notes — because assurance providers will ask who approved what and when.

---

## Why Activity-Centric, Not Emission-Centric

Most ESG data models make `EmissionRecord` the core primitive. This is wrong for four operational reasons:

**1. Emission factors change retroactively.** DEFRA publishes updated conversion factors annually. If your core entity stores a calculated emission value, a factor update requires touching every historical record. If your core entity stores the physical activity (500 L of diesel consumed), recalculation is a read-only query against unchanged source data. The activity record never moves; the factor table updates.

**2. Methodology versioning.** GHG Protocol methodology revisions, shifts from location-based to market-based Scope 2 accounting, and CSRD-mandated factor changes all require the ability to re-derive emissions from original physical quantities. Without immutable activity records, this is impossible without keeping parallel ledgers.

**3. Auditor traceability.** Assurance providers do not verify carbon math in isolation. They verify the physical reality behind it — fuel invoices, meter readings, boarding passes. Their sampling unit is the physical event, not the derived emission. A system organized around activity records can satisfy this in a single lookup. A system organized around emission records requires reconstructing the source chain.

**4. Reversal and netting semantics.** SAP movement type 102 negates a 101. A canceled flight ticket negates a booked one. These are physical inventory events with sign semantics. Netting them correctly at the activity level before computing emissions prevents double-counting. Trying to manage net emissions by creating negative emission records is fragile and audit-unfriendly.

---

## Entity Overview

```
Tenant
  └── IngestionJob
        └── RawUpload (immutable)
              └── ParsedRow
                    └── CanonicalActivityRecord
                          ├── NormalizationEvent (append-only log)
                          ├── AnomalyFlag (per-record flags)
                          └── ReviewEvent (append-only log)
                                └── AuditLock (immutable on approval)

Supporting reference tables:
  PlantMaster, CostCenterMaster, MaterialGroupMap,
  UoMSynonymMap, EmissionFactorTable, AirportReferenceTable
```

---

## Entity Definitions

### 1. Tenant

**Why it exists:** Enterprise ESG platforms are multi-tenant by nature. A consulting firm onboarding multiple corporate clients, or a parent company managing subsidiaries with separate reporting boundaries, cannot share canonical records. Every query is scoped to a tenant.

```
tenant_id          UUID (PK)
name               VARCHAR(255)
reporting_currency VARCHAR(3)        -- ISO 4217, e.g. INR, USD
fiscal_year_start  DATE              -- carbon reporting year boundary
created_at         TIMESTAMP
```

The `fiscal_year_start` field exists because GHG accounting must align with the client's financial year. A company with a March 31 fiscal year end needs interval records sliced at that boundary, not at December 31.

---

### 2. IngestionJob

**Why it exists:** A single CSV upload is not a row-level event. It is a job with a lifecycle. Jobs can partially succeed. Analysts need to know: what batch did this row arrive in, who triggered it, and did the parser encounter errors. Without this entity, there is no way to re-run failed jobs without duplicating records.

```
job_id             UUID (PK)
tenant_id          UUID (FK → Tenant)
source_type        ENUM(SAP_MM, UTILITY_INTERVAL, TRAVEL_CONCUR)
triggered_by       UUID (FK → User)
triggered_at       TIMESTAMP
file_name          VARCHAR(512)
file_hash          VARCHAR(64)       -- SHA-256 of raw uploaded bytes
status             ENUM(QUEUED, PARSING, NORMALIZED, FAILED, COMPLETE)
total_rows         INTEGER
parsed_rows        INTEGER
failed_rows        INTEGER
suspicious_rows    INTEGER
completed_at       TIMESTAMP
```

`file_hash` prevents duplicate uploads of the same file. If the same export is uploaded twice — a common operational accident — the second job is rejected at the hash check before any parsing occurs.

---

### 3. RawUpload

**Why it exists:** The single most important architectural decision in this system. Raw source payloads are stored verbatim and never modified. When an auditor asks "what did the SAP system actually send you?", the answer must be retrievable without reconstruction.

This is not an academic consideration. CSRD assurance providers and Big 4 auditors routinely request original source files during fieldwork. If the system only stores normalized records, you cannot satisfy this request.

```
raw_id             UUID (PK)
job_id             UUID (FK → IngestionJob)
tenant_id          UUID (FK → Tenant)
row_number         INTEGER           -- original line number in source file
raw_payload        JSONB             -- verbatim key-value pairs as extracted
received_at        TIMESTAMP
immutable_hash     VARCHAR(64)       -- SHA-256 of raw_payload JSON string
```

`immutable_hash` creates a cryptographic fingerprint of the source row at ingestion time. If the canonical record is later disputed, you can prove the raw source was never altered by recomputing the hash.

---

### 4. ParsedRow

**Why it exists:** Parsing is distinct from normalization. Parsing is the structural step — detecting the header row, splitting delimiters, casting types. Normalization is the semantic step — converting units, restoring leading zeros, mapping movement types to scopes. These two layers fail for different reasons and require separate error handling.

A ParsedRow can exist even when parsing partially fails (e.g., a row where date parsing succeeded but quantity casting failed). This allows the analyst to see exactly which field broke.

```
parsed_id          UUID (PK)
raw_id             UUID (FK → RawUpload)
job_id             UUID (FK → IngestionJob)
parse_status       ENUM(SUCCESS, PARTIAL, FAILED)
parse_errors       JSONB             -- array of {field, raw_value, error_type}
detected_schema    VARCHAR(100)      -- e.g. "SAP_MB51_DE_LOCALE"
locale_detected    VARCHAR(10)       -- e.g. "de-DE", "en-US"
date_format_inferred VARCHAR(30)     -- e.g. "DD.MM.YYYY", "MM/DD/YYYY"
parsed_at          TIMESTAMP
```

`detected_schema` and `locale_detected` are set by the Lexical Normalization Engine. They explain *why* the parser interpreted the row the way it did — critical for German-locale SAP exports where "Buchungsdatum" replaces "Posting Date" and "1.250,50" means 1250.50.

---

### 5. CanonicalActivityRecord

**Why it exists:** This is the system's heart. Every ingested row — regardless of whether it came from SAP, a utility CSV, or a Concur export — eventually resolves to a single canonical record in this table. This is the record that analysts review, that emission calculations run against, and that gets audit-locked.

The schema is deliberately source-agnostic. Source-specific fields that don't generalize live in `source_metadata` as JSONB.

```
record_id              UUID (PK)
tenant_id              UUID (FK → Tenant)
raw_id                 UUID (FK → RawUpload)
job_id                 UUID (FK → IngestionJob)

-- Source classification
source_type            ENUM(SAP_MM, UTILITY_INTERVAL, TRAVEL_CONCUR)
source_document_ref    VARCHAR(255)   -- e.g. SAP material doc number, booking locator
activity_type          VARCHAR(100)   -- e.g. "fuel_combustion", "grid_electricity", "air_travel"

-- Scope classification
scope_category         ENUM(SCOPE_1, SCOPE_2, SCOPE_3)
scope_subcategory      VARCHAR(100)   -- e.g. "stationary_combustion", "purchased_electricity",
                                     --      "upstream_purchased_goods", "business_travel"
ghg_protocol_category  VARCHAR(100)   -- GHG Protocol Category 1-15 for Scope 3

-- Temporal
activity_date          DATE           -- normalized to fiscal calendar
reporting_period_year  INTEGER
reporting_period_month INTEGER

-- Physical quantity (raw, preserved verbatim)
raw_quantity           NUMERIC(20, 6)
raw_unit               VARCHAR(20)    -- exactly as it appeared in source
raw_quantity_string    VARCHAR(50)    -- the original string, e.g. "500.00-" or "1.500,50"

-- Physical quantity (normalized)
normalized_quantity    NUMERIC(20, 6)
normalized_unit        VARCHAR(20)    -- ISO standard unit, e.g. "L", "kWh", "km"
unit_dimension         VARCHAR(20)    -- "volume", "mass", "energy", "distance"

-- Emission calculation
emission_factor_id     UUID (FK → EmissionFactorTable, nullable)
emission_factor_value  NUMERIC(20, 8)
emission_factor_unit   VARCHAR(50)    -- e.g. "kgCO2e/L"
calculated_emissions   NUMERIC(20, 6) -- in kgCO2e
emissions_locked       BOOLEAN        -- false until audit-locked

-- Organizational context (SAP-specific fields generalized)
facility_id            VARCHAR(100)   -- SAP plant code, meter account, entity name
cost_center            VARCHAR(50)    -- nullable; required for Scope 1 SAP records
supplier_id            VARCHAR(100)   -- nullable; SAP LIFNR, vendor, airline code
material_group         VARCHAR(50)    -- SAP MATKL or equivalent

-- Trust and quality
confidence_score       NUMERIC(4, 3)  -- 0.000 to 1.000, computed deterministically (see scoring table below)
review_priority        ENUM(LOW, MEDIUM, HIGH, CRITICAL)  -- derived from score bands
anomaly_flags          JSONB          -- array of AnomalyFlag.flag_id references
normalization_rules    JSONB          -- ordered array of applied rule identifiers, e.g.:
                                     -- ["trailing_minus_cast", "GAL_to_L",
                                     --  "leading_zero_restore_18char",
                                     --  "movement_type_201_scope1_assignment"]
requires_human_review  BOOLEAN        -- true if any BLOCKING anomaly is unresolved
review_status          ENUM(PENDING, UNDER_REVIEW, APPROVED, REJECTED, AUDIT_LOCKED)

-- Provenance
immutable_hash         VARCHAR(64)    -- SHA-256 of raw_payload at ingestion
approved_by            UUID (FK → User, nullable)
approved_at            TIMESTAMP (nullable)
audit_locked_at        TIMESTAMP (nullable)

-- Overflow
source_metadata        JSONB          -- source-specific fields that don't generalize
created_at             TIMESTAMP
updated_at             TIMESTAMP
```

**Key design decisions in this table:**

`raw_quantity_string` exists specifically to preserve "500.00-" and "1.500,50" before any casting occurs. If a normalization rule is later found to be wrong, the original string is still there.

`normalization_rules` as an ordered JSON array means every canonical record carries its own transformation recipe. When an auditor samples row 10 (Furnace Oil in KG), they can read: `["KG_to_L_density_override_0.850", "manual_density_approved_by:analyst@company.com"]` directly on the record.

**Confidence Score — deterministic computation, not a magic number:**

| Deduction trigger | Score penalty |
|---|---|
| Base score | 1.000 |
| Missing `cost_center` on a 201 movement | −0.30 |
| Cross-dimensional UoM (mass ↔ volume without density rule) | −0.50 |
| Unresolvable leading-zero truncation (orphaned material) | −0.40 |
| Virtual or unknown plant code | −0.35 |
| Missing supplier on a reversal movement | −0.20 |
| European number format detected and auto-resolved | −0.05 (INFO only) |
| Estimated meter read (utility interval) | −0.10 |
| Missing airport code or distance (travel) | −0.25 |
| Canceled/voided ticket present | −0.40 |

Score → priority bands: ≥ 0.85 = LOW (auto-approvable queue), 0.60–0.84 = MEDIUM, 0.35–0.59 = HIGH, < 0.35 = CRITICAL (blocked until analyst resolves).

**JSONB usage rationale:** Five fields use JSONB (`anomaly_flags`, `normalization_rules`, `source_metadata`, `parse_errors`, `fields_edited`). This is a deliberate choice, not schema avoidance. The alternatives are: (a) sparse nullable columns for every possible flag/rule — creates a table with 40+ mostly-null columns, and adding a new rule type requires a migration; or (b) a strict relational join for every flag lookup — adds query complexity for what is essentially a read-heavy display operation. JSONB here is an overflow container for high-cardinality, evolving, source-specific attributes. The core queryable fields (scope, status, confidence, date) remain typed columns. This boundary is intentional.

`review_status` is a state machine: PENDING → UNDER_REVIEW → APPROVED → AUDIT_LOCKED. The AUDIT_LOCKED state is terminal and irreversible at the application layer. Corrections to locked records require a new record with a `supersedes_record_id` reference back to the locked one — the original is never mutated.

---

## Canonical Record Contract

A `CanonicalActivityRecord` is the **only** entity consumed by downstream emissions logic, analyst review queues, and reporting aggregations. No downstream system reads `RawUpload`, `ParsedRow`, or `NormalizationEvent` directly.

**A record is considered processable iff all of the following hold:**

1. `raw_id` resolves to an existing, hash-verified `RawUpload`
2. `normalized_quantity` is non-null and non-zero
3. `normalized_unit` maps to a known entry in `UoMSynonymMap`
4. `activity_date` is non-null and falls within a valid reporting period
5. `scope_category` has been assigned (SCOPE_1, SCOPE_2, or SCOPE_3)
6. `review_status` ≠ REJECTED

**A record is considered audit-ready iff additionally:**

7. `review_status` = APPROVED or AUDIT_LOCKED
8. All `AnomalyFlag` entries for this record are in `resolution_status` ≠ OPEN
9. `emission_factor_id` resolves to a non-expired `EmissionFactorTable` entry
10. `calculated_emissions` is non-null

Records that satisfy conditions 1–5 but fail 6 are invisible to reporting. Records that satisfy 1–6 but fail 7–10 appear in the analyst queue. Records that satisfy all 10 conditions are included in period totals and can be locked.

---

### 6. NormalizationEvent

**Why it exists:** `normalization_rules` on the canonical record tells you *what* happened. `NormalizationEvent` tells you *when*, *by what system*, and *exactly what the before/after values were*. This is the transformation audit trail.

This table is append-only. No updates. No deletes.

```
event_id           UUID (PK)
record_id          UUID (FK → CanonicalActivityRecord)
tenant_id          UUID (FK → Tenant)
event_type         ENUM(LEXICAL_CAST, UOM_NORMALIZATION, LEADING_ZERO_RESTORE,
                        LOCALE_PARSE, MOVEMENT_TYPE_CLASSIFICATION,
                        DENSITY_CONVERSION_MANUAL, SCOPE_ASSIGNMENT,
                        EMISSION_FACTOR_APPLIED, MANUAL_CORRECTION)
field_name         VARCHAR(100)   -- which field was transformed
before_value       TEXT           -- original value as string
after_value        TEXT           -- transformed value as string
rule_applied       VARCHAR(255)   -- e.g. "trailing_minus_regex", "T006A_ST_to_EA"
applied_by         ENUM(SYSTEM, ANALYST)
applied_by_user    UUID (nullable, FK → User)
applied_at         TIMESTAMP
notes              TEXT           -- required when applied_by = ANALYST
```

**Why this is valuable under audit:** If an assurance provider asks "how did 500.00- become -500.00?", the answer is: query `NormalizationEvent` where `record_id = X` and `event_type = LEXICAL_CAST`. You get: before = "500.00-", after = "-500.00", rule = "trailing_minus_regex", applied_by = SYSTEM, applied_at = timestamp. That is a defensible, timestamped transformation log.

---

### 7. AnomalyFlag

**Why it exists:** Not all anomalies are equal. Some can be resolved automatically with high confidence (duplicate timestamp → drop null row). Others require mandatory human review (cross-dimensional UoM, missing cost center on Scope 1 record, virtual plant code with no geography). The flag table separates detection from resolution, allowing analysts to prioritize their queue by severity.

```
flag_id            UUID (PK)
record_id          UUID (FK → CanonicalActivityRecord)
tenant_id          UUID (FK → Tenant)
flag_type          ENUM(
                     MISSING_COST_CENTER,
                     CROSS_DIMENSIONAL_UOM,
                     LEADING_ZERO_TRUNCATION,
                     TRAILING_MINUS,
                     MULTILINGUAL_HEADER_DETECTED,
                     DUPLICATE_TIMESTAMP,
                     MISSING_INTERVAL,
                     UNIT_SHIFT_MWH,
                     ACTIVE_EXPORT_DETECTED,
                     REACTIVE_POWER_EXCLUDED,
                     CANCELED_TICKET,
                     DUPLICATE_SEGMENT,
                     MISSING_AIRPORT_CODE,
                     MISSING_DISTANCE,
                     AMBIGUOUS_TRAVEL_CATEGORY,
                     ORPHANED_MATERIAL,
                     VIRTUAL_PLANT_CODE,
                     MISSING_SUPPLIER_ON_REVERSAL,
                     BLANK_MATERIAL_DESCRIPTION,
                     EUROPEAN_NUMBER_FORMAT
                   )
severity           ENUM(INFO, WARNING, BLOCKING)
auto_resolvable    BOOLEAN
resolution_status  ENUM(OPEN, AUTO_RESOLVED, ANALYST_RESOLVED, WAIVED)
resolution_note    TEXT
resolved_by        UUID (nullable, FK → User)
resolved_at        TIMESTAMP
detected_at        TIMESTAMP
```

`severity = BLOCKING` means the record cannot move to APPROVED status until an analyst explicitly resolves the flag. This is the gate for:
- `CROSS_DIMENSIONAL_UOM` (KG → L requires density evidence)
- `MISSING_COST_CENTER` on a 201 movement (Scope 1 cannot be unallocated)
- `VIRTUAL_PLANT_CODE` (no geography means no emission factor)

`severity = WARNING` means the record can be approved but the flag must be acknowledged.

`severity = INFO` is logged for traceability but does not require action (e.g., `TRAILING_MINUS` auto-resolved by the lexical engine).

---

### 8. ReviewEvent

**Why it exists:** Same reason as NormalizationEvent — analyst decisions must be events, not status fields. When an auditor asks "who approved this record?", the answer should include not just the person but the timestamp, the review notes, and the state transition. A `reviewed_by` column on the canonical record does not provide this.

This table is append-only.

```
review_id          UUID (PK)
record_id          UUID (FK → CanonicalActivityRecord)
tenant_id          UUID (FK → Tenant)
action             ENUM(CLAIM, APPROVE, REJECT, REQUEST_MORE_INFO,
                        EDIT_AND_APPROVE, ESCALATE, WAIVE_FLAG)
previous_status    ENUM(PENDING, UNDER_REVIEW, APPROVED, REJECTED)
new_status         ENUM(PENDING, UNDER_REVIEW, APPROVED, REJECTED, AUDIT_LOCKED)
performed_by       UUID (FK → User)
performed_at       TIMESTAMP
notes              TEXT           -- mandatory for REJECT, EDIT_AND_APPROVE, WAIVE_FLAG
fields_edited      JSONB          -- nullable; for EDIT_AND_APPROVE, records which fields
                                 -- were changed and why
```

---

### 9. AuditLock

**Why it exists:** APPROVED status is reversible at the application layer — an analyst can un-approve a record if they made a mistake. AUDIT_LOCKED is not. Once a reporting period is closed and submitted to auditors, the records must be frozen. `AuditLock` is the immutable record of that freeze event.

```
lock_id            UUID (PK)
tenant_id          UUID (FK → Tenant)
reporting_period   VARCHAR(20)    -- e.g. "FY2025", "FY2025-Q1"
locked_by          UUID (FK → User)
locked_at          TIMESTAMP
record_count       INTEGER        -- how many records were locked in this batch
total_emissions    NUMERIC(20, 6) -- sum of calculated_emissions at lock time (kgCO2e)
lock_hash          VARCHAR(64)    -- SHA-256 of all record immutable_hashes in sorted order
                                 -- allows future verification that locked set is unchanged
notes              TEXT
```

`lock_hash` is the system's tamper-evidence mechanism. By hashing all individual record hashes in sorted order, it creates a single fingerprint of the entire locked dataset. If any record in the locked set were modified at the database level, the lock hash would no longer match. Auditors can request this hash and re-verify it independently.

---

## Reference Tables

### PlantMaster

Maps SAP plant codes to geographic reality. Required because emission factor selection for Scope 2 electricity depends on the power grid of the physical location, and Scope 1 regional fuel standards vary by jurisdiction.

```
plant_id           VARCHAR(20)    -- SAP WERKS value
tenant_id          UUID (FK → Tenant)
plant_name         VARCHAR(255)
country            VARCHAR(3)     -- ISO 3166-1 alpha-3
state_province     VARCHAR(100)
city               VARCHAR(100)
latitude           NUMERIC(9, 6)
longitude          NUMERIC(9, 6)
grid_emission_factor NUMERIC(10, 6) -- kgCO2e/kWh for Scope 2
is_virtual         BOOLEAN        -- true for placeholder codes like 9999
```

### UoMSynonymMap

Simulates the T006 / T006A / T006I chain from SAP. Maps localized internal codes to ISO standards.

```
internal_code      VARCHAR(10)    -- e.g. "ST", "KL", "GAL"
language_key       VARCHAR(2)     -- e.g. "DE", "EN"
iso_code           VARCHAR(10)    -- e.g. "EA", "K6", "GLL"
dimension          VARCHAR(20)    -- "count", "volume", "mass", "energy"
base_unit          VARCHAR(10)    -- SI base unit for this dimension
conversion_factor  NUMERIC(20, 10) -- multiplier to convert to base unit
```

This table is the reason the parser does not hardcode unit mappings. "ST" → "EA" because `language_key = DE` and `dimension = count`. "KL" → "L" because `conversion_factor = 1000`.

### EmissionFactorTable

```
factor_id          UUID (PK)
tenant_id          UUID (FK → Tenant, nullable for global factors)
material_group     VARCHAR(50)    -- SAP MATKL or canonical activity category
scope_category     ENUM(SCOPE_1, SCOPE_2, SCOPE_3)
activity_type      VARCHAR(100)
unit               VARCHAR(20)    -- denominator unit, e.g. "L", "kWh", "km"
factor_value       NUMERIC(20, 8) -- kgCO2e per unit
source             VARCHAR(255)   -- e.g. "DEFRA 2024", "IEA 2024", "Ecoinvent 3.10"
valid_from         DATE
valid_to           DATE (nullable)
```

### AirportReferenceTable

Required for travel enrichment. When a Concur row has origin = "DEL" and destination = "BOM", the pipeline needs to compute great-circle distance without calling an external API at ingestion time.

```
iata_code          VARCHAR(3) (PK)
airport_name       VARCHAR(255)
city               VARCHAR(100)
country            VARCHAR(3)     -- ISO 3166-1 alpha-3
latitude           NUMERIC(9, 6)
longitude          NUMERIC(9, 6)
is_city_code       BOOLEAN        -- true for city codes (BJS, NYC) that map to multiple airports
```

Distance between two airports is computed as Haversine great-circle distance from coordinates. No external API required. When `is_city_code = TRUE`, the record is flagged `AMBIGUOUS_AIRPORT` and routed to analyst review, because a city code (NYC) could resolve to JFK, EWR, or LGA.

---

## Ingestion Lifecycle

```
RAW_UPLOADED
    │
    ▼
PARSING
    ├── PARSE_FAILED ──────────────────────────────► (analyst sees in failed queue)
    │
    ▼
PARSED
    │
    ▼
NORMALIZING
    ├── NORMALIZATION_BLOCKED ─────────────────────► (blocking anomaly, e.g. KG→L)
    │
    ▼
NORMALIZED
    │
    ├── confidence_score ≥ 0.85, no BLOCKING flags ──► PENDING (auto-approvable queue)
    └── confidence_score < 0.85 or BLOCKING flags ───► FLAGGED (analyst review queue)
                                                            │
                                                            ▼
                                                      UNDER_REVIEW
                                                            │
                                               ┌────────────┴────────────┐
                                               ▼                         ▼
                                           APPROVED                  REJECTED
                                               │
                                               ▼
                                         AUDIT_LOCKED (terminal)
```

State transitions are validated at the application layer. A record cannot move from PENDING to AUDIT_LOCKED without passing through APPROVED. A record with an unresolved BLOCKING flag cannot reach APPROVED.

---

## Multi-Tenancy

All tables except reference tables carry `tenant_id`. All queries are filtered by `tenant_id` at the repository layer, not the application layer. This prevents accidental cross-tenant data leakage if application-layer filtering is bypassed.

Shared reference tables (AirportReferenceTable, global EmissionFactorTable rows) use `tenant_id = NULL` as a convention meaning "global". Tenant-specific overrides use the tenant's UUID.

---

## Scope Classification Logic

Scope is not inferred from free text. It is determined by a deterministic rule chain at normalization time:

| Source | Signal | Scope Assignment |
|--------|--------|-----------------|
| SAP_MM | movement_type IN (201, 261) AND material_group IN fossil_fuels | SCOPE_1 / stationary_combustion |
| SAP_MM | movement_type IN (201, 261) AND material_group IN fleet_fuels | SCOPE_1 / mobile_combustion |
| SAP_MM | movement_type IN (101, 102, 122) | SCOPE_3 / upstream_purchased_goods |
| SAP_MM | movement_type = 551 | SCOPE_3 / waste_generation |
| SAP_MM | movement_type IN (301, 311) | requires review for SCOPE_3 / upstream_transport |
| UTILITY_INTERVAL | channel = "Active Import" | SCOPE_2 / purchased_electricity |
| UTILITY_INTERVAL | channel = "Active Export" | excluded (onsite generation credit) |
| UTILITY_INTERVAL | channel = "Reactive" OR unit = "kVARh" | excluded (power quality, not consumption) |
| TRAVEL_CONCUR | mode_norm = "flight" AND status = "flown" | SCOPE_3 / business_travel |
| TRAVEL_CONCUR | status IN (canceled, voided) | excluded (not a flown emission) |
| TRAVEL_CONCUR | mode_norm = "hotel" | SCOPE_3 / business_travel (hotel stays) |

`SCOPE_3 / upstream_transport` for 301/311 movements requires analyst review because it depends on whether the logistics fleet is company-owned (Scope 1) or third-party (Scope 3).

---

## What This Model Does Not Do

1. **Does not compute emissions automatically on ingest.** Emissions are calculated only after normalization is complete and confidence is above threshold. This prevents garbage-in → garbage-out on records that haven't been validated.

2. **Does not support real-time API ingestion.** All ingestion is file-based. This is a deliberate choice: real-time streams bypass the analyst review workflow. In production, a queue-based architecture would be added; for this prototype, the flat-file model is more auditable and more realistic for how SAP exports actually arrive.

3. **Does not model downstream reporting frameworks** (GRI, CSRD, BRSR). The canonical record stores the GHG Protocol category. Framework-specific aggregations are a reporting layer concern, not a data model concern. Adding them here would couple the schema to regulatory formats that change annually.

---

*Schema version 1.0 — for Breathe ESG Tech Intern Assignment*
