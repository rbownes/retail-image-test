"use client";
import type { Template } from "@/lib/types";
import { staticUrl } from "@/lib/api";

export function TemplateCard({
  template,
  selected,
  disabled,
  onSelect,
}: {
  template: Template;
  selected: boolean;
  disabled?: boolean;
  onSelect: (t: Template) => void;
}) {
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={() => onSelect(template)}
      className={`text-left rounded-lg border bg-white overflow-hidden transition-all ${
        selected
          ? "border-neutral-900 ring-2 ring-neutral-900 shadow-md"
          : "border-neutral-200 hover:border-neutral-400 hover:shadow-sm"
      } ${disabled ? "opacity-40 cursor-not-allowed" : ""}`}
    >
      {template.thumbnail_url && (
        <img
          src={staticUrl(template.thumbnail_url) ?? ""}
          alt={template.display_name ?? template.name}
          className="w-full aspect-square object-cover"
        />
      )}
      <div className="p-3">
        <div className="text-sm font-medium">
          {template.display_name ?? template.name}
        </div>
        <div className="text-xs text-neutral-500 mt-1 line-clamp-2">
          {template.description}
        </div>
      </div>
    </button>
  );
}
