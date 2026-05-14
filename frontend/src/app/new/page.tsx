"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import type { BrandKit, Template, Estimate } from "@/lib/types";
import { BrandKitCard } from "@/components/BrandKitCard";
import { TemplateCard } from "@/components/TemplateCard";

export default function NewCreativePage() {
  const router = useRouter();
  const [brandKits, setBrandKits] = useState<BrandKit[]>([]);
  const [templates, setTemplates] = useState<Template[]>([]);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [brand, setBrand] = useState<BrandKit | null>(null);
  const [template, setTemplate] = useState<Template | null>(null);
  const [prompt, setPrompt] = useState("");
  const [copy, setCopy] = useState("");
  const [advanced, setAdvanced] = useState(false);
  const [maxIterations, setMaxIterations] = useState(3);
  const [quality, setQuality] = useState<"low" | "medium" | "high">("medium");
  const [provider, setProvider] = useState<"openai" | "local">("openai");
  const [seed, setSeed] = useState<string>("");
  const [costCap, setCostCap] = useState<string>("0.50");

  const [estimate, setEstimate] = useState<Estimate | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    Promise.all([api.getBrandKits(), api.getTemplates()])
      .then(([kits, tpls]) => {
        if (cancelled) return;
        setBrandKits(kits);
        setTemplates(tpls);
      })
      .catch((e) => {
        if (cancelled) return;
        setLoadError((e as Error).message);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  // Update estimate when knobs change.
  useEffect(() => {
    let cancelled = false;
    api
      .estimate({ provider, quality, max_iterations: maxIterations })
      .then((est) => !cancelled && setEstimate(est))
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [provider, quality, maxIterations]);

  function pickBrand(picked: BrandKit) {
    setBrand(picked);
    // Auto-select the brand's default template if loaded.
    const def = templates.find((t) => t.id === picked.default_template);
    setTemplate(def ?? null);
  }

  const supportedTemplates = useMemo(() => {
    if (!brand) return templates;
    return templates.filter((t) =>
      brand.supported_templates.length === 0
        ? true
        : brand.supported_templates.includes(t.id),
    );
  }, [brand, templates]);

  const canSubmit =
    brand !== null &&
    template !== null &&
    prompt.trim().length > 0 &&
    copy.trim().length > 0 &&
    !submitting;

  async function submit() {
    if (!brand || !template) return;
    setSubmitting(true);
    setSubmitError(null);
    try {
      const { job_id } = await api.createSingleJob({
        prompt,
        copy,
        brand_kit_id: brand.id,
        template_id: template.id,
        provider,
        quality,
        max_iterations: maxIterations,
        seed: seed === "" ? null : Number(seed),
        cost_cap_usd: costCap === "" ? null : Number(costCap),
      });
      router.push(`/jobs/${job_id}`);
    } catch (e) {
      setSubmitError((e as Error).message);
      setSubmitting(false);
    }
  }

  if (loadError) {
    return (
      <div className="mx-auto max-w-4xl px-6 py-10">
        <div className="rounded-md border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-900">
          Couldn&apos;t reach the backend: <span className="font-mono">{loadError}</span>
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-5xl px-6 py-10 space-y-10">
      <header>
        <h1 className="text-3xl font-semibold tracking-tight">New creative</h1>
        <p className="text-neutral-500 mt-1">
          Pick a brand, a layout, and write the brief. The agent will iterate
          until the image is on-brand, then place the copy.
        </p>
      </header>

      <section>
        <h2 className="text-sm font-semibold uppercase tracking-wider text-neutral-500 mb-3">
          1. Brand
        </h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
          {brandKits.map((k) => (
            <BrandKitCard
              key={k.id}
              kit={k}
              selected={brand?.id === k.id}
              onSelect={pickBrand}
            />
          ))}
        </div>
      </section>

      <section>
        <h2 className="text-sm font-semibold uppercase tracking-wider text-neutral-500 mb-3">
          2. Layout
        </h2>
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          {templates.map((t) => {
            const supported =
              !brand || brand.supported_templates.length === 0
                ? true
                : brand.supported_templates.includes(t.id);
            return (
              <TemplateCard
                key={t.id}
                template={t}
                selected={template?.id === t.id}
                disabled={!supported}
                onSelect={setTemplate}
              />
            );
          })}
        </div>
        {brand && supportedTemplates.length < templates.length && (
          <p className="text-xs text-neutral-500 mt-2">
            Greyed templates aren&apos;t typically used for {brand.name}.
          </p>
        )}
      </section>

      <section className="space-y-4">
        <h2 className="text-sm font-semibold uppercase tracking-wider text-neutral-500">
          3. Brief
        </h2>
        <label className="block">
          <span className="text-sm font-medium">Image prompt</span>
          <textarea
            className="mt-1 w-full rounded-md border border-neutral-300 px-3 py-2 text-sm font-mono"
            rows={4}
            placeholder="Dramatic studio shot of premium retail products partially emerging from glossy black gift boxes, deep crimson and electric red rim lighting…"
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
          />
        </label>
        <label className="block">
          <span className="text-sm font-medium">Headline copy</span>
          <input
            className="mt-1 w-full rounded-md border border-neutral-300 px-3 py-2 text-sm"
            placeholder="Up to 60% off everything"
            value={copy}
            onChange={(e) => setCopy(e.target.value)}
          />
        </label>

        <details
          open={advanced}
          onToggle={(e) => setAdvanced((e.target as HTMLDetailsElement).open)}
          className="rounded-md border border-neutral-200 bg-white"
        >
          <summary className="cursor-pointer px-4 py-2 text-sm font-medium">
            Advanced
          </summary>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 px-4 pb-4">
            <label className="block">
              <span className="text-xs text-neutral-500">Provider</span>
              <select
                className="mt-1 w-full rounded-md border border-neutral-300 px-2 py-1.5 text-sm"
                value={provider}
                onChange={(e) =>
                  setProvider(e.target.value as "openai" | "local")
                }
              >
                <option value="openai">OpenAI gpt-image-1 (paid)</option>
                <option value="local">Local SDXL-Turbo (free, slow)</option>
              </select>
            </label>
            <label className="block">
              <span className="text-xs text-neutral-500">Quality</span>
              <select
                className="mt-1 w-full rounded-md border border-neutral-300 px-2 py-1.5 text-sm"
                value={quality}
                onChange={(e) =>
                  setQuality(e.target.value as "low" | "medium" | "high")
                }
              >
                <option value="low">Low</option>
                <option value="medium">Medium</option>
                <option value="high">High</option>
              </select>
            </label>
            <label className="block">
              <span className="text-xs text-neutral-500">Max iterations</span>
              <input
                type="number"
                min={1}
                max={8}
                className="mt-1 w-full rounded-md border border-neutral-300 px-2 py-1.5 text-sm font-mono"
                value={maxIterations}
                onChange={(e) => setMaxIterations(Number(e.target.value))}
              />
            </label>
            <label className="block">
              <span className="text-xs text-neutral-500">Cost cap (USD)</span>
              <input
                type="number"
                step="0.01"
                min={0}
                className="mt-1 w-full rounded-md border border-neutral-300 px-2 py-1.5 text-sm font-mono"
                value={costCap}
                onChange={(e) => setCostCap(e.target.value)}
              />
            </label>
            <label className="block sm:col-span-2">
              <span className="text-xs text-neutral-500">
                Seed (optional, local provider only)
              </span>
              <input
                type="number"
                className="mt-1 w-full rounded-md border border-neutral-300 px-2 py-1.5 text-sm font-mono"
                value={seed}
                onChange={(e) => setSeed(e.target.value)}
              />
            </label>
          </div>
        </details>
      </section>

      <footer className="flex items-center justify-between border-t border-neutral-200 pt-6">
        {estimate && (
          <div className="text-sm text-neutral-600">
            Estimated cost:{" "}
            <span className="font-mono">
              ${estimate.min.toFixed(3)} – ${estimate.max.toFixed(3)}
            </span>{" "}
            <span className="text-neutral-500">
              (typ. ${estimate.expected.toFixed(3)})
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
          {submitting ? "Submitting…" : "Generate"}
        </button>
      </footer>

      {submitError && (
        <div className="rounded-md border border-rose-300 bg-rose-50 px-4 py-3 text-sm text-rose-900">
          {submitError}
        </div>
      )}
    </div>
  );
}
