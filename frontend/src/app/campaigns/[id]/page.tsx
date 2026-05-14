"use client";

import { use, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { openEventStream } from "@/lib/sse";
import type { PipelineEvent } from "@/lib/types";

type ChildState = {
  id: string;
  index: number;
  status: "queued" | "running" | "done" | "error" | "cancelled" | "cost_capped";
  current_b64: string | null;
  final_b64: string | null;
  iteration: number;
  total_iterations: number;
  cost: number;
  error?: string | null;
};

type ChildEvent = PipelineEvent & { child_id?: string };

export default function CampaignPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  return <CampaignView campaignId={id} />;
}

function CampaignView({ campaignId }: { campaignId: string }) {
  const [children, setChildren] = useState<Record<string, ChildState>>({});
  const [order, setOrder] = useState<string[]>([]);
  const [done, setDone] = useState(false);
  const counter = useRef(0);

  useEffect(() => {
    function handle(event: ChildEvent) {
      if (event.type === "child_queued") {
        setChildren((prev) => ({
          ...prev,
          [event.child_id]: {
            id: event.child_id,
            index: event.index,
            status: "queued",
            current_b64: null,
            final_b64: null,
            iteration: 0,
            total_iterations: 0,
            cost: 0,
          },
        }));
        setOrder((prev) => [...prev, event.child_id]);
        return;
      }
      if (event.type === "batch_done") {
        setDone(true);
        return;
      }
      if (event.type === "child_terminal") {
        return;
      }
      const cid = event.child_id;
      if (!cid) return;
      setChildren((prev) => {
        const c = prev[cid] ?? {
          id: cid,
          index: counter.current++,
          status: "running" as const,
          current_b64: null,
          final_b64: null,
          iteration: 0,
          total_iterations: 0,
          cost: 0,
        };
        const next: ChildState = { ...c, status: "running" };
        switch (event.type) {
          case "gen_start":
            next.iteration = event.iteration;
            next.total_iterations = event.max;
            break;
          case "gen_done":
            next.current_b64 = event.image_b64;
            next.cost = event.cost_so_far;
            break;
          case "critique_done":
          case "placement_done":
            next.cost = event.cost_so_far;
            break;
          case "render_done":
            next.final_b64 = event.final_b64;
            next.cost = event.total_cost;
            next.status = "done";
            break;
          case "cost_cap_hit":
            next.cost = event.cost_so_far;
            next.status = "cost_capped";
            break;
          case "cancelled":
            next.status = "cancelled";
            break;
          case "error":
            next.status = "error";
            next.error = event.message;
            break;
        }
        return { ...prev, [cid]: next };
      });
    }

    const close = openEventStream(
      api.batchEventsUrl(campaignId),
      (raw) => handle(raw as ChildEvent),
      () => setDone(true),
    );
    return close;
  }, [campaignId]);

  const list = order.map((cid) => children[cid]).filter(Boolean);
  const totalCost = list.reduce((s, c) => s + c.cost, 0);

  return (
    <div className="mx-auto max-w-7xl px-6 py-10">
      <div className="mb-6 flex items-center justify-between">
        <Link href="/" className="text-sm text-neutral-500 hover:text-neutral-900">
          ← Gallery
        </Link>
        <div className="text-xs font-mono text-neutral-500">
          campaign {campaignId}
        </div>
      </div>

      <div className="flex items-baseline justify-between mb-6">
        <h1 className="text-2xl font-semibold tracking-tight">
          {done ? "Campaign complete" : "Running campaign…"}
        </h1>
        <div className="flex items-center gap-4">
          <div className="text-sm">
            <span className="text-neutral-500">Total cost: </span>
            <span className="font-mono">${totalCost.toFixed(4)}</span>
          </div>
          {done && (
            <a
              href={api.downloadUrl(campaignId, "bundle.zip")}
              className="rounded-md bg-neutral-900 text-white px-4 py-2 text-sm hover:bg-neutral-700"
            >
              Download all (.zip)
            </a>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {list.map((c) => (
          <Link
            key={c.id}
            href={`/jobs/${c.id}`}
            className="rounded-lg bg-white border border-neutral-200 overflow-hidden hover:shadow-md transition-shadow"
          >
            <div className="aspect-square bg-neutral-100 relative">
              {c.final_b64 ? (
                <img
                  src={`data:image/png;base64,${c.final_b64}`}
                  alt={c.id}
                  className="absolute inset-0 w-full h-full object-cover"
                />
              ) : c.current_b64 ? (
                <img
                  src={`data:image/png;base64,${c.current_b64}`}
                  alt={c.id}
                  className="absolute inset-0 w-full h-full object-cover opacity-70"
                />
              ) : (
                <div className="absolute inset-0 flex items-center justify-center text-neutral-400 text-sm">
                  queued…
                </div>
              )}
            </div>
            <div className="p-3 flex items-center justify-between">
              <span className="text-xs font-mono text-neutral-500">
                #{c.index + 1}
              </span>
              <StatusPill status={c.status} iteration={c.iteration} total={c.total_iterations} />
              <span className="text-xs font-mono">${c.cost.toFixed(3)}</span>
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}

function StatusPill({
  status,
  iteration,
  total,
}: {
  status: ChildState["status"];
  iteration: number;
  total: number;
}) {
  const map = {
    queued: { label: "Queued", cls: "bg-neutral-100 text-neutral-700" },
    running: {
      label: total ? `Iter ${iteration}/${total}` : "Running",
      cls: "bg-sky-100 text-sky-800",
    },
    done: { label: "Done", cls: "bg-emerald-100 text-emerald-800" },
    error: { label: "Error", cls: "bg-rose-100 text-rose-800" },
    cancelled: { label: "Cancelled", cls: "bg-amber-100 text-amber-800" },
    cost_capped: { label: "Capped", cls: "bg-amber-100 text-amber-800" },
  } as const;
  const { label, cls } = map[status];
  return (
    <span className={`text-xs rounded px-2 py-0.5 ${cls}`}>{label}</span>
  );
}
