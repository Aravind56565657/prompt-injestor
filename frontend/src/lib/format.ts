import type { Classification, ScanStatus, Severity } from "../types/models";

export const CLASSIFICATION_STYLES: Record<Classification, { badge: string; dot: string; label: string }> = {
  success: { badge: "bg-red-100 text-red-800", dot: "bg-red-600", label: "Success" },
  partial: { badge: "bg-amber-100 text-amber-800", dot: "bg-amber-500", label: "Partial" },
  blocked: { badge: "bg-emerald-100 text-emerald-800", dot: "bg-emerald-600", label: "Blocked" },
  uncertain: { badge: "bg-slate-100 text-slate-700", dot: "bg-slate-400", label: "Uncertain" },
  error: { badge: "bg-purple-100 text-purple-800", dot: "bg-purple-500", label: "Error" },
};

export const SEVERITY_STYLES: Record<Severity, { badge: string; label: string }> = {
  critical: { badge: "bg-red-600 text-white", label: "Critical" },
  high: { badge: "bg-orange-500 text-white", label: "High" },
  medium: { badge: "bg-amber-500 text-white", label: "Medium" },
  low: { badge: "bg-lime-600 text-white", label: "Low" },
  info: { badge: "bg-slate-500 text-white", label: "Info" },
};

export const STATUS_STYLES: Record<ScanStatus, { badge: string; label: string }> = {
  pending: { badge: "bg-slate-200 text-slate-700", label: "Pending" },
  running: { badge: "bg-blue-100 text-blue-700 animate-pulse", label: "Running" },
  completed: { badge: "bg-emerald-100 text-emerald-800", label: "Completed" },
  failed: { badge: "bg-red-100 text-red-800", label: "Failed" },
  cancelled: { badge: "bg-slate-200 text-slate-600", label: "Cancelled" },
};

export const RISK_STYLES: Record<string, { badge: string; label: string }> = {
  critical: { badge: "bg-red-600 text-white", label: "Critical Risk" },
  high: { badge: "bg-orange-500 text-white", label: "High Risk" },
  medium: { badge: "bg-amber-500 text-white", label: "Medium Risk" },
  low: { badge: "bg-lime-600 text-white", label: "Low Risk" },
  unknown: { badge: "bg-slate-200 text-slate-700", label: "Unknown Risk" },
};

export function formatRatio(value: number): string {
  return `${Math.round(value * 100)}%`;
}

export function formatNumber(value: number): string {
  return new Intl.NumberFormat().format(value);
}

export function formatDateTime(value?: string | null): string {
  if (!value) return "—";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return value;
  return d.toLocaleString();
}

export function formatDuration(ms?: number | null): string {
  if (ms == null) return "—";
  if (ms < 1000) return `${ms} ms`;
  const s = ms / 1000;
  if (s < 60) return `${s.toFixed(1)} s`;
  const m = Math.floor(s / 60);
  return `${m}m ${Math.round(s % 60)}s`;
}

export function truncate(value: string, max: number): string {
  if (value.length <= max) return value;
  return `${value.slice(0, max)}…`;
}

export function classifyKey(
  key: string,
): "confidence" | "evidence" | "detail" | "analysis" | "layer" | "other" {
  if (key === "confidence") return "confidence";
  if (key === "evidence" || key === "detail") return key;
  if (key === "analysis") return "analysis";
  if (key === "layer") return "layer";
  return "other";
}