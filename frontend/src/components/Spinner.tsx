export default function Spinner({ label }: { label?: string }) {
  return (
    <div className="flex items-center justify-center gap-3 py-12 text-slate-500">
      <svg className="h-6 w-6 animate-spin text-slate-400" viewBox="0 0 24 24" fill="none">
        <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" opacity="0.25" />
        <path
          d="M12 2a10 10 0 0 1 10 10"
          stroke="currentColor"
          strokeWidth="4"
          strokeLinecap="round"
        />
      </svg>
      {label && <span className="text-sm">{label}</span>}
    </div>
  );
}