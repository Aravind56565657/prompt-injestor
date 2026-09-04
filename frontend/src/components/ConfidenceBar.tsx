import { formatRatio } from "../lib/format";

export default function ConfidenceBar({ value, tone }: { value: number; tone: "red" | "emerald" | "amber" | "slate" }) {
  const colors: Record<string, string> = {
    red: "bg-red-500",
    emerald: "bg-emerald-500",
    amber: "bg-amber-500",
    slate: "bg-slate-400",
  };
  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 w-20 overflow-hidden rounded-full bg-slate-200">
        <div
          className={`h-full rounded-full ${colors[tone]}`}
          style={{ width: `${Math.min(100, Math.max(0, value * 100))}%` }}
        />
      </div>
      <span className="text-xs tabular-nums text-slate-600">{formatRatio(value)}</span>
    </div>
  );
}