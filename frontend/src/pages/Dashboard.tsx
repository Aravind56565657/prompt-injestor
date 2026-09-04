import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import Card from "../components/Card";
import EmptyState from "../components/EmptyState";
import Spinner from "../components/Spinner";
import StatCard from "../components/StatCard";
import { StatusBadge, RiskBadge } from "../components/labels";
import { formatDateTime } from "../lib/format";
import type { Scan, Target } from "../types/models";

export default function Dashboard() {
  const [targets, setTargets] = useState<Target[] | null>(null);
  const [scans, setScans] = useState<Scan[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const [t, s] = await Promise.all([api.listTargets(), api.listScans()]);
      setTargets(t);
      setScans(s);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  if (error) {
    return (
      <Card title="Could not reach the API">
        <p className="text-sm text-slate-600">{error}</p>
        <p className="mt-2 text-sm text-slate-500">
          Start the backend with <code className="rounded bg-slate-100 px-1">uvicorn app.main:app</code> and the
          mock target with <code className="rounded bg-slate-100 px-1">python run.py</code>.
        </p>
      </Card>
    );
  }

  if (!targets || !scans) return <Spinner label="Loading dashboard…" />;

  const activeScans = scans.filter((s) => s.status === "running").length;
  const failingTargetFindings = 0;

  const highestRisk = (() => {
    const rank: Record<string, number> = { critical: 4, high: 3, medium: 2, low: 1, unknown: 0 };
    const completed = scans
      .filter((s) => s.summary?.overall_risk && s.summary.overall_risk !== "unknown")
      .sort(
        (a, b) =>
          (rank[b.summary.overall_risk ?? "unknown"] ?? 0) -
          (rank[a.summary.overall_risk ?? "unknown"] ?? 0),
      );
    return completed[0]?.summary.overall_risk ?? "—";
  })();
  const highestRiskAccent =
    highestRisk === "critical" || highestRisk === "high"
      ? "bg-red-500"
      : highestRisk === "medium"
        ? "bg-amber-500"
        : highestRisk === "low"
          ? "bg-emerald-500"
          : "bg-slate-400";

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold">Dashboard</h1>
          <p className="text-sm text-slate-500">Overview of targets and security scans</p>
        </div>
        <div className="flex gap-2">
          <Link
            to="/targets/new"
            className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-medium hover:bg-slate-50"
          >
            Add Target
          </Link>
          <Link
            to="/scans/new"
            className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700"
          >
            Run Scan
          </Link>
        </div>
      </div>

      <div className="grid grid-cols-4 gap-4">
        <StatCard label="Targets" value={targets.length} />
        <StatCard
          label="Recent Scans"
          value={scans.length}
          sub={activeScans > 0 ? `${activeScans} running` : undefined}
        />
        <StatCard label="Findings" value={failingTargetFindings} sub="across recent scans" />
        <StatCard
          label="Highest Risk"
          value={highestRisk}
          accent={highestRiskAccent}
        />
      </div>

      <Card title="Recent Scans" subtitle="Latest 10 scan runs">
        {scans.length === 0 ? (
          <EmptyState
            title="No scans yet"
            hint="Add a target and run a prompt-injection scan to see results here."
            action={
              <Link
                to="/scans/new"
                className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700"
              >
                Configure a scan
              </Link>
            }
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-slate-200 text-xs uppercase tracking-wide text-slate-500">
                  <th className="py-2 pr-4 font-medium">Scan</th>
                  <th className="py-2 pr-4 font-medium">Target</th>
                  <th className="py-2 pr-4 font-medium">Status</th>
                  <th className="py-2 pr-4 font-medium text-right">Attacks</th>
                  <th className="py-2 pr-4 font-medium text-right">Risk</th>
                  <th className="py-2 font-medium">Started</th>
                </tr>
              </thead>
              <tbody>
                {scans.slice(0, 10).map((scan) => {
                  const target = targets.find((t) => t.id === scan.target_id);
                  return (
                    <tr key={scan.id} className="border-b border-slate-100 hover:bg-slate-50">
                      <td className="py-2.5 pr-4">
                        <Link to={`/scans/${scan.id}`} className="font-medium text-slate-900 hover:underline">
                          {scan.name ?? `Scan #${scan.id}`}
                        </Link>
                      </td>
                      <td className="py-2.5 pr-4 text-slate-600">{target?.name ?? `Target #${scan.target_id}`}</td>
                      <td className="py-2.5 pr-4">
                        <StatusBadge value={scan.status} />
                      </td>
                      <td className="py-2.5 pr-4 text-right tabular-nums text-slate-600">
                        {scan.summary?.total ?? scan.attack_count ?? "—"}
                      </td>
                      <td className="py-2.5 pr-4 text-right">
                        <RiskBadge value={scan.summary?.overall_risk ?? "unknown"} />
                      </td>
                      <td className="py-2.5 text-xs text-slate-500">{formatDateTime(scan.started_at)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}