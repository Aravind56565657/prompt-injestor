import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import Card from "../components/Card";
import EmptyState from "../components/EmptyState";
import Spinner from "../components/Spinner";
import { formatDateTime, truncate } from "../lib/format";
import type { Target } from "../types/models";

export default function Targets() {
  const [targets, setTargets] = useState<Target[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<number | null>(null);

  const load = useCallback(async () => {
    try {
      setTargets(await api.listTargets());
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const remove = async (id: number) => {
    if (!window.confirm("Delete this target? Existing scans are kept.")) return;
    setBusyId(id);
    try {
      await api.deleteTarget(id);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusyId(null);
    }
  };

  if (error) {
    return (
      <Card title="Error">
        <p className="text-sm text-red-700">{error}</p>
      </Card>
    );
  }
  if (!targets) return <Spinner label="Loading targets…" />;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold">Targets</h1>
          <p className="text-sm text-slate-500">AI endpoints you scan for prompt-injection vulnerabilities</p>
        </div>
        <Link
          to="/targets/new"
          className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700"
        >
          Add Target
        </Link>
      </div>

      {targets.length === 0 ? (
        <EmptyState
          title="No targets yet"
          hint="Add your first AI endpoint so you can run prompt-injection scans against it."
          action={
            <Link
              to="/targets/new"
              className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700"
            >
              Add a target
            </Link>
          }
        />
      ) : (
        <Card>
          <div className="divide-y divide-slate-100">
            {targets.map((target) => (
              <div key={target.id} className="flex items-center justify-between py-4">
                <div className="min-w-0 pr-4">
                  <div className="flex items-center gap-2">
                    <span className="font-semibold text-slate-900">{target.name}</span>
                    <span className="rounded bg-slate-100 px-1.5 py-0.5 text-xs text-slate-500">
                      {target.adapter_type}
                    </span>
                    <span className="rounded bg-slate-100 px-1.5 py-0.5 text-xs text-slate-500">
                      {target.http_method}
                    </span>
                  </div>
                  <div className="mt-1 truncate text-sm text-slate-500">{target.url}</div>
                  {target.description && (
                    <div className="mt-0.5 text-xs text-slate-400">{truncate(target.description, 120)}</div>
                  )}
                  <div className="mt-1 text-xs text-slate-400">
                    payload_path: <code className="rounded bg-slate-100 px-1">{target.payload_path}</code>
                    {target.response_path && (
                      <>
                        {" · "}response_path: <code className="rounded bg-slate-100 px-1">{target.response_path}</code>
                      </>
                    )}
                    {" · "}added {formatDateTime(target.created_at)}
                  </div>
                </div>
                <div className="flex shrink-0 items-center gap-2">
                  <Link
                    to={`/scans/new?target=${target.id}`}
                    className="rounded-lg border border-slate-300 px-3 py-1.5 text-xs font-medium hover:bg-slate-50"
                  >
                    Scan
                  </Link>
                  <button
                    onClick={() => void remove(target.id)}
                    disabled={busyId === target.id}
                    className="rounded-lg border border-red-200 px-3 py-1.5 text-xs font-medium text-red-700 hover:bg-red-50 disabled:opacity-50"
                  >
                    {busyId === target.id ? "Deleting…" : "Delete"}
                  </button>
                </div>
              </div>
            ))}
          </div>
        </Card>
      )}
    </div>
  );
}