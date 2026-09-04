export default function Tabs({
  tabs,
  active,
  onChange,
}: {
  tabs: { key: string; label: string; count?: number }[];
  active: string;
  onChange: (key: string) => void;
}) {
  return (
    <div className="flex gap-1 border-b border-slate-200">
      {tabs.map((tab) => (
        <button
          key={tab.key}
          onClick={() => onChange(tab.key)}
          className={`-mb-px rounded-t-lg border-b-2 px-4 py-2.5 text-sm font-medium ${
            active === tab.key
              ? "border-slate-900 text-slate-900"
              : "border-transparent text-slate-500 hover:text-slate-700"
          }`}
        >
          {tab.label}
          {typeof tab.count === "number" && (
            <span className="ml-2 rounded-full bg-slate-100 px-2 py-0.5 text-xs tabular-nums">
              {tab.count}
            </span>
          )}
        </button>
      ))}
    </div>
  );
}