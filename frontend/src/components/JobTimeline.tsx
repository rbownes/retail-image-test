"use client";
import type { PipelineEvent } from "@/lib/types";

export type TimelineEntry = {
  id: number;
  kind: PipelineEvent["type"];
  label: string;
  detail?: string;
  severity?: "neutral" | "good" | "warn" | "bad";
  cost?: number;
};

export function buildTimelineEntry(
  event: PipelineEvent,
  id: number,
): TimelineEntry | null {
  switch (event.type) {
    case "gen_start":
      return {
        id,
        kind: event.type,
        label: `Generating image ${event.iteration}/${event.max}`,
        detail: event.prompt.slice(0, 140) + (event.prompt.length > 140 ? "…" : ""),
        severity: "neutral",
      };
    case "gen_done":
      return {
        id,
        kind: event.type,
        label: `Image ${event.iteration} generated`,
        cost: event.cost_so_far,
        severity: "good",
      };
    case "critique_start":
      return {
        id,
        kind: event.type,
        label: `Critiquing iteration ${event.iteration}`,
        severity: "neutral",
      };
    case "critique_done":
      return {
        id,
        kind: event.type,
        label: `Critique: ${event.critique.severity}${
          event.critique.is_acceptable ? " — accepted" : " — regenerating"
        }`,
        detail:
          event.critique.issues.length > 0
            ? event.critique.issues.join("; ")
            : event.critique.reasoning?.slice(0, 200),
        severity: event.critique.is_acceptable ? "good" : "warn",
        cost: event.cost_so_far,
      };
    case "critique_failed":
      return {
        id,
        kind: event.type,
        label: `Critique failed — accepting current image`,
        detail: event.message,
        severity: "warn",
      };
    case "max_iterations_reached":
      return {
        id,
        kind: event.type,
        label: `Reached iteration cap`,
        detail: event.warning,
        severity: "warn",
      };
    case "placement_start":
      return {
        id,
        kind: event.type,
        label: "Placing copy",
        severity: "neutral",
      };
    case "placement_done":
      return {
        id,
        kind: event.type,
        label: "Copy placement decided",
        detail: (event.spec as { reasoning?: string }).reasoning,
        severity: "good",
        cost: event.cost_so_far,
      };
    case "render_done":
      return {
        id,
        kind: event.type,
        label: "Final composite ready",
        severity: "good",
        cost: event.total_cost,
      };
    case "cost_cap_hit":
      return {
        id,
        kind: event.type,
        label: `Cost cap hit at $${event.cost_so_far.toFixed(4)} (cap $${event.cap.toFixed(4)})`,
        severity: "warn",
        cost: event.cost_so_far,
      };
    case "cancelled":
      return {
        id,
        kind: event.type,
        label: "Cancelled",
        severity: "warn",
      };
    case "error":
      return {
        id,
        kind: event.type,
        label: `Error at ${event.stage}`,
        detail: event.message,
        severity: "bad",
      };
    default:
      return null;
  }
}

const SEV_STYLES = {
  neutral: "bg-neutral-100 text-neutral-700 border-neutral-200",
  good: "bg-emerald-50 text-emerald-800 border-emerald-200",
  warn: "bg-amber-50 text-amber-900 border-amber-200",
  bad: "bg-rose-50 text-rose-900 border-rose-200",
} as const;

export function JobTimeline({ entries }: { entries: TimelineEntry[] }) {
  return (
    <ol className="space-y-2">
      {entries.map((e) => (
        <li
          key={e.id}
          className={`rounded-md border px-3 py-2 ${
            SEV_STYLES[e.severity ?? "neutral"]
          }`}
        >
          <div className="flex items-baseline justify-between gap-2">
            <span className="text-sm font-medium">{e.label}</span>
            {typeof e.cost === "number" && (
              <span className="text-xs font-mono opacity-70">
                ${e.cost.toFixed(4)}
              </span>
            )}
          </div>
          {e.detail && (
            <div className="text-xs mt-1 opacity-80 leading-snug">{e.detail}</div>
          )}
        </li>
      ))}
    </ol>
  );
}
