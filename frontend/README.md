# CanvasKit frontend

Next.js 16 (App Router, TypeScript, Tailwind v4). Wraps the FastAPI
backend with a designed UI for non-technical users.

## Run locally

```bash
npm install
npm run dev   # http://localhost:3000
```

The backend must be running on `http://localhost:8000`. Override with
`NEXT_PUBLIC_BACKEND_URL` if it lives elsewhere.

```bash
NEXT_PUBLIC_BACKEND_URL=http://10.0.0.5:8000 npm run dev
```

## Routes

| Route | What it does |
|---|---|
| `/` | Gallery — server-rendered grid of the 10 finished scenarios. |
| `/gallery/[id]` | Single-creative detail with raw + spec. |
| `/new` | Generator: pick brand kit → layout → write brief → live preview. |
| `/jobs/[id]` | Live job page. SSE-driven iteration preview, cost meter, cancel + regenerate. |
| `/campaigns/new` | Multi-brief campaign editor. |
| `/campaigns/[id]` | Live batch grid + zip download. |

## Architecture notes

* All API access goes through `src/lib/api.ts` (typed fetch client).
* SSE wrapped by `src/lib/sse.ts` with a typed event union mirroring the
  backend pipeline.
* Server components fetch read-only data (gallery, brand kits, templates);
  client components handle SSE and interactive forms.
* No external state library — `useState` is plenty for the screens here.

## Next.js 16 caveats

* Dynamic-route `params` are async: `params: Promise<{ id: string }>`. Use
  `await params` in server components, `use(params)` from `react` in client
  components.
* Turbopack is the default bundler.
* See `frontend/AGENTS.md` for breaking-change references.
