# Breathe ESG — Activity Ingestion & Analyst Review Platform

An audit-first ESG data pipeline and governance platform built for deterministic accuracy, data provenance, and operational trust.

When ESG activity data is ingested without normalization, reporting becomes guesswork. When anomalies are approved without risk context, audits fail. Breathe ESG closes the gap by separating data ingestion from canonical reporting via a rigorous analyst review workflow.

---

## 🎯 Architectural Philosophy

This platform explicitly rejects the "upload and visualize" dashboard archetype. Instead, it is built on a **three-layer ingestion pipeline**:

1. **Raw Ingestion Layer**: Source-specific parsers (`SAP_MM`, `UTILITY_INTERVAL`, `TRAVEL_CONCUR`) extract un-normalized activity data.
2. **Deterministic Intelligence Layer**: A rules-engine evaluates records against 19 specific anomaly vectors (e.g., *Cross-dimensional UOM*, *Impossible dates*, *Orphaned cost centers*), calculating a deterministic Confidence Score (0-100) and severity priority.
3. **Analyst Review Layer**: A strict RBAC-gated governance workflow where Analysts must resolve `BLOCKING` flags and explicitly approve transformations before a record enters the `CanonicalActivityRecord` reporting layer.

Full documentation available in:
- `MODEL.md` — Domain architecture and parsing strategies
- `DECISIONS.md` — Architectural trade-offs and rationale

---

## 🚀 Quick Start

### 1. Backend (Django REST Framework)

```bash
# Navigate to backend
cd backend

# Create virtual environment and install dependencies
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Run migrations and seed the database with demo users/data
python manage.py migrate
python manage.py seed_reference_data
python manage.py seed_sample_data

# Start the server
python manage.py runserver 8000
# → API running at http://localhost:8000
```

### 2. Frontend (React + Vite)

```bash
# Navigate to frontend in a new terminal
cd frontend

# Install dependencies
npm install

# Start the development server
npm run dev
# → UI running at http://localhost:5173
```

---

## 🔐 Role-Based Access Control (RBAC)

The system implements strict route guards and backend API permissions based on user roles.

| Role | Capabilities | Demo Credentials (User/Pass) |
|------|--------------|------------------------------|
| **ADMIN** | Full system access, audit locks, user management. | `admin` / `esg2025` |
| **ANALYST** | Uploads, approvals, rejections, manual edits, flag resolution. | `analyst` / `esg2025` |
| **VIEWER** | Read-only access to dashboards, queue, and provenance drawer. | `viewer` / `esg2025` |

---

## 🌍 Deployment Strategy (Vercel + Railway)

The architecture is designed to be deployed as decoupled services.

### Frontend (Vercel)
The frontend uses Vite and React Router. It includes **Vercel Web Analytics** out of the box to track viewer traffic, demographics, and engagement.

1. Import the repository into your Vercel dashboard.
2. Set the framework preset to `Vite`.
3. Vercel Web Analytics will automatically begin tracking once deployed.

### Backend (Railway or Render)
The Django API uses SQLite (configurable to PostgreSQL via `dj-database-url` in `production.py`) and serves the REST endpoints.

1. Create a Railway project and deploy from the GitHub repository.
2. Set `DJANGO_SETTINGS_MODULE=config.settings.production`
3. Update the frontend's `.env.production` (or `api/client.ts` baseURL) to point to the new Railway URL.

---

## 🏗 Tech Stack

| Technology | Why |
| --- | --- |
| **Django & DRF** | Server-side data integrity. Python provides the best ecosystem for complex data parsing, Pandas integration (if needed), and scientific calculations. |
| **React + Vite** | Instant HMR and fast builds. Enables a highly interactive, state-heavy review dashboard without server roundtrips for UI updates. |
| **Recharts** | Lightweight, highly customizable, SVG-based charting for the Analytics dashboards. |
| **Tailwind CSS** | Utility-first CSS with a strict Breathe ESG design token system (`index.css`). Enables rapid iteration on complex UI requirements without CSS bloat. |
| **SQLite (Dev)** | Zero-config local development, seamlessly upgradable to PostgreSQL for production concurrency via Django ORM. |

---

## 📊 Core Modules

| Module | Status | Description |
| --- | --- | --- |
| **Ingestion Pipeline** | Complete | `SAP_MM`, `UTILITY_INTERVAL`, and `TRAVEL_CONCUR` parsers. |
| **Anomaly Engine** | Complete | 19 deterministic rules across 3 severity levels. |
| **Command Center** | Complete | High-level ingestion statistics, priorities, and system health. |
| **Analytics Dashboard** | Complete | Deep-dive visualizations on emissions scope, data quality, and trends. |
| **Review Queue** | Complete | Filterable, paginated table prioritizing the lowest confidence scores first. |
| **Provenance Drawer** | Complete | 5-tab audit trail showing raw payload, timeline, flags, and review history. |
| **RBAC Enforcement** | Complete | Server-enforced permissions blocking unauthorized mutations. |

---

## 📂 Repository Structure

```text
esg/
├── backend/
│   ├── config/            # Django settings (base, local, production)
│   ├── core/              # Users, Tenants, RBAC Permissions, Pagination
│   ├── ingestion/         # File upload, parsing engine, BaseParser
│   ├── normalization/     # Canonical Activity Records, Normalization Events
│   ├── reference/         # Reference data (Emission factors, UOM mapping)
│   ├── review/            # Anomaly Flags, Review Events, Queue API
│   ├── sample_data/       # CSV templates for testing uploads
│   └── manage.py
│
├── frontend/
│   ├── src/
│   │   ├── api/           # Axios client, auth interceptors
│   │   ├── components/    # Layout, Sidebar
│   │   ├── pages/         # CommandCenter, Analytics, ReviewQueue, UploadPage
│   │   ├── types/         # TypeScript interfaces
│   │   ├── App.tsx        # React Router, Vercel Analytics integration
│   │   └── index.css      # Tailwind design system & micro-animations
│   ├── package.json
│   ├── tailwind.config.js
│   └── vite.config.ts
│
├── MODEL.md               # Domain architecture & parsing methodology
├── DECISIONS.md           # Engineering trade-offs
└── README.md
```
