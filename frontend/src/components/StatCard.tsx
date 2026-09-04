export default function StatCard({
  label,
  value,
  accent = "bg-slate-900",
  sub,
}: {
  label: string;
  value: string | number;
  accent?: string;
  sub?: string;
}) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</div>
      <div className={`mt-2 text-2xl font-bold tabular-nums ${accent === "bg-red-500" ? "text-red-600" : accent === "bg-emerald-500" ? "text-emerald-600" : accent === "bg-amber-500" ? "text-amber-600" : accent === "bg-slate-400" ? "text-slate-700" : "text-slate-900"}`}>
        {value}
      </div>
      {sub && <div className="mt-1 text-xs text-slate-500">{sub}</div>}
    </div>
  );
}