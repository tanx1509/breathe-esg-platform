# SOURCES.md — Operational Source Research

## Overview

This document summarizes the operational source research conducted for each ingestion domain. Each section covers: the format researched, what was learned, sample data rationale, and what breaks in production.

The system models three ingestion domains:
1. SAP MM flat-file exports (procurement / goods movements)
2. Utility interval CSV exports (electricity consumption)
3. Corporate travel CSV exports (Concur/Navan flight segments)

---

## 1. SAP MM Flat-File Exports

### Format Researched

MB51 (Material Document List) exported via ALV grid to CSV. This is the most common way ESG teams receive SAP procurement data — not through IDocs or OData, but through scheduled or ad-hoc ALV grid exports from the MM module.

Key transaction codes investigated: MB51 (material doc list), MIGO (goods movement), ME2M (purchase orders by material).

### What Was Learned

**SAP exports are locale-dependent.** A German-locale SAP system exports:
- Headers in German: "Buchungsdatum" (Posting Date), "Werks" (Plant), "Kostl" (Cost Center), "Menge" (Quantity), "Meins" (Unit of Measure), "LIFNR" (Supplier)
- Numbers in European format: `1.500,50` means 1500.50
- Negative values as trailing minus: `500.00-` means -500.00

**Leading zeros are silently truncated.** When Excel opens a SAP CSV, material numbers like `000000000000012345` become `12345`. This destroys the ability to join back to SAP master data. The parser must detect truncated MATNR fields and restore leading zeros to 18 characters.

**Movement types carry scope-assignment semantics:**
| Movement Type | Operational Meaning | Scope Assignment |
|--------------|---------------------|-----------------|
| 101 | Goods receipt from vendor | Scope 3 — purchased goods |
| 102 | Reversal of 101 | Scope 3 — reversal (nets against 101) |
| 122 | Return to vendor | Scope 3 — reversal |
| 201 | Consumption from warehouse | Scope 1 — if fuel/chemical |
| 261 | Consumption for production order | Scope 1 — if fuel |
| 301 | Plant-to-plant transfer | Scope 3 — upstream transport (requires review) |
| 311 | Storage location transfer | Scope 3 — transport (requires review) |
| 551 | Scrapping / waste | Scope 3 — waste generation |

**Duplicate header rows appear mid-file.** ALV grid exports sometimes repeat the header row after every N rows (pagination artifact). The parser must detect and skip these.

**Virtual plant codes exist.** Plant code `9999` is commonly used as a catch-all or dummy plant with no real geographic mapping. Records against virtual plants cannot have emission factors assigned because there is no grid emission factor for a non-existent location.

### Sample Data Rationale

The 15-row SAP sample CSV was designed to exercise every modeled anomaly:
- Rows with trailing minus values (reversal quantities)
- Rows with European number formatting
- Rows with truncated material numbers (orphaned after leading-zero loss)
- A row with missing cost center on a 201 movement type (BLOCKING)
- A row with cross-dimensional UoM (KG for a fuel material that should be in liters — BLOCKING)
- A row against virtual plant 9999 (BLOCKING)
- A duplicate header row mid-file
- Multiple movement types (101, 102, 201, 261, 301, 551)
- Both German and English header variants

### What Breaks in Production

1. **Excel-mangled CSVs.** Analysts often open SAP exports in Excel before uploading. Excel truncates leading zeros, reformats dates, and converts European numbers to text. The parser should detect Excel artifacts.
2. **Mixed-locale exports.** A multinational with SAP instances in Germany, India, and the US will produce exports in three locales. Header mapping must handle DE, EN, and potentially HI locale keys.
3. **Movement type 411/412 (transfer posting).** These create both a debit and credit movement. Without both sides of the posting, scope assignment is ambiguous. The parser logs these as INFO and defers to analyst review.

---

## 2. Utility Interval CSV Exports

### Format Researched

Interval meter data exported from utility portals or energy management systems. Format: 15-minute or 30-minute interval readings with timestamps, meter serial numbers, and consumption values in kWh or MWh.

Common sources: utility company web portals, building management systems (BMS), smart meter data aggregators.

### What Was Learned

**Interval data is per-meter, not per-account.** A single utility account may have multiple meters (main meter, sub-meters for HVAC, lighting, etc.). The parser must key on `Meter_SN` (serial number), not `Account_ID`.

**Duplicate timestamps occur frequently.** Meter data re-exports, estimated reads that are later replaced by actual reads, and DST transitions all create duplicate timestamp rows. Resolution hierarchy: drop null-usage row → retain estimated-read row → log NormalizationEvent.

**Missing intervals indicate data gaps.** If 15-minute intervals are expected and a 45-minute gap appears, this represents missing data that should not be silently ignored. The parser detects timestamp gaps and flags them as `MISSING_INTERVAL`.

