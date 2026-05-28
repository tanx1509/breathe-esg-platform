# DECISIONS.md

## Philosophy

This prototype was intentionally designed as an audit-first ESG activity ingestion and analyst review system rather than a generalized sustainability dashboard.

The core architectural question throughout development was:

> *"Can an analyst or auditor trace exactly how a reported emissions figure was derived from operational source data?"*

As a result, the system prioritizes:

- provenance over automation
- normalization transparency over abstraction
- analyst reviewability over ingestion speed
- operational realism over feature breadth

The following sections document the key design decisions made during implementation.

---

## 1. Flat-File SAP Ingestion over Direct ERP Integration

### Decision

The prototype models SAP ingestion using flat-file CSV exports (MB51 / ALV-style exports) instead of direct SAP integrations through IDocs, OData APIs, or database replication.

### Why

This decision was driven primarily by operational realism.

In many organizations, ESG and sustainability teams do not receive direct production SAP access. Reporting workflows frequently rely on:

- scheduled CSV exports
- emailed operational reports
- shared-drive extracts
- manually uploaded ERP data

Flat-file ingestion therefore better represents how operational ESG data commonly enters reporting pipelines.

This approach also surfaces realistic ingestion problems that are important for analyst review workflows:

- multilingual headers
- leading-zero truncation
- trailing negative values
- locale-specific number formatting
- duplicate headers
- inconsistent units

These operational inconsistencies are often hidden behind normalized APIs.

### Alternative Considered

- SAP IDoc ingestion
- SAP OData APIs
- direct database replication
- event-based ERP synchronization

### Why Rejected

These approaches were rejected for the MVP because they:

- increase infrastructure complexity significantly
- optimize for integration engineering instead of ingestion governance
- reduce visibility into operational data inconsistencies
- move focus away from analyst review and normalization traceability

The assignment emphasized operational reasoning and auditability rather than enterprise integration depth.

### What I Would Ask the PM

- How do ESG analysts currently receive SAP operational data?
- Is direct ERP integration expected in future scope?
- Are there restrictions around storing raw ERP exports for audit replay?
- Which SAP modules are operationally in scope for ESG reporting?

---

## 2. Activity-Centric Modeling over Emission-Centric Modeling

### Decision

The canonical model is centered around operational activity records rather than directly around emissions.

Emissions are treated as derived values computed from physical activity data.

### Why

This was the most important architectural decision in the system.

Operational activity is the true source-of-truth in ESG reporting:

- liters of diesel consumed
- kWh of electricity imported
- flight segments traveled
- purchased material quantities

Emission calculations are downstream interpretations of those activities.

This distinction matters because:

- emission factors change over time
- methodologies evolve
- recalculation may be required retroactively
- auditors validate operational evidence rather than carbon math outputs

By centering the system around activity records:

- provenance remains stable
- recalculation becomes reproducible
- normalization history stays attached to physical quantities
- reversal events can be modeled correctly

This also improves audit replay because the underlying operational evidence remains immutable even if reporting methodologies change later.

### Alternative Considered

A simplified emission-centric schema:

- EmissionRecord
- Scope category
- Emissions value
- Reporting metadata

### Why Rejected

The emission-centric approach was rejected because it:

- weakens provenance
- tightly couples ingestion to current methodologies
- obscures operational source evidence
- makes retroactive recalculation harder to explain under audit

The prototype instead treats emissions as a computed reporting layer derived from operational activities.

### What I Would Ask the PM

- Will historical emissions require recalculation under updated methodologies?
- Are assurance providers expected to inspect operational source data?
- Should multiple methodologies coexist across reporting periods?
- Is operational traceability more important than reporting aggregation speed?

---

## 3. Segment-Level Travel Modeling over Trip-Level Modeling

### Decision

Travel ingestion is modeled at the individual segment level rather than at the itinerary or trip level.

Each flight leg becomes its own canonical activity record.

### Why

Emissions are fundamentally generated per travel segment, not per itinerary.

A single business trip may contain:

- multiple flight legs
- different cabin classes
- partial cancellations
- reissued tickets
- mixed carriers

Operational travel exports from systems like SAP Concur or Navan are also commonly structured at the segment level.

Modeling at the segment level enables:

- accurate distance enrichment
- cabin-class multipliers
- cancellation handling
- duplicate segment detection
- route-level anomaly review

It also improves analyst review because problematic segments can be isolated independently without invalidating the entire itinerary.

### Alternative Considered

Trip-level aggregation:

