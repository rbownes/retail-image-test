"use client";

export function CostMeter({
  current,
  cap,
  estimate,
}: {
  current: number;
  cap?: number | null;
  estimate?: { min: number; expected: number; max: number };
}) {
  const pct = cap ? Math.min(100, (current / cap) * 100) : null;
  const overCap = cap !== undefined && cap !== null && current >= cap;
  return (
    <div className="rounded-lg border border-neutral-200 bg-white p-4">
      <div className="text-xs uppercase tracking-wide text-neutral-500">
        Cost so far
      </div>
      <div
        className={`text-3xl font-mono mt-1 ${
          overCap ? "text-rose-600" : "text-neutral-900"
        }`}
      >
        ${current.toFixed(4)}
      </div>
      {estimate && (
        <div className="mt-2 text-xs text-neutral-500">
          Est. ${estimate.min.toFixed(3)} – ${estimate.max.toFixed(3)} (typ. $
          {estimate.expected.toFixed(3)})
        </div>
      )}
      {cap !== undefined && cap !== null && (
        <>
          <div className="mt-3 h-2 rounded bg-neutral-100 overflow-hidden">
            <div
              className={`h-full transition-all ${
                overCap ? "bg-rose-500" : "bg-neutral-900"
              }`}
              style={{ width: `${pct ?? 0}%` }}
            />
          </div>
          <div className="mt-1 text-xs text-neutral-500 font-mono text-right">
            cap ${cap.toFixed(2)}
          </div>
        </>
      )}
    </div>
  );
}
