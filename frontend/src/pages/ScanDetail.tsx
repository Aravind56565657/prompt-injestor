import { useCallback, useEffect, useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import { api } from "../api/client";
import Card from "../components/Card";
import ConfidenceBar from "../components/ConfidenceBar";
import Spinner from "../components/Spinner";
import StatCard from "../components/StatCard";
import Tabs from "../components/Tabs";
import { ClassificationBadge, RiskBadge, SeverityBadge, StatusBadge } from "../components/labels";
import { formatDateTime, formatDuration, formatRatio, truncate } from "../lib/format";
import { usePolling } from "../hooks/usePolling";
import type { Classification, Finding, Scan, TestResult } from "../types/models";

export default function ScanDetail() {
  const { scanId } = useParams<{ scanId: string }>();
  const id = Number(scanId);
  const [tab, setTab] = useState("results");
  const [results, setResults] = useState<TestResult[] | null>(null);
  const [findings, setFindings] = useState<Finding[] | null>(null);
  const [resultsError, setResultsError] = useState<string | null>(null);

  const fetchScan = useCallback(() => api.getScan(id), [id]);
  const shouldPoll = useCallback((s: Scan) => s.status === "running" || s.status === "pending", []);
  const { data: scan, error: scanError, loading: scanLoading, refresh: refreshScan } = usePolling<Scan>(fetchScan, 1500, shouldPoll);

  useEffect(() => {
    if (!scan) return;
    void api
      .getResults(id)
      .then((r) => setResults(r))
      .catch((err) => setResultsError(err instanceof Error ? err.message : String(err)));

    if (scan.status !== "running" && scan.status !== "pending") {
      void api
        .getFindings(id)
        .then(setFindings)
        .catch(() => undefined);
    }
  }, [id, scan]);

  const refreshAll = async () => {
    await refreshScan();
    try {
      setResults(await api.getResults(id));
    } catch (err) {
      setResultsError(err instanceof Error ? err.message : String(err));
    }
  };

  const counts = useMemo(() => {
    const c: Record<string, number> = { total: 0, success: 0, partial: 0, blocked: 0, uncertain: 0, error: 0 };
    if (results) {
      c.total = results.length;
      for (const r of results) {
        if (c[r.classification] !== undefined) c[r.classification] += 1;
      }
    }
    return c;
  }, [results]);

  const avgConf = useMemo(() => {
    if (!results || results.length === 0) return 0;
    return results.reduce((a, r) => a + r.confidence, 0) / results.length;
  }, [results]);

  const running = scan?.status === "running" || scan?.status === "pending";

  if (scanLoading && !scan) return <Spinner label="Loading scan…" />;
  if (scanError) {
    return (
      <Card title="Error">
        <p className="text-sm text-red-700">{scanError instanceof Error ? scanError.message : String(scanError)}</p>
      </Card>
    );
  }
  if (!scan) return null;

  const summary = scan.summary ?? {};

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold">{scan.name ?? `Scan #${scan.id}`}</h1>
          <div className="mt-1 flex items-center gap-3 text-sm text-slate-500">
            <StatusBadge value={scan.status} />
            <span>Started {formatDateTime(scan.started_at)}</span>
            {scan.ended_at && <span>· Ended {formatDateTime(scan.ended_at)}</span>}
            {scan.status === "running" && (
              <button
                onClick={() => void api.cancelScan(scan.id).then(refreshAll)}
                className="rounded border border-red-200 px-2 py-0.5 text-xs text-red-700 hover:bg-red-50"
              >
                Cancel
              </button>
            )}
          </div>
        </div>
        <div className="flex gap-2">
          {scan.status === "completed" && (
            <>
              <button
                onClick={() => void api.rerunScan(scan.id)}
                className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-medium hover:bg-slate-50"
              >
                Rerun
              </button>
              <a
                href={`/api/reports/${scan.id}/html`}
                target="_blank"
                rel="noreferrer"
                className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700"
              >
                HTML Report
              </a>
            </>
          )}
        </div>
      </div>

      <div className="grid grid-cols-6 gap-4">
        <StatCard label="Total" value={counts.total ?? summary.total ?? 0} />
        <StatCard label="Success" value={counts.success ?? summary.success ?? 0} accent="bg-red-500" />
        <StatCard label="Partial" value={counts.partial ?? summary.partial ?? 0} accent="bg-amber-500" />
        <StatCard label="Blocked" value={counts.blocked ?? summary.blocked ?? 0} accent="bg-emerald-500" />
        <StatCard label="Uncertain" value={counts.uncertain ?? summary.uncertain ?? 0} accent="bg-slate-400" />
        <StatCard label="Avg conf" value={formatRatio(avgConf || summary.avg_confidence || 0)} />
      </div>

      <Card title="Overall risk" subtitle="Aggregated from findings and result classifications">
        <RiskBadge value={scan.summary?.overall_risk ?? "unknown"} />
      </Card>

      <div>
        <Tabs
          tabs={[
            { key: "results", label: "Results", count: results?.length },
            { key: "findings", label: "Findings", count: findings?.length ?? scan.summary?.error },
          ]}
          active={tab}
          onChange={setTab}
        />

        <div className="mt-4">
          {tab === "results" && (
            <ResultsTable
              results={results ?? []}
              resultsError={resultsError}
              running={running}
              onRefresh={() => void refreshAll()}
            />
          )}
          {tab === "findings" &&
            (findings && findings.length > 0 ? (
              <div className="space-y-4">
                {findings.map((f) => (
                  <FindingCard key={f.id} finding={f} />
                ))}
              </div>
            ) : (
              <Card>
                <p className="text-sm text-slate-600">
                  {running ? "Findings will appear when the scan completes." : "No confirmed vulnerabilities."}
                </p>
              </Card>
            ))}
        </div>
      </div>
    </div>
  );
}

