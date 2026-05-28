# Breathe ESG — Activity Ingestion & Analyst Review Platform

An **audit-first** ESG activity ingestion and analyst review platform that prioritizes **data provenance**, **normalization traceability**, and **operational review workflows** over generic dashboards.

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                   Frontend (React)                   │
│   Login → Command Center → Review Queue → Drawer     │
├─────────────────────────────────────────────────────┤
│                  REST API (DRF + JWT)                │
│   /api/auth/ → /api/ingest/ → /api/review/           │
├─────────────────────────────────────────────────────┤
│              Three-Layer Ingestion Pipeline           │
│                                                       │
│  Layer 1: Raw Ingestion (Immutable)                   │
│    └── RawUpload: SHA-256 hashed, no update/delete    │
│                                                       │
│  Layer 2: Canonical Normalization                     │
│    └── CanonicalActivityRecord: source-agnostic       │
│    └── NormalizationEvent: append-only audit trail     │
│                                                       │
│  Layer 3: Analyst Review (The Product)                │
│    └── AnomalyFlag: BLOCKING / WARNING / INFO          │
│    └── ReviewEvent: append-only decision log           │
│    └── AuditLock: immutable period freeze              │
├─────────────────────────────────────────────────────┤
│              Reference Data                          │
│    PlantMaster · UoMSynonymMap · EmissionFactorTable  │
│    AirportReferenceTable                              │
└─────────────────────────────────────────────────────┘
```

## Three Source Parsers

| Parser | Source | Key Anomalies Handled |
|--------|--------|----------------------|
| **SAP MM** | ALV-grid CSV (MB51) | Trailing minus, European numbers, leading zeros, multilingual headers, movement type → scope mapping |
| **Utility Interval** | Smart meter 15-min | MWh→kWh shift, active export exclusion, reactive power filtering, interval gap detection |
| **Travel (Concur)** | Segment-level flights | Haversine distance, cabin class multipliers, duplicate segments, city code ambiguity |

## Quick Start

### Prerequisites
- Python 3.11+
- Node.js 18+

### Backend
```bash
cd backend
python3 -m venv venv && source venv/bin/activate
pip install django djangorestframework djangorestframework-simplejwt django-cors-headers whitenoise
python manage.py migrate
python manage.py seed_reference_data   # Creates tenant, users, reference data
python manage.py seed_sample_data      # Runs all 3 sample CSVs through parsers
python manage.py runserver 8000
```

### Frontend
```bash
cd frontend
npm install
npm run dev  # Starts on :5173, proxies /api → :8000
```

### Demo Credentials
| Username | Role | Password |
|----------|------|----------|
| `admin` | ADMIN | `esg2025` |
| `analyst` | ANALYST | `esg2025` |
| `viewer` | VIEWER | `esg2025` |

## Key Design Decisions

1. **Raw payloads are immutable** — `RawUpload.save()` raises `PermissionDenied` on updates
2. **Normalization events are append-only** — every transformation is logged with before/after values
3. **Review events are events, not status fields** — analyst decisions include person, timestamp, notes
4. **BLOCKING flags prevent approval** — system enforces that records cannot be approved until blocking anomalies are resolved
5. **Confidence scores are deterministic** — computed from specific deduction triggers, not ML
6. **Parsing ≠ normalization** — `ParsedRow` exists because parsing and normalization fail for different reasons

## Sample Data Results

After running `seed_sample_data`:
- **43 canonical records** across 3 source types
- **140 normalization events** (transformation audit trail)
- **37 anomaly flags** (19 unique flag types)
- **7 records requiring human review**

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/auth/token/` | JWT login (returns tenant_id, role in claims) |
| GET | `/api/review/queue/` | Paginated review queue with filters |
| GET | `/api/review/record/{id}/` | Full record detail with provenance |
| POST | `/api/review/record/{id}/approve/` | Approve (validates no BLOCKING flags) |
| POST | `/api/review/record/{id}/reject/` | Reject (notes required) |
| POST | `/api/review/record/{id}/edit/` | Edit + approve with audit trail |
| POST | `/api/review/flag/{id}/resolve/` | Resolve anomaly flag |
| POST | `/api/ingest/upload/` | Upload CSV file |
| GET | `/api/ingest/jobs/` | Recent ingestion jobs |
| GET | `/api/ingest/stats/` | Pipeline health by source type |
| GET | `/api/health/` | Health check |

## Documentation

- [MODEL.md](MODEL.md) — Complete data model specification
- [DECISIONS.md](DECISIONS.md) — Architectural rationale
- [TRADEOFFS.md](TRADEOFFS.md) — Deliberate exclusions
- [SOURCES.md](SOURCES.md) — Operational data research
