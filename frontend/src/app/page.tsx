import Link from "next/link";
import { api } from "@/lib/api";
import { GalleryGrid } from "@/components/GalleryGrid";
import type { GalleryItem } from "@/lib/types";

export default async function Home() {
  let items: GalleryItem[] = [];
  let backendError: string | null = null;
  try {
    items = await api.getGallery();
  } catch (e) {
    backendError = (e as Error).message;
  }

  return (
    <div className="mx-auto max-w-7xl px-6 py-10">
      <div className="flex items-end justify-between mb-8">
        <div>
          <h1 className="text-3xl font-semibold tracking-tight">Gallery</h1>
          <p className="text-neutral-500 mt-1">
            Finished campaign creatives produced end-to-end by the agentic pipeline.
          </p>
        </div>
        <Link
          href="/new"
          className="rounded-md bg-neutral-900 text-white px-4 py-2 text-sm font-medium hover:bg-neutral-700"
        >
          + New creative
        </Link>
      </div>

      {backendError && (
        <div className="mb-6 rounded-md border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-900">
          Backend unreachable. Start it with{" "}
          <code className="font-mono">uvicorn backend.app.main:app --port 8000</code>.
          <div className="mt-1 font-mono text-xs text-amber-700">{backendError}</div>
        </div>
      )}

      <GalleryGrid items={items} />
    </div>
  );
}
