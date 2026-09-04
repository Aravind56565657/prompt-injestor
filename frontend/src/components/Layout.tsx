import { useState } from "react";
import { Link, NavLink, Outlet } from "react-router-dom";
import { api, clearCreds, getStoredCreds, storeCreds } from "../api/client";

const NAV_ITEMS = [
  { to: "/", label: "Dashboard", end: true },
  { to: "/playground", label: "Live Chat Playground", end: false },
  { to: "/targets", label: "Targets", end: false },
  { to: "/scans/new", label: "New Scan", end: false },
];

export default function Layout() {
  const [serverOk, setServerOk] = useState<boolean | null>(null);
  const [showAuth, setShowAuth] = useState(Boolean(getStoredCreds()));
  const [username, setUsername] = useState(getStoredCreds()?.username ?? "");
  const [password, setPassword] = useState(getStoredCreds()?.password ?? "");
  const [authMsg, setAuthMsg] = useState<string | null>(null);

  const checkHealth = async () => {
    try {
      await api.health();
      setServerOk(true);
    } catch {
      setServerOk(false);
    }
  };

  if (serverOk === null) void checkHealth();

  const saveAuth = () => {
    if (!username || !password) {
      setAuthMsg("Enter both username and password");
      return;
    }
    storeCreds(username.trim(), password);
    setShowAuth(true);
    setAuthMsg("Saved. Requests now include Basic auth headers.");
    setServerOk(null);
    void checkHealth();
  };

  return (
    <div className="flex min-h-screen">
      <aside className="w-60 shrink-0 border-r border-slate-200 bg-white flex flex-col">
        <div className="px-5 py-5 border-b border-slate-100">
          <div className="text-lg font-bold tracking-tight">Prompt-Injection Tester</div>
          <div className="text-xs text-slate-500 mt-0.5">AI Application Security</div>
        </div>
        <nav className="flex-1 px-3 py-4 space-y-1">
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) =>
                `block rounded-md px-3 py-2 text-sm font-medium ${
                  isActive
                    ? "bg-slate-900 text-white"
                    : "text-slate-700 hover:bg-slate-100"
                }`
              }
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
        <div className="px-5 py-4 border-t border-slate-100 space-y-3">
          <div className="flex items-center justify-between">
            <span
              className={`inline-flex items-center gap-1.5 text-xs font-medium ${
                serverOk === true
                  ? "text-emerald-700"
                  : serverOk === false
                    ? "text-red-700"
                    : "text-slate-400"
              }`}
            >
              <span
                className={`h-2 w-2 rounded-full ${
                  serverOk === true
                    ? "bg-emerald-500"
                    : serverOk === false
                      ? "bg-red-500"
                      : "bg-slate-300"
                }`}
              />
              API {serverOk === true ? "online" : serverOk === false ? "offline" : "checking…"}
            </span>
            <button
              onClick={() => void checkHealth()}
              className="text-xs text-slate-400 hover:text-slate-600"
            >
              refresh
            </button>
          </div>
          <div className="rounded-md border border-slate-200 p-2">
            {showAuth ? (
              <div className="space-y-2">
                <div className="text-xs text-slate-600">
                  Basic auth active as <b>{username || "—"}</b>
                </div>
                <div className="flex gap-2">
                  <button
                    onClick={() => setShowAuth(false)}
                    className="flex-1 rounded border border-slate-300 px-2 py-1 text-xs hover:bg-slate-50"
                  >
                    Change
                  </button>
                  <button
                    onClick={() => {
                      clearCreds();
                      setShowAuth(false);
                      setUsername("");
                      setPassword("");
                      setAuthMsg(null);
                      void checkHealth();
                    }}
                    className="flex-1 rounded border border-slate-300 px-2 py-1 text-xs hover:bg-slate-50"
                  >
                    Clear
                  </button>
                </div>
              </div>
            ) : (
              <div className="space-y-2">
                <div className="text-xs text-slate-600">Enable Basic auth (optional)</div>
                <input
                  className="w-full rounded border border-slate-300 px-2 py-1 text-xs"
                  placeholder="Username"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                />
                <input
                  className="w-full rounded border border-slate-300 px-2 py-1 text-xs"
                  placeholder="Password"
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                />
                <button
                  onClick={saveAuth}
                  className="w-full rounded bg-slate-900 px-2 py-1 text-xs text-white hover:bg-slate-700"
                >
                  Save
                </button>
                {authMsg && <div className="text-[11px] text-slate-500">{authMsg}</div>}
              </div>
            )}
          </div>
        </div>
      </aside>
      <main className="flex-1 bg-slate-50">
        <div className="mx-auto max-w-6xl px-8 py-8">
          <Outlet />
        </div>
      </main>
    </div>
  );
}

export function LayoutLink({ children }: { children?: React.ReactNode }) {
  return <Link to="/">{children}</Link>;
}