export type Classification = "blocked" | "partial" | "success" | "uncertain" | "error";
export type Severity = "info" | "low" | "medium" | "high" | "critical";
export type ScanStatus = "pending" | "running" | "completed" | "failed" | "cancelled";

export interface Target {
  id: number;
  name: string;
  description?: string | null;
  url: string;
  http_method: string;
  headers: Record<string, string>;
  auth_type: "none" | "bearer" | "api_key" | "basic";
  request_template: Record<string, unknown>;
  payload_path: string;
  response_path?: string | null;
  timeout: number;
  retry_count: number;
  retry_backoff: number;
  max_conversation_turns: number;
  adapter_type: "http" | "openai" | "mock";
  meta: Record<string, unknown>;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface TargetCreatePayload {
  name: string;
  description?: string | null;
  url: string;
  http_method?: string;
  headers?: Record<string, string>;
  auth_type?: string;
  auth_token?: string | null;
  request_template?: Record<string, unknown>;
  payload_path?: string;
  response_path?: string | null;
  timeout?: number;
  retry_count?: number;
  retry_backoff?: number;
  max_conversation_turns?: number;
  adapter_type?: string;
  meta?: Record<string, unknown>;
}

export interface ScanConfig {
  attack_categories?: string[] | null;
  attack_ids?: string[] | null;
  max_attacks: number;
  concurrency: number;
  include_generated: boolean;
  include_mutations: boolean;
  mutation_count_per_attack: number;
  multi_turn_enabled: boolean;
  max_turns: number;
  rate_limit_per_second: number;
  timeout: number;
  regard_severity_filter?: number | null;
}

export interface ScanCreatePayload {
  target_id: number;
  name?: string | null;
  config: Partial<ScanConfig>;
}

export interface ScanSummary {
  total: number;
  success: number;
  partial: number;
  blocked: number;
  uncertain: number;
  error: number;
  overall_risk: string;
  avg_confidence: number;
}

export interface Scan {
  id: number;
  target_id: number;
  name?: string | null;
  status: ScanStatus;
  attack_count: number;
  config: Partial<ScanConfig>;
  summary: Partial<ScanSummary>;
  started_at?: string | null;
  ended_at?: string | null;
  created_at?: string | null;
}

export interface TestResult {
  id: number;
  test_run_id: number;
  attack_id: number;
  payload: string;
  response?: string | null;
  http_status?: number | null;
  latency_ms?: number | null;
  error?: string | null;
  classification: Classification;
  confidence: number;
  severity: Severity;
  evidence: Record<string, unknown>;
  layer_results: Record<string, unknown>;
  attack_meta?: Record<string, unknown> | null;
}

export interface Finding {
  id: number;
  test_run_id: number;
  title: string;
  category: string;
  severity: Severity;
  confidence: number;
  attack_id?: string | null;
  attack_objective?: string | null;
  payload?: string | null;
  target_response?: string | null;
  evidence?: string | null;
  violated_boundary?: string | null;
  root_cause?: string | null;
  remediation?: string | null;
  reproduction: Record<string, unknown>;
  created_at?: string | null;
}

export interface AttackInfo {
  id: string;
  category: string;
  objective: string;
  severity: Severity;
  template: string;
  expected_behavior?: string;
  evaluation_strategy?: string;
  tags: string[];
  is_reference?: boolean;
}

export interface AttackCatalog {
  categories: Record<string, string>;
  default_categories: string[];
  attacks: AttackInfo[];
}

export interface ReportScan {
  id: number;
  name: string;
  status: string;
  started_at?: string | null;
  ended_at?: string | null;
  generated_at?: string | null;
}

export interface ReportTarget {
  id: number;
  name: string;
  url: string;
  adapter_type: string;
}

export interface ReportBreakdownEntry {
  category: string;
  attempted: number;
  success: number;
  partial: number;
  blocked: number;
}

export interface FindingDetail {
  id: number;
  title: string;
  category: string;
  category_label: string;
  severity: Severity;
  confidence: number;
  attack_id?: string | null;
  attack_objective?: string | null;
  payload?: string | null;
  target_response?: string | null;
  evidence?: string | null;
  violated_boundary?: string | null;
  root_cause?: string | null;
  remediation?: string | null;
  reproduction: Record<string, unknown>;
}

export interface ReportData {
  scan: ReportScan;
  target: ReportTarget;
  summary: ScanSummary;
  breakdown: ReportBreakdownEntry[];
  severity_counts: Record<Severity, number>;
  top_vulnerabilities: string[];
  findings: FindingDetail[];
}