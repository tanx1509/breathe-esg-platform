// ─── Enums ────────────────────────────────────────────────────────────
export type SourceType = 'SAP_MM' | 'UTILITY_INTERVAL' | 'TRAVEL_CONCUR';
export type ScopeCategory = 'SCOPE_1' | 'SCOPE_2' | 'SCOPE_3' | '';
export type ReviewStatus = 'PENDING' | 'UNDER_REVIEW' | 'APPROVED' | 'REJECTED' | 'AUDIT_LOCKED';
export type ReviewPriority = 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
export type Severity = 'INFO' | 'WARNING' | 'BLOCKING';
export type ResolutionStatus = 'OPEN' | 'AUTO_RESOLVED' | 'ANALYST_RESOLVED' | 'WAIVED';

// ─── Review Queue ─────────────────────────────────────────────────────
export interface AnomalySummary {
  id: string;
  type: string;
  severity: Severity;
  status: ResolutionStatus;
}

export interface QueueRecord {
  id: string;
  source_type: SourceType;
  source_document_ref: string;
  scope_category: ScopeCategory;
  scope_subcategory: string;
  activity_type: string;
  activity_date: string | null;
  raw_quantity_string: string;
  raw_unit: string;
  normalized_quantity: string | null;
  normalized_unit: string;
  confidence_score: string;
  review_priority: ReviewPriority;
  review_status: ReviewStatus;
  requires_human_review: boolean;
  anomaly_summary: AnomalySummary[];
  blocking_count: number;
  warning_count: number;
  normalization_rules: string[];
  facility_id: string;
  cost_center: string;
  calculated_emissions: string | null;
  created_at: string;
}

// ─── Record Detail ────────────────────────────────────────────────────
export interface RawUpload {
  id: string;
  row_number: number;
  raw_payload: Record<string, string>;
  received_at: string;
  immutable_hash: string;
}

export interface ParsedRow {
  id: string;
  parse_status: string;
  parse_errors: Array<{ field: string; raw_value: string; error_type: string }>;
  detected_schema: string;
  locale_detected: string;
  date_format_inferred: string;
  parsed_at: string;
}

export interface NormalizationEvent {
  id: string;
  event_type: string;
  field_name: string;
  before_value: string;
  after_value: string;
  rule_applied: string;
  applied_by: 'SYSTEM' | 'ANALYST';
  applied_by_user: string | null;
  applied_at: string;
  notes: string;
}

export interface AnomalyFlag {
  id: string;
  flag_type: string;
  severity: Severity;
  auto_resolvable: boolean;
  resolution_status: ResolutionStatus;
  resolution_note: string;
  resolved_by: string | null;
  resolved_at: string | null;
  detected_at: string;
}

export interface ReviewEvent {
  id: string;
  action: string;
  previous_status: ReviewStatus;
  new_status: ReviewStatus;
  performed_by: string | null;
  performed_by_email: string | null;
  performed_at: string;
  notes: string;
  fields_edited: Record<string, unknown> | null;
}

export interface RecordDetail extends QueueRecord {
  raw_quantity: string | null;
  unit_dimension: string;
  emission_factor_id: string | null;
  emission_factor_value: string | null;
  emission_factor_unit: string;
  emissions_locked: boolean;
  supplier_id: string;
  material_group: string;
  immutable_hash: string;
  approved_by: string | null;
  approved_at: string | null;
  audit_locked_at: string | null;
  source_metadata: Record<string, unknown>;
  updated_at: string;
  ghg_protocol_category: string;
  raw_payload: RawUpload | null;
  parsed_row: ParsedRow | null;
  normalization_events: NormalizationEvent[];
  anomaly_flags: AnomalyFlag[];
  review_events: ReviewEvent[];
}

// ─── Ingestion ────────────────────────────────────────────────────────
export interface IngestionJob {
  id: string;
  source_type: SourceType;
  file_name: string;
  status: string;
  total_rows: number;
  parsed_rows: number;
  failed_rows: number;
  suspicious_rows: number;
  triggered_at: string;
  completed_at: string | null;
}

export interface IngestionStats {
  source_type: SourceType;
  total_jobs: number;
  total_rows: number;
  failed_rows: number;
  suspicious_rows: number;
  pending_review: number;
}

// ─── Paginated ────────────────────────────────────────────────────────
export interface PaginatedResponse<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

// ─── Auth ─────────────────────────────────────────────────────────────
export interface AuthTokens {
  access: string;
  refresh: string;
}

export interface DecodedToken {
  user_id: string;
  tenant_id: string;
  role: string;
  email: string;
  exp: number;
}