function ResultsTable({
  results,
  resultsError,
  running,
  onRefresh,
}: {
  results: TestResult[];
  resultsError: string | null;
  running: boolean;
  onRefresh: () => void;
}) {
  const [filter, setFilter] = useState<Classification | "all">("all");
  const [severity, setSeverity] = useState<string>("all");

  const visible = results.filter(
    (r) =>
      (filter === "all" || r.classification === filter) &&
      (severity === "all" || r.severity === severity),
  );

  if (resultsError) {
    return (
      <Card title="Results">
        <p className="text-sm text-red-700">{resultsError}</p>
      </Card>
    );
  }

  if (running && results.length === 0) {
    return (
      <Card title="Running scan" subtitle="Attacks are being executed against the target">
        <Spinner label="Executing attacks…" />
        <p className="text-center text-xs text-slate-400">Results stream in as each test completes.</p>
        <div className="mt-4 text-center">
          <button
            onClick={onRefresh}
            className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium hover:bg-slate-50"
          >
            Refresh now
          </button>
        </div>
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <select
          className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm"
          value={filter}
          onChange={(e) => setFilter(e.target.value as Classification | "all")}
        >
          <option value="all">All classifications</option>
          <option value="success">Success</option>
          <option value="partial">Partial</option>
          <option value="blocked">Blocked</option>
          <option value="uncertain">Uncertain</option>
          <option value="error">Error</option>
        </select>
        <select
          className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm"
          value={severity}
          onChange={(e) => setSeverity(e.target.value)}
        >
          <option value="all">All severities</option>
          <option value="critical">Critical</option>
          <option value="high">High</option>
          <option value="medium">Medium</option>
          <option value="low">Low</option>
          <option value="info">Info</option>
        </select>
        {running && (
          <button
            onClick={onRefresh}
            className="ml-auto rounded-lg border border-slate-300 px-4 py-1.5 text-sm font-medium hover:bg-slate-50"
          >
            Refresh now
          </button>
        )}
        <span className="text-xs text-slate-400">{visible.length} shown</span>
      </div>

      <Card>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-slate-200 text-xs uppercase tracking-wide text-slate-500">
                <th className="py-2 pr-3 font-medium">#</th>
                <th className="py-2 pr-3 font-medium">Attack</th>
                <th className="py-2 pr-3 font-medium">Category</th>
                <th className="py-2 pr-3 font-medium">Classification</th>
                <th className="py-2 pr-3 font-medium">Severity</th>
                <th className="py-2 pr-3 font-medium">Confidence</th>
                <th className="py-2 pr-3 font-medium text-right">Latency</th>
              </tr>
            </thead>
            <tbody>
              {visible.map((r) => (
                <tr key={r.id} className="border-b border-slate-100 hover:bg-slate-50">
                  <td className="py-2.5 pr-3 text-xs text-slate-400">{r.id}</td>
                  <td className="max-w-[220px] py-2.5 pr-3">
                    <div className="truncate font-medium text-slate-900" title={r.payload}>
                      {String(r.attack_meta?.id ?? r.attack_id)}
                    </div>
                    <div className="truncate text-xs text-slate-500" title={r.payload}>
                      {truncate(r.payload, 80)}
                    </div>
                  </td>
                  <td className="py-2.5 pr-3 text-slate-600">{String(r.attack_meta?.category ?? "—")}</td>
                  <td className="py-2.5 pr-3">
                    <ClassificationBadge value={r.classification} />
                  </td>
                  <td className="py-2.5 pr-3">
                    <SeverityBadge value={r.severity} />
                  </td>
                  <td className="py-2.5 pr-3">
                    <ConfidenceBar
                      value={r.confidence}
                      tone={r.classification === "success" ? "red" : r.classification === "blocked" ? "emerald" : r.classification === "partial" ? "amber" : "slate"}
                    />
                  </td>
                  <td className="py-2.5 text-right text-xs tabular-nums text-slate-500">
                    {formatDuration(r.latency_ms)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}

function FindingCard({ finding }: { finding: Finding }) {
  return (
    <Card
      title={
        <span className="flex items-center gap-2">
          {finding.title}
          <SeverityBadge value={finding.severity} />
        </span>
      }
      subtitle={finding.attack_objective}
    >
      <div className="space-y-3 text-sm">
        <div className="flex flex-wrap gap-x-6 gap-y-1 text-xs text-slate-500">
          <span>
            Attack: <b className="text-slate-700">{finding.attack_id ?? "—"}</b>
          </span>
          <span>
            Confidence: <b className="text-slate-700">{formatRatio(finding.confidence)}</b>
          </span>
        </div>
        {finding.payload && (
          <div>
            <div className="mb-1 text-xs font-medium text-slate-500">Payload</div>
            <pre className="rounded-lg bg-slate-900 px-3 py-2 text-xs text-slate-100">{finding.payload}</pre>
          </div>
        )}
        {finding.target_response && (
          <div>
            <div className="mb-1 text-xs font-medium text-slate-500">Target response</div>
            <pre className="rounded-lg bg-slate-100 px-3 py-2 text-xs text-slate-800">
              {truncate(finding.target_response, 2000)}
            </pre>
          </div>
        )}
        {finding.violated_boundary && (
          <p>
            <span className="font-medium text-slate-600">Violated boundary: </span>
            {finding.violated_boundary}
          </p>
        )}
        {finding.root_cause && (
          <p>
            <span className="font-medium text-slate-600">Root cause: </span>
            {finding.root_cause}
          </p>
        )}
        {finding.remediation && (
          <div className="rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-800">
            <span className="font-semibold">Remediation: </span>
            {finding.remediation}
          </div>
        )}
      </div>
    </Card>
  );
}