**Unit inconsistency.** Some meters report in kWh, others in MWh. Some exports mix units within the same file. All values must be normalized to kWh for consistent Scope 2 calculation.

**Active export (negative values or "Export" channel).** Solar panels or on-site generation produce export readings. These must be excluded from Scope 2 purchased electricity — they represent generation credits, not consumption.

**Reactive power contamination.** Some interval exports include kVARh (reactive power) or kVAh (apparent power) readings alongside kWh (active power). Only active power (kWh) contributes to Scope 2 emissions. Reactive power rows must be excluded entirely.

**Footer summary rows.** Many utility exports append a summary row at the bottom with null timestamps and totalled values. The parser must detect and skip these.

### Sample Data Rationale

The 15-row utility sample CSV exercises:
- A meter serial with leading zeros stripped (needs restoration)
- Duplicate timestamps (one null-usage, one estimated)
- A gap in the timestamp sequence (missing interval)
- A row in MWh instead of kWh (unit shift)
- A negative consumption value (active export)
- A kVARh reactive power row
- A footer summary row with null timestamp
- An "N/A" string in a numeric consumption field
- Normal 15-minute interval readings for baseline

### What Breaks in Production

1. **Timezone ambiguity.** Interval timestamps may be in local time, UTC, or the utility's reporting timezone. Without explicit timezone metadata, a meter in IST (UTC+5:30) with timestamps in UTC will misalign with the fiscal reporting period.
2. **Estimated vs actual reads.** Some utilities mark readings as "Estimated" (E) vs "Actual" (A). Estimated reads have lower confidence and should be flagged for analyst awareness.
3. **Net metering confusion.** Buildings with solar may have net metering where the single meter records both import and export. Without channel separation, net consumption can be negative — leading to incorrect Scope 2 = 0 calculations.

---

## 3. Corporate Travel CSV Exports (Concur/Navan)

### Format Researched

Segment-level flight data exported from travel management systems. Modeled on SAP Concur and Navan export formats. Each row represents one flight segment (one leg of a journey), not a complete itinerary.

### What Was Learned

**Travel systems rarely provide emissions-ready data.** Exports typically contain:
- Origin airport (IATA code)
- Destination airport (IATA code)
- Cabin class
- Booking status
- Traveler name and cost center

They do not typically contain:
- Flight distance
- Emission factors
- CO2e values

Distance must be enriched post-ingestion using airport coordinates and Haversine great-circle calculation.

**Segment-level modeling is essential.** A round trip BOM→DEL→BOM is two segments with potentially different cabin classes, carriers, and booking statuses. Emissions are per-segment. A canceled return leg should not invalidate the outbound emission.

**Booking status matters operationally:**
| Status | Treatment |
|--------|-----------|
| Flown | Generate emissions |
| Canceled | Flag CANCELED_TICKET, exclude |
| Voided | Flag CANCELED_TICKET, exclude |
| Exchange/Reissue | Flag CANCELED_TICKET on original, process reissued segment |
| Open | Exclude — not yet a physical event |

**City codes create ambiguity.** IATA city codes (NYC, BJS, TYO) map to multiple airports. NYC could be JFK, EWR, or LGA. The parser flags these as `AMBIGUOUS_AIRPORT` because the exact airport affects distance calculation.

**Cabin class affects emission factors significantly:**
| Cabin Class | Multiplier (vs Economy) |
|-------------|------------------------|
| Economy | 1.0× |
| Premium Economy | 1.5× |
| Business | 2.0× |
| First | 2.4× |

These multipliers reflect the proportional floor space and weight allocation per passenger in each cabin.

**Ambiguous expense categories.** Travel exports sometimes include non-flight rows categorized as "Misc Travel" or "Ground Transport." These cannot be automatically classified and must be routed to analyst review.

### Sample Data Rationale

The 15-row travel sample CSV exercises:
- A canceled ticket (status = "Canceled")
- Duplicate segments (same origin/dest/date/traveler)
- A segment with a missing destination airport
- An origin using a city code (NYC → ambiguous)
- Multiple cabin classes (Economy, Business, First)
- A "Misc Travel" category row (ambiguous)
- Normal flown segments with resolvable IATA codes
- A segment requiring Haversine distance calculation
- A voided exchange/reissue pair

### What Breaks in Production

1. **Codeshare flights.** A traveler books on carrier A but flies on carrier B. The IATA code in the export may reference the marketing carrier, not the operating carrier. Emission factors by aircraft type would require operating carrier data.
2. **Multi-city itineraries with mixed bookings.** A single trip may span multiple booking references with segments added incrementally. Deduplication becomes complex when the same segment appears in multiple exports.
3. **Private/charter flights.** These do not appear in Concur/Navan exports and require separate ingestion. The system does not model them.
