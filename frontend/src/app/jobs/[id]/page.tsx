"use client";

import { use, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { openEventStream } from "@/lib/sse";
import type { JobSummary, PipelineEvent } from "@/lib/types";
import { CostMeter } from "@/components/CostMeter";
import { JobTimeline, buildTimelineEntry, TimelineEntry } from "@/components/JobTimeline";

type Phase = "running" | "done" | "error" | "cancelled" | "cost_capped";

export default function JobPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  return <JobView jobId={id} />;
}

function JobView({ jobId }: { jobId: string }) {
  const [entries, setEntries] = useState<TimelineEntry[]>([]);
  const [currentImage, setCurrentImage] = useState<string | null>(null);
  const [finalImage, setFinalImage] = useState<string | null>(null);
  const [cost, setCost] = useState(0);
  const [phase, setPhase] = useState<Phase>("running");
  const [job, setJob] = useState<JobSummary | null>(null);
  const [warning, setWarning] = useState<string | null>(null);
  const counter = useRef(0);

  useEffect(() => {
    function handleEvent(event: PipelineEvent) {
      const entry = buildTimelineEntry(event, counter.current++);
      if (entry) setEntries((prev) => [...prev, entry]);

      switch (event.type) {
        case "gen_done":
          setCurrentImage(`data:image/png;base64,${event.image_b64}`);
          setCost(event.cost_so_far);
          break;
        case "critique_done":
        case "placement_done":
          setCost(event.cost_so_far);
          break;
        case "max_iterations_reached":
          setWarning(event.warning);
          break;
        case "render_done":
          setFinalImage(`data:image/png;base64,${event.final_b64}`);
          setCost(event.total_cost);
          setPhase("done");
          break;
        case "cost_cap_hit":
          setCost(event.cost_so_far);
          setPhase("cost_capped");
          break;
        case "cancelled":
          setPhase("cancelled");
          break;
        case "error":
          setPhase("error");
          break;
      }
    }

    const close = openEventStream(
      api.jobEventsUrl(jobId),
      handleEvent,
      async () => {
        try {
          const summary = await api.getJob(jobId);
          setJob(summary);
        } catch {}
      },
    );
    return close;
  }, [jobId]);

  function regenerate() {
    if (!job) return;
    const req = job.request as Record<string, unknown>;
    const seedSrc = typeof req.seed === "number" ? (req.seed as number) : null;
    const nextSeed = seedSrc !== null ? seedSrc + 1 : Math.floor(Math.random() * 1_000_000);
    api
      .createSingleJob({
        prompt: req.prompt as string,
        copy: req.copy as string,
        brand_kit_id: (req.brand_kit_id as string | null) ?? "",
        template_id: req.template_id as string | null,
        provider: (req.provider as "openai" | "local") ?? "openai",
        quality: (req.quality as "low" | "medium" | "high") ?? "medium",
        max_iterations: (req.max_iterations as number) ?? 3,
        seed: nextSeed,
        cost_cap_usd: (req.cost_cap_usd as number | null) ?? null,
      })
      .then(({ job_id }) => {
        window.location.assign(`/jobs/${job_id}`);
      });
  }

  return (
    <div className="mx-auto max-w-7xl px-6 py-10">
      <div className="mb-6 flex items-center justify-between">
        <Link href="/" className="text-sm text-neutral-500 hover:text-neutral-900">
          ← Gallery
        </Link>
        <div className="text-xs font-mono text-neutral-500">job {jobId}</div>
      </div>

      <h1 className="text-2xl font-semibold tracking-tight mb-1">
        {phase === "running" ? "Generating…" : phaseLabel(phase)}
      </h1>

      {warning && (
        <div className="mt-3 mb-6 rounded-md border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-900">
          {warning}
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-[2fr_1fr] gap-8 mt-6">
        <section>
          <div className="rounded-lg bg-white border border-neutral-200 overflow-hidden">
            {finalImage ? (
              <img
                src={finalImage}
                alt="final"
                className="w-full h-auto"
              />
            ) : currentImage ? (
              <img
                src={currentImage}
                alt="current iteration"
                className="w-full h-auto opacity-90"
              />
            ) : (
              <div className="aspect-square flex items-center justify-center text-neutral-400 text-sm">
                Waiting for first iteration…
              </div>
            )}
          </div>

          {phase === "done" && (
            <div className="mt-4 flex gap-2 flex-wrap">
              <a
                href={api.downloadUrl(jobId, "final")}
                className="rounded-md bg-neutral-900 text-white px-4 py-2 text-sm hover:bg-neutral-700"
              >
                Download PNG
              </a>
              <a
                href={api.downloadUrl(jobId, "spec")}
                className="rounded-md border border-neutral-300 px-4 py-2 text-sm hover:bg-neutral-100"
              >
                Download spec
              </a>
              <a
                href={api.downloadUrl(jobId, "raw")}
                className="rounded-md border border-neutral-300 px-4 py-2 text-sm hover:bg-neutral-100"
              >
                Download raw
              </a>
              <button
                onClick={regenerate}
                className="rounded-md border border-neutral-300 px-4 py-2 text-sm hover:bg-neutral-100 ml-auto"
              >
                Regenerate variant
              </button>
            </div>
          )}
        </section>

        <aside className="space-y-4">
          <CostMeter
            current={cost}
            cap={(job?.request as { cost_cap_usd?: number | null } | undefined)?.cost_cap_usd ?? undefined}
          />

          {phase === "running" && (
            <button
              onClick={async () => {
                await api.cancelJob(jobId);
              }}
              className="w-full rounded-md border border-neutral-300 px-4 py-2 text-sm hover:bg-neutral-100"
            >
              Stop
            </button>
          )}

          <div>
            <div className="text-xs uppercase tracking-wide text-neutral-500 mb-2">
              Timeline
            </div>
            <JobTimeline entries={entries} />
          </div>
        </aside>
      </div>
    </div>
  );
}

function phaseLabel(phase: Phase): string {
  switch (phase) {
    case "done":
      return "Final creative";
    case "error":
      return "Job failed";
    case "cancelled":
      return "Cancelled";
    case "cost_capped":
      return "Stopped at cost cap";
    default:
      return "Generating…";
  }
}
