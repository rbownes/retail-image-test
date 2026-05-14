import { BACKEND_URL, BACKEND_URL_SERVER } from "./config";
import type {
  BrandKit,
  Estimate,
  GalleryItem,
  JobSummary,
  SingleJobRequest,
  Template,
} from "./types";

function backend(isServer: boolean) {
  return isServer ? BACKEND_URL_SERVER : BACKEND_URL;
}

async function fetchJson<T>(
  path: string,
  init?: RequestInit & { isServer?: boolean }
): Promise<T> {
  const { isServer = typeof window === "undefined", ...rest } = init ?? {};
  const res = await fetch(`${backend(isServer)}${path}`, {
    cache: "no-store",
    ...rest,
  });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`${res.status} ${res.statusText}: ${body || path}`);
  }
  return res.json() as Promise<T>;
}

export function staticUrl(staticPath: string | null | undefined): string | null {
  if (!staticPath) return null;
  // Always use the browser-facing backend origin. This function produces URLs
  // that end up in HTML <img src>/<a href>, so even when called during SSR the
  // browser will be the one resolving them — never the docker-internal hostname.
  return `${BACKEND_URL}${staticPath}`;
}

export const api = {
  getBrandKits: () => fetchJson<BrandKit[]>("/api/brand-kits"),
  getBrandKit: (id: string) => fetchJson<BrandKit>(`/api/brand-kits/${id}`),
  getTemplates: () => fetchJson<Template[]>("/api/templates"),
  getTemplate: (id: string) => fetchJson<Template>(`/api/templates/${id}`),
  getGallery: () => fetchJson<GalleryItem[]>("/api/gallery"),
  getGalleryItem: (id: string) => fetchJson<GalleryItem>(`/api/gallery/${id}`),

  estimate: (body: { provider: string; quality: string; max_iterations: number }) =>
    fetchJson<Estimate>("/api/jobs/estimate", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(body),
    }),

  createSingleJob: (body: SingleJobRequest) =>
    fetchJson<{ job_id: string }>("/api/jobs/single", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(body),
    }),

  createBatchJob: (body: { name: string; briefs: SingleJobRequest[] }) =>
    fetchJson<{ job_id: string; expected_children: number }>("/api/jobs/batch", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(body),
    }),

  getJob: (id: string) => fetchJson<JobSummary>(`/api/jobs/${id}`),
  cancelJob: (id: string) =>
    fetchJson<{ status: string }>(`/api/jobs/${id}/cancel`, { method: "POST" }),
  jobEventsUrl: (id: string) => `${backend(false)}/api/jobs/${id}/events`,
  batchEventsUrl: (id: string) => `${backend(false)}/api/jobs/${id}/batch-events`,
  downloadUrl: (id: string, kind: "final" | "raw" | "spec" | "summary" | "bundle.zip") =>
    `${backend(false)}/api/jobs/${id}/download/${kind}`,
};
