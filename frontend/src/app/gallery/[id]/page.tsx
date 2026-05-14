import Link from "next/link";
import { notFound } from "next/navigation";
import { api, staticUrl } from "@/lib/api";

export default async function GalleryDetail({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  let item;
  try {
    item = await api.getGalleryItem(id);
  } catch {
    notFound();
  }

  return (
    <div className="mx-auto max-w-6xl px-6 py-10">
      <div className="mb-6 flex items-center justify-between">
        <Link
          href="/"
          className="text-sm text-neutral-500 hover:text-neutral-900"
        >
          ← Gallery
        </Link>
        <Link
          href={`/new?theme=${encodeURIComponent(item.theme)}`}
          className="rounded-md border border-neutral-300 px-3 py-1.5 text-sm hover:bg-neutral-100"
        >
          Use as starting point
        </Link>
      </div>

      <h1 className="text-3xl font-semibold tracking-tight mb-1">{item.theme}</h1>
      <p className="text-sm text-neutral-500 mb-6 font-mono">{item.id}</p>

      <div className="grid grid-cols-1 lg:grid-cols-[2fr_1fr] gap-8">
        <div className="bg-white rounded-lg border border-neutral-200 overflow-hidden">
          <img
            src={staticUrl(item.final_url) ?? ""}
            alt={`${item.theme} — final`}
            className="w-full h-auto"
          />
        </div>

        <aside className="space-y-4">
          {item.cost_usd !== null && (
            <div className="rounded-lg bg-white border border-neutral-200 p-4">
              <div className="text-xs uppercase tracking-wide text-neutral-500">
                Cost
              </div>
              <div className="text-2xl font-mono mt-1">
                ${item.cost_usd.toFixed(4)}
              </div>
            </div>
          )}

          {item.raw_url && (
            <details className="rounded-lg bg-white border border-neutral-200">
              <summary className="cursor-pointer px-4 py-3 text-sm font-medium">
                Pre-overlay image
              </summary>
              <div className="border-t border-neutral-200">
                <img
                  src={staticUrl(item.raw_url) ?? ""}
                  alt={`${item.theme} — raw`}
                  className="w-full h-auto"
                />
              </div>
            </details>
          )}

          {item.spec && (
            <details className="rounded-lg bg-white border border-neutral-200">
              <summary className="cursor-pointer px-4 py-3 text-sm font-medium">
                Placement spec
              </summary>
              <pre className="border-t border-neutral-200 p-4 text-xs font-mono overflow-auto">
                {JSON.stringify(item.spec, null, 2)}
              </pre>
            </details>
          )}
        </aside>
      </div>
    </div>
  );
}
