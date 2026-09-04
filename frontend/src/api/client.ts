import type {
  AttackCatalog,
  Finding,
  ReportData,
  Scan,
  ScanCreatePayload,
  Target,
  TargetCreatePayload,
  TestResult,
} from "../types/models";

const API_BASE = (import.meta.env.VITE_API_BASE as string | undefined) ?? "/api";
const CREDS_KEY = "pit_creds";

export function getStoredCreds(): { username: string; password: string } | null {
  try {
    const raw = localStorage.getItem(CREDS_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as { username: string; password: string };
    if (!parsed.username || !parsed.password) return null;
    return parsed;
  } catch {
    return null;
  }
}

export function storeCreds(username: string, password: string): void {
  localStorage.setItem(CREDS_KEY, JSON.stringify({ username, password }));
}

export function clearCreds(): void {
  localStorage.removeItem(CREDS_KEY);
}

export class ApiError extends Error {
  status: number;
  detail: unknown;
  constructor(status: number, detail: unknown) {
    super(typeof detail === "string" ? detail : `Request failed (${status})`);
    this.status = status;
    this.detail = detail;
  }
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string> | undefined),
  };
  const creds = getStoredCreds();
  if (creds) {
    headers.Authorization = "Basic " + btoa(`${creds.username}:${creds.password}`);
  }
  const res = await fetch(`${API_BASE}${path}`, { ...options, headers });
  if (!res.ok) {
    let detail: unknown = null;
    try {
      const body = await res.json();
      detail = (body as { detail?: unknown }).detail ?? body;
    } catch {
      detail = res.statusText;
    }
    throw new ApiError(res.status, detail);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export const api = {
  // Health
  health: () => request<{ status: string; app: string }>("/health"),

  // Targets
  listTargets: () => request<Target[]>("/targets"),
  getTarget: (id: number) => request<Target>(`/targets/${id}`),
  createTarget: (payload: TargetCreatePayload) =>
    request<Target>("/targets", { method: "POST", body: JSON.stringify(payload) }),
  deleteTarget: (id: number) => request<void>(`/targets/${id}`, { method: "DELETE" }),

  // Scans
  listScans: () => request<Scan[]>("/scans"),
  getScan: (id: number) => request<Scan>(`/scans/${id}`),
  createScan: (payload: ScanCreatePayload) =>
    request<Scan>("/scans", { method: "POST", body: JSON.stringify(payload) }),
  rerunScan: (id: number) => request<Scan>(`/scans/${id}/rerun`, { method: "POST" }),
  cancelScan: (id: number) => request<void>(`/scans/${id}`, { method: "DELETE" }),
  getResults: (scanId: number) => request<TestResult[]>(`/scans/${scanId}/results`),
  getFindings: (scanId: number) => request<Finding[]>(`/scans/${scanId}/findings`),

  // Reports
  getReportJson: (scanId: number) => request<ReportData>(`/reports/${scanId}/json`),

  // Attack catalog
  getCatalog: () => request<AttackCatalog>("/attacks/catalog"),

  // Interactive Target Chat Playground
  chatTarget: (
    targetId: number,
    payload: { message: string; evaluate?: boolean; profile?: string }
  ) =>
    request<{
      target_response: string | null;
      latency_ms: number;
      http_status: number;
      evaluation?: {
        classification: string;
        confidence: number;
        evidence: string[];
        detail?: {
          reasoning_summary?: string;
          violated_boundary?: string;
        };
      } | null;
      error?: string;
    }>(`/targets/${targetId}/chat`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
};