import { useEffect, useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { api } from "../api/client";
import Card from "../components/Card";
import EmptyState from "../components/EmptyState";
import Spinner from "../components/Spinner";
import type { AttackCatalog, Target } from "../types/models";

export default function NewScan() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const preselectId = Number(searchParams.get("target")) || 0;

  const [targets, setTargets] = useState<Target[] | null>(null);
  const [catalog, setCatalog] = useState<AttackCatalog | null>(null);
  const [targetId, setTargetId] = useState<number>(preselectId);
  const [name, setName] = useState("");
  const [selectedCategories, setSelectedCategories] = useState<string[]>([]);
  const [maxAttacks, setMaxAttacks] = useState(50);
  const [concurrency, setConcurrency] = useState(5);
  const [mutationCount, setMutationCount] = useState(3);
  const [maxTurns, setMaxTurns] = useState(3);
  const [rateLimit, setRateLimit] = useState(10);
  const [includeGenerated, setIncludeGenerated] = useState(true);
  const [includeMutations, setIncludeMutations] = useState(true);
  const [multiTurn, setMultiTurn] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    void Promise.all([api.listTargets(), api.getCatalog()])
      .then(([t, c]) => {
        setTargets(t);
        setCatalog(c);
        setSelectedCategories(c.default_categories ?? []);
        if (!targetId && t.length > 0) setTargetId(t[0].id);
      })
      .catch((err) => setError(err instanceof Error ? err.message : String(err)));
  }, [targetId]);

  const allCategories = useMemo(() => catalog?.categories ?? {}, [catalog]);

  const toggleCategory = (cat: string) =>
    setSelectedCategories((prev) =>
      prev.includes(cat) ? prev.filter((c) => c !== cat) : [...prev, cat],
    );

  const submit = async () => {
    setError(null);
    if (!targetId) {
      setError("Please select a target.");
      return;
    }
    if (selectedCategories.length === 0) {
      setError("Select at least one attack category.");
      return;
    }
    setSubmitting(true);
    try {
      const scan = await api.createScan({
        target_id: targetId,
        name: name.trim() || null,
        config: {
          attack_categories: selectedCategories,
          max_attacks: maxAttacks,
          concurrency,
          include_generated: includeGenerated,
          include_mutations: includeMutations,
          mutation_count_per_attack: mutationCount,
          multi_turn_enabled: multiTurn,
          max_turns: maxTurns,
          rate_limit_per_second: rateLimit,
        },
      });
      navigate(`/scans/${scan.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setSubmitting(false);
    }
  };

  if (!targets || !catalog) return error ? <ErrorBox msg={error} /> : <Spinner label="Loading scan options…" />;

  const attackCountForSelected =
    catalog.attacks.filter((a) => selectedCategories.includes(a.category)).length;

  return (
    <div className="max-w-4xl space-y-6">
      <div>
        <h1 className="text-xl font-bold">Configure Scan</h1>
        <p className="text-sm text-slate-500">Choose a target and the attack surface to probe</p>
      </div>

      {targets.length === 0 ? (
        <EmptyState
          title="No targets available"
          hint="Create a target before running a scan."
          action={
            <button
              onClick={() => navigate("/targets/new")}
              className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700"
            >
              Add a target
            </button>
          }
        />
      ) : (
        <>
          <Card title="Target" subtitle="Endpoint the attacks will be sent to">
            <label className="block">
              <span className="text-xs font-medium text-slate-600">AI endpoint</span>
              <select
                className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
                value={targetId}
                onChange={(e) => setTargetId(Number(e.target.value))}
              >
                {targets.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.name} — {t.url}
                  </option>
                ))}
              </select>
            </label>
            <label className="mt-4 block">
              <span className="text-xs font-medium text-slate-600">Scan name (optional)</span>
              <input
                className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
                placeholder={`Scan #… of ${targets.find((t) => t.id === targetId)?.name ?? "target"}`}
                value={name}
                onChange={(e) => setName(e.target.value)}
              />
            </label>
          </Card>

          <Card
            title="Attack categories"
            subtitle={`${selectedCategories.length} selected · ${attackCountForSelected} reference attacks in scope`}
          >
            <div className="grid grid-cols-2 gap-2">
              {Object.entries(allCategories).map(([key, label]) => {
                const count = catalog.attacks.filter((a) => a.category === key).length;
                const checked = selectedCategories.includes(key);
                return (
                  <label
                    key={key}
                    className={`flex items-center justify-between rounded-lg border px-3 py-2.5 text-sm cursor-pointer ${
                      checked ? "border-slate-900 bg-slate-50" : "border-slate-200 hover:bg-slate-50"
                    }`}
                  >
                    <span className="flex items-center gap-2">
                      <input
                        type="checkbox"
                        checked={checked}
                        onChange={() => toggleCategory(key)}
                        className="h-4 w-4 rounded border-slate-300"
                      />
                      <span className="font-medium text-slate-800">{label}</span>
                    </span>
                    <span className="text-xs text-slate-400">{count}</span>
                  </label>
                );
              })}
            </div>
          </Card>

          <Card title="Execution settings">
            <div className="grid grid-cols-3 gap-4">
              <label className="block">
                <span className="text-xs font-medium text-slate-600">Max attacks</span>
                <input
                  type="number"
                  min={1}
                  max={500}
                  className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
                  value={maxAttacks}
                  onChange={(e) => setMaxAttacks(Number(e.target.value))}
                />
              </label>
              <label className="block">
                <span className="text-xs font-medium text-slate-600">Concurrency</span>
                <input
                  type="number"
                  min={1}
                  max={32}
                  className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
                  value={concurrency}
                  onChange={(e) => setConcurrency(Number(e.target.value))}
                />
              </label>
              <label className="block">
                <span className="text-xs font-medium text-slate-600">Rate limit (req/s)</span>
                <input
                  type="number"
                  min={0.1}
                  max={100}
                  step={0.5}
                  className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
                  value={rateLimit}
                  onChange={(e) => setRateLimit(Number(e.target.value))}
                />
              </label>
              <label className="block">
                <span className="text-xs font-medium text-slate-600">Mutations per attack</span>
                <input
                  type="number"
                  min={0}
                  max={10}
                  className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
                  value={mutationCount}
                  onChange={(e) => setMutationCount(Number(e.target.value))}
                />
              </label>
              <label className="block">
                <span className="text-xs font-medium text-slate-600">Max multi-turn depth</span>
                <input
                  type="number"
                  min={1}
                  max={10}
                  className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
                  value={maxTurns}
                  onChange={(e) => setMaxTurns(Number(e.target.value))}
                />
              </label>
            </div>
            <div className="mt-4 space-y-2">
              {(
                [
                  ["include_generated", includeGenerated, setIncludeGenerated, "Generate additional attacks with the LLM generator when configured"],
                  ["include_mutations", includeMutations, setIncludeMutations, "Create obfuscation variants of each base attack"],
                  ["multi_turn", multiTurn, setMultiTurn, "Probe multi-turn injection (follow-up hijacking, context confusion)"],
                ] as const
              ).map(([key, value, setter, hint]) => (
                <label key={key} className="flex items-start gap-2 text-sm text-slate-700">
                  <input
                    type="checkbox"
                    checked={value}
                    onChange={(e) => setter(e.target.checked)}
                    className="mt-0.5 h-4 w-4 rounded border-slate-300"
                  />
                  <span>
                    {key === "include_generated"
                      ? "Include generated attacks"
                      : key === "include_mutations"
                        ? "Include mutations"
                        : "Multi-turn attacks"}
                    <span className="block text-xs text-slate-400">{hint}</span>
                  </span>
                </label>
              ))}
            </div>
          </Card>

          {error && (
            <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>
          )}

          <div className="flex justify-end gap-3">
            <button
              onClick={() => navigate(-1)}
              className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium hover:bg-slate-50"
            >
              Cancel
            </button>
            <button
              onClick={() => void submit()}
              disabled={submitting}
              className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700 disabled:opacity-50"
            >
              {submitting ? "Starting…" : "Start scan"}
            </button>
          </div>
        </>
      )}
    </div>
  );
}

function ErrorBox({ msg }: { msg: string }) {
  return (
    <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{msg}</div>
  );
}