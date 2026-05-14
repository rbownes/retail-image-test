import Link from "next/link";
import type { GalleryItem } from "@/lib/types";
import { staticUrl } from "@/lib/api";

export function GalleryGrid({ items }: { items: GalleryItem[] }) {
  if (items.length === 0) {
    return (
      <div className="rounded-lg border border-dashed border-neutral-300 p-10 text-center text-neutral-500">
        No finished creatives yet. Click <span className="font-medium">+ New creative</span> to make one.
      </div>
    );
  }
  return (
    <div className="masonry">
      {items.map((item) => (
        <Link
          key={item.id}
          href={`/gallery/${item.id}`}
          className="block group overflow-hidden rounded-lg bg-white border border-neutral-200 shadow-sm hover:shadow-md transition-shadow"
        >
          {/* Backend serves PNGs as static; use plain <img> to skip the next/image
              remote-pattern config — these come from localhost backend. */}
          <img
            src={staticUrl(item.final_url) ?? ""}
            alt={item.theme}
            className="w-full h-auto group-hover:opacity-95 transition-opacity"
            loading="lazy"
          />
          <div className="px-4 py-3 flex items-center justify-between">
            <span className="text-sm font-medium">{item.theme}</span>
            {item.cost_usd !== null && (
              <span className="text-xs font-mono text-neutral-500">
                ${item.cost_usd.toFixed(3)}
              </span>
            )}
          </div>
        </Link>
      ))}
    </div>
  );
}
