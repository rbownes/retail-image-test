// Where the FastAPI backend lives.
// Server components use BACKEND_URL_SERVER (defaults to BACKEND_URL).
// Client components use BACKEND_URL (must be NEXT_PUBLIC_ for hydration).

export const BACKEND_URL =
  process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000";

// Same origin when running via Docker on the same host.
export const BACKEND_URL_SERVER =
  process.env.BACKEND_URL_SERVER ?? BACKEND_URL;

export const PRODUCT_NAME = process.env.NEXT_PUBLIC_PRODUCT_NAME ?? "CanvasKit";
export const PRODUCT_TAGLINE =
  process.env.NEXT_PUBLIC_PRODUCT_TAGLINE ??
  "Brief to brand-ready creative in under a minute.";
