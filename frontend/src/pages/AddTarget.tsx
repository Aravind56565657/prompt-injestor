import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import Card from "../components/Card";

const AUTH_TYPES = ["none", "bearer", "api_key", "basic"];
const METHODS = ["POST", "GET", "PUT", "PATCH", "DELETE"];
const ADAPTERS = ["http", "openai", "mock"];

const initialState = {
  name: "",
  description: "",
  url: "",
  http_method: "POST",
  auth_type: "none",
  auth_token: "",
  payload_path: "message",
  response_path: "",
  adapter_type: "http",
  headersRaw: "",
  requestTemplateRaw: "",
  timeout: 30,
  retry_count: 2,
};

export default function AddTarget() {
  const navigate = useNavigate();
  const [form, setForm] = useState(initialState);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const set = (key: keyof typeof initialState, value: string | number) =>
    setForm((prev) => ({ ...prev, [key]: value }));

  const submit = async () => {
    setError(null);
    if (!form.name.trim() || !form.url.trim()) {
      setError("Name and URL are required.");
      return;
    }
    let headers: Record<string, string> = {};
    let request_template: Record<string, unknown> = {};
    try {
      if (form.headersRaw.trim()) headers = JSON.parse(form.headersRaw);
      if (form.requestTemplateRaw.trim()) request_template = JSON.parse(form.requestTemplateRaw);
    } catch {
      setError("Headers and request template must be valid JSON objects.");
      return;
    }
    setSaving(true);
    try {
      const target = await api.createTarget({
        name: form.name.trim(),
        description: form.description.trim() || null,
        url: form.url.trim(),
        http_method: form.http_method,
        adapter_type: form.adapter_type,
        auth_type: form.auth_type,
        auth_token: form.auth_token || null,
        headers,
        request_template,
        payload_path: form.payload_path.trim() || "message",
        response_path: form.response_path.trim() || null,
        timeout: Number(form.timeout),
        retry_count: Number(form.retry_count),
      });
      navigate(`/scans/new?target=${target.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setSaving(false);
    }
  };

  const field = (label: string, key: keyof typeof initialState, props: React.InputHTMLAttributes<HTMLInputElement> = {}) => (
    <label className="block">
      <span className="text-xs font-medium text-slate-600">{label}</span>
      <input
        className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none"
        value={String(form[key] ?? "")}
        onChange={(e) => set(key, e.target.value)}
        {...props}
      />
    </label>
  );

  return (
    <div className="max-w-3xl space-y-6">
      <div>
        <h1 className="text-xl font-bold">Add Target</h1>
        <p className="text-sm text-slate-500">Register an AI endpoint to scan</p>
      </div>

      <Card title="Endpoint">
        <div className="grid grid-cols-2 gap-4">
          {field("Name *", "name", { placeholder: "e.g. Production RAG assistant" })}
          {field("Description", "description", { placeholder: "Optional context about this target" })}
          <div className="col-span-2">
            {field("URL *", "url", { placeholder: "http://localhost:8001/chat" })}
          </div>
          <label className="block">
            <span className="text-xs font-medium text-slate-600">HTTP method</span>
            <select
              className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
              value={form.http_method}
              onChange={(e) => set("http_method", e.target.value)}
            >
              {METHODS.map((m) => (
                <option key={m}>{m}</option>
              ))}
            </select>
          </label>
          <label className="block">
            <span className="text-xs font-medium text-slate-600">Adapter type</span>
            <select
              className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
              value={form.adapter_type}
              onChange={(e) => set("adapter_type", e.target.value)}
            >
              {ADAPTERS.map((m) => (
                <option key={m}>{m}</option>
              ))}
            </select>
          </label>
        </div>
      </Card>

      <Card title="Payload mapping">
        <div className="grid grid-cols-2 gap-4">
          {field("Payload path", "payload_path", { placeholder: "message" })}
          {field("Response path", "response_path", { placeholder: "answer (optional)" })}
        </div>
        <p className="mt-2 text-xs text-slate-500">
          Payload path is the JSON key where attack messages are injected. Response path extracts the assistant text
          from the JSON reply. Supports dot-notation for nested keys.
        </p>
      </Card>

      <Card title="Authentication">
        <div className="grid grid-cols-2 gap-4">
          <label className="block">
            <span className="text-xs font-medium text-slate-600">Auth type</span>
            <select
              className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
              value={form.auth_type}
              onChange={(e) => set("auth_type", e.target.value)}
            >
              {AUTH_TYPES.map((m) => (
                <option key={m}>{m}</option>
              ))}
            </select>
          </label>
          {form.auth_type !== "none" && (
            <label className="block">
              <span className="text-xs font-medium text-slate-600">Secret/token</span>
              <input
                className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
                placeholder={form.auth_type === "basic" ? "Basic base64 or leave empty" : "Token value"}
                value={form.auth_token}
                onChange={(e) => set("auth_token", e.target.value)}
              />
            </label>
          )}
          <label className="block">
            <span className="text-xs font-medium text-slate-600">Custom headers (JSON object)</span>
            <input
              className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 font-mono text-xs"
              placeholder='{"X-API-Key": "..."}'
              value={form.headersRaw}
              onChange={(e) => set("headersRaw", e.target.value)}
            />
          </label>
          <label className="block">
            <span className="text-xs font-medium text-slate-600">Request template (JSON object)</span>
            <input
              className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 font-mono text-xs"
              placeholder='{"model": "gpt-4o", "temperature": 0}'
              value={form.requestTemplateRaw}
              onChange={(e) => set("requestTemplateRaw", e.target.value)}
            />
          </label>
        </div>
        <p className="mt-2 text-xs text-slate-500">
          Secrets are stored locally for the scanner and never sent to the reporting UI.
        </p>
      </Card>

      <Card title="Run settings">
        <div className="grid grid-cols-2 gap-4">
          {field("Timeout (s)", "timeout", { type: "number", min: 1, max: 300 })}
          {field("Retry count", "retry_count", { type: "number", min: 0, max: 10 })}
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
          disabled={saving}
          className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700 disabled:opacity-50"
        >
          {saving ? "Creating…" : "Create target"}
        </button>
      </div>
    </div>
  );
}