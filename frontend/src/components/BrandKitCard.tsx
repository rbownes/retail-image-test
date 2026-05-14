"use client";
import type { BrandKit } from "@/lib/types";
import { staticUrl } from "@/lib/api";

export function BrandKitCard({
  kit,
  selected,
  onSelect,
}: {
  kit: BrandKit;
  selected: boolean;
  onSelect: (kit: BrandKit) => void;
}) {
  return (
    <button
      type="button"
      onClick={() => onSelect(kit)}
      className={`text-left rounded-lg border bg-white p-4 transition-all ${
        selected
          ? "border-neutral-900 ring-2 ring-neutral-900 shadow-md"
          : "border-neutral-200 hover:border-neutral-400 hover:shadow-sm"
      }`}
    >
      <div className="flex items-center gap-3 mb-3">
        {kit.logo_url && (
          <div
            className="h-10 w-10 rounded flex items-center justify-center shrink-0 overflow-hidden bg-white border-2"
            style={{ borderColor: kit.primary }}
          >
            <img
              src={staticUrl(kit.logo_url) ?? ""}
              alt={kit.name}
              className="max-h-7 max-w-7 object-contain"
            />
          </div>
        )}
        <div>
          <div className="text-base font-semibold leading-tight">{kit.name}</div>
          <div className="text-xs text-neutral-500">{kit.tagline}</div>
        </div>
      </div>
      <div className="flex gap-1.5 mb-2">
        <span
          className="h-5 w-5 rounded border border-neutral-200"
          style={{ background: kit.primary }}
          title={`primary ${kit.primary}`}
        />
        <span
          className="h-5 w-5 rounded border border-neutral-200"
          style={{ background: kit.secondary }}
          title={`secondary ${kit.secondary}`}
        />
        <span
          className="h-5 w-5 rounded border border-neutral-200"
          style={{ background: kit.accent }}
          title={`accent ${kit.accent}`}
        />
      </div>
      <div className="text-xs text-neutral-600 leading-snug">{kit.tone}</div>
    </button>
  );
}
