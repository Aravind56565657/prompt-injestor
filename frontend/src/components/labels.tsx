import type { Classification, ScanStatus, Severity } from "../types/models";
import {
  CLASSIFICATION_STYLES,
  RISK_STYLES,
  SEVERITY_STYLES,
  STATUS_STYLES,
} from "../lib/format";
import Badge from "./Badge";

export function ClassificationBadge({ value }: { value: Classification }) {
  const s = CLASSIFICATION_STYLES[value] ?? CLASSIFICATION_STYLES.uncertain;
  return (
    <Badge className={s.badge}>
      <span className={`h-1.5 w-1.5 rounded-full ${s.dot}`} />
      {s.label}
    </Badge>
  );
}

export function SeverityBadge({ value }: { value: Severity }) {
  const s = SEVERITY_STYLES[value] ?? SEVERITY_STYLES.info;
  return <Badge className={s.badge}>{s.label}</Badge>;
}

export function StatusBadge({ value }: { value: ScanStatus }) {
  const s = STATUS_STYLES[value] ?? STATUS_STYLES.pending;
  return <Badge className={s.badge}>{s.label}</Badge>;
}

export function RiskBadge({ value }: { value: string }) {
  const s = RISK_STYLES[value] ?? RISK_STYLES.unknown;
  return <Badge className={s.badge}>{s.label}</Badge>;
}