- one record per itinerary
- aggregated emissions per trip
- combined route handling

### Why Rejected

Trip-level modeling was rejected because:

- cabin class can vary between segments
- partial cancellations become ambiguous
- anomaly handling becomes harder
- provenance weakens during itinerary changes
- segment-level exports require additional reconciliation logic

The segment-level model better reflects operational travel data structures.

### What I Would Ask the PM

- Are downstream users interested in route-level or traveler-level analysis?
- Are rail and hotel emissions expected in future scope?
- How are exchanged or reissued tickets currently handled operationally?
- Are analysts reviewing itinerary-level or segment-level exports today?

---

## 4. Flights-Only Scope for Travel Data

### Decision

The prototype intentionally limits travel ingestion to flights only.

Hotels, rail, taxis, and meal reimbursements are excluded.

### Why

The purpose of the travel pipeline is to demonstrate:

- ingestion
- enrichment
- normalization
- anomaly detection
- analyst review

Flight records already exercise all of these workflows through:

- airport enrichment (IATA code → coordinates → great-circle distance)
- cabin-class emission factor multipliers
- duplicate segment handling
- cancellation handling
- missing-location review

Adding additional travel modes would substantially increase:

- parser variability
- categorization complexity
- emission-factor branching
- review workflow complexity

without adding significant architectural insight.

The constrained scope therefore creates a more focused and defensible MVP.

### Alternative Considered

Supporting:

- hotels
- rail
- taxis
- mileage reimbursement
- expense-category mapping

### Why Rejected

These were excluded because:

- category semantics vary heavily between organizations
- ingestion complexity grows quickly
- normalization logic fragments across modes
- the assignment rewards operational depth over reporting breadth

The flight-only scope was sufficient to demonstrate the normalization and analyst-review pipeline end-to-end.

### What I Would Ask the PM

- Is flight travel operationally dominant in current reporting?
- Are hotel emissions estimated separately today?
- Is there an approved methodology already used internally?
- Are employee reimbursements included within reporting boundaries?

---

## 5. File-Based Ingestion over Real-Time Streaming

### Decision

The ingestion architecture is intentionally file-based rather than stream-based or real-time API-driven.

### Why

This decision reinforces the system's audit-first philosophy.

Real-time systems optimize primarily for:

- ingestion throughput
- synchronization speed
- low-latency processing

This prototype instead optimizes for:

- provenance checkpoints
- analyst review
- normalization traceability
- controlled approval workflows

File-based ingestion creates a deliberate operational checkpoint where:

- raw payloads are preserved
- normalization occurs deterministically
- anomalies are surfaced before approval
- analysts can intervene before emissions become reportable

This more closely reflects periodic ESG reporting operations.

### Alternative Considered

- streaming ingestion
- webhook-driven synchronization
- direct polling integrations
- queue-based ingestion pipelines

### Why Rejected

These approaches were rejected because they:

- increase architectural complexity significantly
- weaken analyst review gating
- prioritize ingestion speed over review quality
- reduce visibility into ingestion provenance

For this prototype, operational defensibility was prioritized over ingestion velocity.

### What I Would Ask the PM

- Are reporting cycles monthly, quarterly, or near-real-time?
- Is analyst review mandatory before emissions become reportable?
- Are ingestion SLAs operationally important?
- Is future queue-based ingestion expected?

---

## 6. Append-Only Review and Normalization Events

### Decision

Normalization actions and analyst reviews are modeled as append-only event logs instead of mutable status updates.

### Why

Auditability depends not only on current state, but also on historical decision lineage.

A mutable status field can answer:

> "What is the current status?"

It cannot answer:

> "Who changed it, when, and why?"

Append-only events preserve:

- chronological review history
- transformation lineage
- analyst interventions
- correction rationale
- approval traceability

This pattern is commonly used in:

- financial systems
- compliance tooling
- regulated operational workflows
- audit-sensitive platforms

### Alternative Considered

Simple mutable fields:

- reviewed_by
- reviewed_at
- current_status
- normalized_by

### Why Rejected

The mutable-state approach was rejected because it:

- weakens historical traceability
- obscures analyst accountability
- makes review replay difficult
- reduces audit defensibility

The append-only model provides stronger provenance guarantees while remaining manageable within MVP scope.

### What I Would Ask the PM

- Are analyst actions expected to be externally audited?
- Should waived anomalies remain permanently visible?
- Is review replay required during assurance sampling?
- Are correction histories expected to remain immutable?
