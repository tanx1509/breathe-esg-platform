# TRADEOFFS.md — Deliberate Exclusions

## Philosophy

This document explains what was intentionally excluded from the MVP and why those exclusions improved the prototype. The assignment rewards restraint, judgment, and defensibility. A system that deeply executes a narrow scope demonstrates stronger operational understanding than one that attempts breadth.

---

## 1. No Automated Emission Factor Engine

### What Was Excluded

The system does not automatically infer or select emission factors based on material descriptions, NLP classifiers, or AI-based recommendations. Factor assignment is deterministic and rule-based via the `EmissionFactorTable`.

### Why

**Silent misclassification risk.** "Industrial Solvent — Cleaning Grade" could be a chemical product (Scope 3) or a fuel (Scope 1) depending on use. An automated classifier might assign the wrong factor without surfacing the ambiguity.

**Factor version drift.** DEFRA, IEA, and Ecoinvent publish on different schedules. Silent auto-application changes historical totals without audit trail.

**Material group ambiguity.** SAP MATKL codes are tenant-specific. "RW01" could mean "Raw Water" or "Raw Wax" across tenants.

**Audit defensibility.** "The AI recommended it" is not defensible under ISAE 3410 or CSRD assurance. Factor selection must trace to a specific rule or analyst decision.

### What I Would Build Next

- Factor recommendation engine (suggests, never auto-applies)
- Analyst confirmation as a required step
- Factor version tracking with period-level snapshots

### What I Would Ask the PM

- Are analysts comfortable with manual factor assignment?
- Is there an internally maintained factor library?
- Has the organization undergone external assurance? What was the auditor's stance on automated factor selection?

---

## 2. No Real-Time API Ingestion

### What Was Excluded

No streaming ingestion, webhook-driven sync, direct API polling, or queue-based pipelines. All ingestion is file-based with explicit analyst review checkpoints.

### Why

**The analyst review gate is the product's core value. Real-time streaming bypasses it.**

The architecture creates five deliberate provenance checkpoints:

1. File upload → IngestionJob created
2. Parsing → RawUpload records stored immutably
3. Normalization → CanonicalActivityRecords with anomaly flags
4. Analyst review → ReviewEvents created
5. Approval → emissions become reportable

Each checkpoint is a provenance boundary. Removing any weakens auditability.

**Operational realism:** ESG reporting operates on monthly/quarterly cycles with periodic exports, not real-time streams. File-based ingestion is more operationally authentic.

### What I Would Build Next

- Celery + Redis async parsing (preserving all provenance checkpoints)
- SFTP/S3 drop-folder monitoring with auto IngestionJob creation
- Idempotent ingestion via `file_hash` deduplication

### What I Would Ask the PM

- What is expected data volume per reporting period?
- Is batch ingestion sufficient, or are there near-real-time regulatory requirements?
- Would an SFTP drop-folder reduce operational friction?

---

## 3. No Multi-Framework Reporting Layer (GRI / CSRD / BRSR)

### What Was Excluded

No framework-specific report generation: GRI Standards, CSRD/ESRS, BRSR, CDP, TCFD, or SASB. The canonical model stores GHG Protocol scope classifications only.

### Why

**Framework aggregations change annually.** GRI revised in 2021. CSRD effective 2024 with phased applicability through 2028. BRSR mandated in India FY2022-23 with evolving requirements. SASB consolidated into ISSB in 2023.

Coupling the data model to any framework creates schema churn in the wrong layer.

**Correct architectural boundary:**

- **Data layer** (this system): normalized activity records with GHG Protocol scope classification. Stable since 2004.
- **Reporting layer** (future): maps GHG Protocol categories to framework disclosures. Volatile, should be a separate service.

The `ghg_protocol_category` field already stores the universal mapping key (Scope 3 categories 1–15) that all frameworks reference.

### What I Would Build Next

- Reporting microservice reading canonical records for framework-specific outputs
- Template-based report generation with framework mappings as configuration
- Framework version management with period-level binding

### What I Would Ask the PM

- Which frameworks are operationally required?
- Are reports currently produced manually from exported data?
- How frequently do framework requirements change in practice?
