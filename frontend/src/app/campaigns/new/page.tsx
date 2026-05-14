"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import type { BrandKit, Estimate, Template } from "@/lib/types";

type Brief = {
  brand_kit_id: string;
  template_id: string;
  prompt: string;
  copy: string;
};

function newBrief(brand?: BrandKit, tpl?: Template): Brief {
  return {
    brand_kit_id: brand?.id ?? "",
    template_id: tpl?.id ?? brand?.default_template ?? "",
    prompt: "",
    copy: "",
  };
}

export default function NewCampaignPage() {
  const router = useRouter();
  const [name, setName] = useState("Untitled campaign");
  const [briefs, setBriefs] = useState<Brief[]>([newBrief()]);
  const [brandKits, setBrandKits] = useState<BrandKit[]>([]);
  const [templates, setTemplates] = useState<Template[]>([]);
  const [estimate, setEstimate] = useState<Estimate | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([api.getBrandKits(), api.getTemplates()]).then(([kits, tpls]) => {
      setBrandKits(kits);
      setTemplates(tpls);
      setBriefs([newBrief(kits[0], tpls.find((t) => t.id === kits[0].default_template))]);
    });
    api.estimate({ provider: "openai", quality: "medium", max_iterations: 3 }).then(setEstimate);
  }, []);

  function update(index: number, patch: Partial<Brief>) {
    setBriefs((prev) =>
      prev.map((b, i) => (i === index ? { ...b, ...patch } : b)),
    );
  }

  function add() {
    setBriefs((prev) => [...prev, newBrief(brandKits[0], templates[0])]);
  }
  function duplicate(i: number) {
    setBriefs((prev) => [...prev.slice(0, i + 1), { ...prev[i] }, ...prev.slice(i + 1)]);
  }
  function remove(i: number) {
    setBriefs((prev) => prev.filter((_, idx) => idx !== i));
  }

  const totalEstimate = estimate ? estimate.expected * briefs.length : 0;
  const totalMax = estimate ? estimate.max * briefs.length : 0;

  const canSubmit =
    !submitting &&
    briefs.length > 0 &&
    briefs.every(
      (b) => b.brand_kit_id && b.template_id && b.prompt.trim() && b.copy.trim(),
    );

  async function submit() {
    setSubmitting(true);
    setError(null);
    try {
      const { job_id } = await api.createBatchJob({
        name,
        briefs: briefs.map((b) => ({
          brand_kit_id: b.brand_kit_id,
          template_id: b.template_id,
          prompt: b.prompt,
          copy: b.copy,
        })),
      });
      router.push(`/campaigns/${job_id}`);
    } catch (e) {
      setError((e as Error).message);
      setSubmitting(false);
    }
  }

  return (
    <div className="mx-auto max-w-6xl px-6 py-10 space-y-6">
      <header>
        <h1 className="text-3xl font-semibold tracking-tight">New campaign</h1>
        <p className="text-neutral-500 mt-1">
          Author multiple briefs once, generate them as a batch, and review the
          grid.
        </p>
      </header>

      <label className="block max-w-md">
        <span className="text-sm font-medium">Campaign name</span>
        <input
          className="mt-1 w-full rounded-md border border-neutral-300 px-3 py-2 text-sm"
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
      </label>

      <div className="space-y-3">
        {briefs.map((b, i) => (
          <div
            key={i}
            className="rounded-lg border border-neutral-200 bg-white p-4 grid grid-cols-1 md:grid-cols-[1fr_1fr] gap-3"
          >
            <div className="md:col-span-2 flex items-center justify-between">
              <div className="text-xs uppercase tracking-wide text-neutral-500">
                Brief {i + 1}
              </div>
              <div className="flex gap-1 text-xs">
                <button
                  onClick={() => duplicate(i)}
                  className="px-2 py-1 rounded border border-neutral-200 hover:bg-neutral-100"
                >
                  Duplicate
                </button>
                {briefs.length > 1 && (
                  <button
                    onClick={() => remove(i)}
                    className="px-2 py-1 rounded border border-neutral-200 hover:bg-neutral-100 text-rose-600"
                  >
                    Remove
                  </button>
                )}
              </div>
            </div>

            <label className="block">
              <span className="text-xs text-neutral-500">Brand</span>
              <select
                value={b.brand_kit_id}
                onChange={(e) => update(i, { brand_kit_id: e.target.value })}
                className="mt-1 w-full rounded-md border border-neutral-300 px-2 py-1.5 text-sm"
              >
                <option value="" disabled>
                  Pick…
                </option>
                {brandKits.map((k) => (
                  <option key={k.id} value={k.id}>
                    {k.name}
                  </option>
                ))}
              </select>
            </label>

            <label className="block">
              <span className="text-xs text-neutral-500">Layout</span>
              <select
                value={b.template_id}
                onChange={(e) => update(i, { template_id: e.target.value })}
                className="mt-1 w-full rounded-md border border-neutral-300 px-2 py-1.5 text-sm"
              >
                <option value="" disabled>
                  Pick…
                </option>
                {templates.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.display_name ?? t.name}
                  </option>
                ))}
              </select>
            </label>

            <label className="block md:col-span-2">
              <span className="text-xs text-neutral-500">Image prompt</span>
              <textarea
                className="mt-1 w-full rounded-md border border-neutral-300 px-3 py-2 text-sm font-mono"
                rows={2}
                value={b.prompt}
                onChange={(e) => update(i, { prompt: e.target.value })}
              />
            </label>

            <label className="block md:col-span-2">
              <span className="text-xs text-neutral-500">Headline copy</span>
              <input
                className="mt-1 w-full rounded-md border border-neutral-300 px-3 py-2 text-sm"
                value={b.copy}
                onChange={(e) => update(i, { copy: e.target.value })}
              />
            </label>
          </div>
        ))}
        <button
          onClick={add}
          className="w-full rounded-md border border-dashed border-neutral-300 px-4 py-3 text-sm text-neutral-600 hover:bg-neutral-100"
        >
          + Add brief
        </button>
      </div>

      <footer className="flex items-center justify-between border-t border-neutral-200 pt-6">
        {estimate && (
          <div className="text-sm text-neutral-600">
            {briefs.length} brief{briefs.length === 1 ? "" : "s"} · est. total{" "}
            <span className="font-mono">
              ${totalEstimate.toFixed(2)} – ${totalMax.toFixed(2)}
            </span>
          </div>
        )}
        <button
          onClick={submit}
          disabled={!canSubmit}
          className={`rounded-md px-5 py-2 text-sm font-medium ${
            canSubmit
              ? "bg-neutral-900 text-white hover:bg-neutral-700"
              : "bg-neutral-200 text-neutral-500 cursor-not-allowed"
          }`}
        >
          {submitting ? "Submitting…" : `Run ${briefs.length} brief${briefs.length === 1 ? "" : "s"}`}
        </button>
      </footer>

      {error && (
        <div className="rounded-md border border-rose-300 bg-rose-50 px-4 py-3 text-sm text-rose-900">
          {error}
        </div>
      )}
    </div>
  );
}
