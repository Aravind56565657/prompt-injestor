import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api/client";
import Card from "../components/Card";
import Spinner from "../components/Spinner";
import { RiskBadge, SeverityBadge } from "../components/labels";import { formatDateTime, formatRatio } from "../lib/format";
import type { ReportData } from "../types/models";

const CLASS_LABELS: Record<string, string> = {
  total: "Total",
  success: "Success",
  partial: "Partial",
  blocked: "Blocked",
  uncertain: "Uncertain",
  error: "Error",
};

export default function Report() {
  const { scanId } = useParams<{ scanId: string }>();
  const id = Number(scanId);
  const [report, setReport] = useState<ReportData | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void api
      .getReportJson(id)
      .then(setReport)
      .catch((err) => setError(err instanceof Error ? err.message : String(err)));
  }, [id]);

  if (error) {
    return (
      <Card title="Report unavailable">
        <p className="text-sm text-red-700">{error}</p>
        <p className="mt-1 text-xs text-slate-500">
          The scan may still be running or the scan/completed results are not yet available.
        </p>
      </Card>
    );
  }
  if (!report) return <Spinner label="Building report…" />;

  const s = report.summary;
  const sev = report.severity_counts;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold">{report.scan.name} — Security Report</h1>
          <p className="text-sm text-slate-500">
            Target: {report.target.name} ({report.target.url}) · Generated {formatDateTime(report.scan.generated_at)}
          </p>
        </div>
        <div className="flex gap-2">
          <Link
            to={`/scans/${report.scan.id}`}
            className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-medium hover:bg-slate-50"
          >
            Back to scan
          </Link>
          <a
            href={`/api/reports/${report.scan.id}/json`}
            target="_blank"
            rel="noreferrer"
            className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-medium hover:bg-slate-50"
          >
            JSON
          </a>
          <a
            href={`/api/reports/${report.scan.id}/html`}
            target="_blank"
            rel="noreferrer"
            className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700"
          >
            Download HTML
          </a>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        {Object.entries(CLASS_LABELS).map(([key, label]) => (
          <div key={key} className="rounded-xl border border-slate-200 bg-white p-4">
            <div className="text-xs uppercase tracking-wide text-slate-500">{label}</div>
            <div className="mt-1 text-2xl font-bold tabular-nums text-slate-900">
              {s[key as keyof typeof s] ?? 0}
            </div>
          </div>
        ))}
      </div>

      <Card title="Executive summary" subtitle="Aggregated outcome across the scan">
        <div className="flex items-center gap-4">
          <RiskBadge value={s.overall_risk} />
          <span className="text-sm text-slate-600">
            Avg confidence: <b className="text-slate-800">{formatRatio(s.avg_confidence)}</b>
          </span>
        </div>
        <div className="mt-4 grid grid-cols-2 gap-3 md:grid-cols-5">
          {(["critical", "high", "medium", "low", "info"] as const).map((key) => (
            <div key={key} className="flex items-center justify-between rounded-lg border border-slate-200 px-3 py-2">
              <SeverityBadge value={key} />
              <span className="text-sm font-semibold tabular-nums">{sev[key]}</span>
            </div>
          ))}
        </div>
      </Card>

      <Card title="Breakdown by category" subtitle="Attempted vs successful/partial/blocked per attack category">
        {report.breakdown.length === 0 ? (
          <p className="text-sm text-slate-500">No attack results recorded.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-slate-200 text-xs uppercase tracking-wide text-slate-500">
                  <th className="py-2 pr-4 font-medium">Category</th>
                  <th className="py-2 pr-4 font-medium text-right">Attempted</th>
                  <th className="py-2 pr-4 font-medium text-right">Success</th>
                  <th className="py-2 pr-4 font-medium text-right">Partial</th>
                  <th className="py-2 pr-4 font-medium text-right">Blocked</th>
                </tr>
              </thead>
              <tbody>
                {report.breakdown.map((b) => (
                  <tr key={b.category} className="border-b border-slate-100">
                    <td className="py-2 pr-4 font-medium text-slate-800">{b.category}</td>
                    <td className="py-2 pr-4 text-right tabular-nums">{b.attempted}</td>
                    <td className="py-2 pr-4 text-right tabular-nums text-red-600">{b.success}</td>
                    <td className="py-2 pr-4 text-right tabular-nums text-amber-600">{b.partial}</td>
                    <td className="py-2 pr-4 text-right tabular-nums text-emerald-600">{b.blocked}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      <Card title={`Findings (${report.findings.length})`} subtitle="Confirmed vulnerabilities and remediation">
        {report.findings.length === 0 ? (
          <p className="text-sm text-slate-500">No confirmed vulnerabilities.</p>
        ) : (
          <div className="space-y-4">
            {report.findings.map((f) => (
              <div key={f.id} className="rounded-lg border border-slate-200 p-4">
                <div className="flex items-center gap-2">
                  <SeverityBadge value={f.severity} />
                  <h3 className="font-semibold text-slate-900">{f.title}</h3>
                  <span className="ml-auto text-xs text-slate-500">conf {formatRatio(f.confidence)}</span>
                </div>
                <p className="mt-1 text-xs text-slate-500">
                  {f.category_label} · {f.attack_id ?? "—"} — {f.attack_objective}
                </p>
                {f.payload && (
                  <pre className="mt-2 rounded-lg bg-slate-900 px-3 py-2 text-xs text-slate-100">{f.payload}</pre>
                )}
                {f.target_response && (
                  <pre className="mt-2 rounded-lg bg-slate-100 px-3 py-2 text-xs text-slate-800">
                    {f.target_response.slice(0, 2000)}
                  </pre>
                )}
                {f.violated_boundary && (
                  <p className="mt-2 text-sm text-slate-700">
                    <b>Boundary:</b> {f.violated_boundary}
                  </p>
                )}
                {f.root_cause && (
                  <p className="mt-1 text-sm text-slate-700">
                    <b>Root cause:</b> {f.root_cause}
                  </p>
                )}
                {f.remediation && (
                  <div className="mt-2 rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-800">
                    <b>Remediation:</b> {f.remediation}
                  </div>
                )}
                {f.reproduction && Object.keys(f.reproduction).length > 0 && (
                  <pre className="mt-2 rounded-lg bg-slate-100 px-3 py-2 text-xs text-slate-700">
                    {JSON.stringify(f.reproduction, null, 2)}
                  </pre>
                )}
              </div>
            ))}
          </div>
        )}
      </Card>

      {report.top_vulnerabilities.length > 0 && (
        <Card title="Top vulnerability categories" subtitle="Most frequently confirmed">
          <div className="flex flex-wrap gap-2">
            {report.top_vulnerabilities.map((v) => (
              <span key={v} className="rounded-full bg-amber-50 px-3 py-1 text-sm text-amber-800">
                {v}
              </span>
            ))}
          </div>
        </Card>
      )}
    </div>
  );
}