# GetDrove web app

The frontend: **Next.js + TypeScript** with the App Router ([ADR 0002](../docs/architecture/adr/0002-frontend-framework.md)). It's the frontend only: all business logic lives in the backend services, which the app calls through the gateway at `/api/<service>`.

## Requirements

- **Node 24** (the version in `.nvmrc`). Check with `node --version`.
- For real data: the backend running with `docker compose up --build` from the repo root.

## Getting started

```bash
cd web
npm install        # first time, and after pulling changes to package.json / package-lock.json
npm run dev        # http://localhost:3000, reloads on save
```

`npm run dev` forwards `/api/*` to the gateway at `http://localhost`, so with Docker Compose running, the dev server talks to the real services. To point somewhere else, set `API_PROXY_URL` (e.g. `API_PROXY_URL=http://localhost:8000 npm run dev` if you changed `GATEWAY_PORT`).

With Docker Compose, the app also runs in its own container at **http://localhost** (production build, no hot reload).

## Commands

| Command | What it does |
|---|---|
| `npm run dev` | Dev server with hot reload |
| `npm run dev:mock` | Dev server with the mock API, so pages work without the backend |
| `npm run build` / `npm start` | Production build, then run it |
| `npm run lint` | ESLint: Next.js rules, React hooks rules and the folder rules below |
| `npm run typecheck` | TypeScript, strict |
| `npm test` | Unit tests (Vitest); `npm run test:watch` re-runs on save |
| `npm run api:generate` | Regenerates the API types from `contracts/openapi` |
| `npm run api:check` | Fails if the API types don't match the contracts |
| `npm run check` | All of the checks CI runs (except the build) |

`bash scripts/check.sh` at the repo root runs these too, after the backend checks. CI runs them in the **Frontend checks** job on every pull request.

## Folders

```text
web/
├── package.json / package-lock.json   # Dependencies; commit both
├── next.config.ts                     # Standalone output for Docker; /api proxy for npm run dev
├── eslint.config.mjs                  # Lint rules, including the folder rules
├── postcss.config.mjs                 # Tailwind CSS
├── vitest.config.mts                  # Unit and component tests (jsdom)
├── Dockerfile                         # deps → build → small runtime image (node server.js)
├── scripts/generate-api.mjs           # contracts/openapi/*.json → src/shared/api/generated/
└── src/
    ├── app/                           # Routing only: pages and layouts stay thin
    ├── features/                      # One folder per product area (auth, ride, drive, …)
    │   └── <feature>/
    │       ├── ui/                    # Components
    │       ├── hooks/                 # State and data fetching used by the components
    │       ├── api/                   # Calls to the backend, through shared/api
    │       ├── model/                 # Plain types and rules: no React, no network
    │       └── index.ts               # What other folders may use from this feature
    └── shared/
        ├── ui/                        # Design system: Button, TextField, Card, Badge, BottomSheet, …
        ├── map/                       # MapView (MapLibre), map colours, geo helpers, CAMPUS
        ├── mocks/                     # Mock API (MSW) for building pages before endpoints exist
        ├── api/                       # Typed API clients, error handling, generated types
        ├── lib/                       # Small helpers (cn)
        └── config/                    # Settings read from the environment
```

`features/status/` is the example to copy: a small feature that checks every service's `/health` and is shown on the placeholder home page.

### Folder rules

ESLint enforces these (the frontend's version of import-linter, using ESLint's built-in `no-restricted-imports` rule), so `npm run lint` fails if they're broken:

| Folder | May import from |
|---|---|
| `app/` | `app/`, `features/`, `shared/` |
| `features/` | its own files, other features (through their `index.ts`), `shared/` |
| `shared/` | `shared/` only |

Outside a feature's own folder, import it as `@/features/<name>`, never `@/features/<name>/ui/...`, so each feature decides what it exposes in `index.ts`. Also, by convention, pages don't call APIs directly: they use a feature's components.

## Styling and the design system

Styling uses **Tailwind CSS**. The design tokens from the mockups (colours, font, corners, shadows) are defined once in `src/app/globals.css`, and Tailwind turns each into classes: `bg-brand`, `text-muted`, `border-line`, `rounded-lg`, `shadow-card`. Tailwind's default colours are switched off, so only our colours exist.

- **See everything at [`/design`](http://localhost:3000/design)**: every colour, text style and shared component, and [`/design/layout`](http://localhost:3000/design/layout) for the panel + map layout (resize the window to see the mobile version).
- **Use the shared components** from `@/shared/ui` before writing your own: `Button` (primary, dark, outline, secondary, soft), `TextField` (label, error, password toggle), `Card`, `Badge`, `Avatar`, `Eyebrow` ("PICKUP · 7:48 AM"), `PrivacyNote` (the lock line), `Logo`, `AppHeader`, `MapLayout`, `BottomSheet`.
- **A new shared component** goes in `src/shared/ui/` with a test, an export in `index.ts`, and an example on `/design`.
- **Font:** Figtree, self-hosted from npm (no request to Google). Icons: [Lucide](https://lucide.dev/icons/) (`lucide-react`).
- **Mobile first:** write the phone layout first, then add `md:` classes for desktop. The mockups switch layout at tablet width (`md`, 768px).

## Maps

`MapView` from `@/shared/map` draws MapLibre with OpenFreeMap tiles (free, no key; ADR 0009), recoloured to match the mockups. It takes plain data and zooms to fit it:

```tsx
<MapView
  routes={[{ id: "trip", coordinates: [[-97.1445, 49.8786], [-97.1366, 49.8075]], style: "primary" }]}
  markers={[{ id: "pickup", lngLat: [-97.1445, 49.8786], kind: "pickup", label: "Pickup · 7:48 AM" }]}
  area={{ center: [-97.1405, 49.8762], radiusMeters: 450 }}
/>
```

MapLibre runs its drawing work in a background worker, a file copied into `public/maplibre/` by `npm run maplibre:worker` (run automatically before `dev` and `build`, and gitignored). If the map stays blank with "Worker failed to load", run it by hand.

Coordinates are `[longitude, latitude]` (GeoJSON order, the reverse of how they're usually said). `CAMPUS` is University Centre. The map loads in the browser only; give its container a height.

## Building against the mock API

`npm run dev:mock` (or `NEXT_PUBLIC_API_MOCKING=enabled` in `.env.local`) serves fake responses for the Sprint 1 endpoints from `src/shared/mocks/` using [MSW](https://mswjs.io/), so a page can be built before its endpoint exists. The fake data is typed against the contracts, so it can't drift from the real API. Special inputs trigger the error states (e.g. signing up with a non-UofM email); they're listed at the top of `src/shared/mocks/handlers.ts`. Add a handler there when you start a page whose endpoint isn't ready. Tests use the same handlers through `src/shared/mocks/server.ts`.

## Calling the backend

The API types are **generated from the contracts**, so TypeScript catches a wrong path, a missing field or a renamed property:

```ts
import { tripsApi, unwrap } from "@/shared/api";

const trips = await unwrap(tripsApi.GET("/mine"));          // typed response
await unwrap(tripsApi.POST("/", { body: { /* typed */ } })); // typed request body
```

- `unwrap` returns the data, or throws an `ApiError` whose `code` is the backend's stable error name (e.g. `email_taken`, `token_expired`). Show messages based on `code`, not on the text.
- Gateway errors that aren't Problem Details (e.g. a 502 while a service restarts) become `code: "service_unavailable"`.
- The clients use relative URLs (`/api/...`), so call them from client components (`"use client"`).
- Endpoints under `/internal` appear in the types but are only for services; the gateway doesn't expose them.

**When a contract changes:** pull, then run `npm run api:generate` and commit the changed files in `src/shared/api/generated/`. CI fails if they're out of date.

## Environment variables

| Variable | Default | Used for |
|---|---|---|
| `NEXT_PUBLIC_API_MOCKING` | `disabled` | `enabled` serves the mock API in the browser |
| `NEXT_PUBLIC_API_BASE_URL` | `/api` | Base URL of the APIs, as the browser sees it |
| `API_PROXY_URL` | `http://localhost` | Where `npm run dev` forwards `/api/*` |

Put local overrides in `web/.env.local` (gitignored); `.env.example` lists them. Anything starting with `NEXT_PUBLIC_` is built into the JavaScript that browsers download, so never put secrets in it.

## Libraries

| Need | Library |
|---|---|
| Styling | Tailwind CSS |
| Data fetching and caching | TanStack Query (`QueryClientProvider` in `src/app/providers.tsx`) |
| Bottom sheets | vaul |
| Maps | MapLibre GL 6 + react-map-gl |
| Icons | lucide-react |
| Mock API | MSW |
| Forms and validation | React Hook Form + Zod (`zodResolver`); rules mirror the contract's limits |
| Tests | Vitest + Testing Library |

## Pages so far

| Page | What it does |
|---|---|
| `/signup` | Sign up with first name, last name, UofM email and a password of 10+ characters; then "Check your email" with a resend button |
| `/login` | Log in; `?next=/path` returns to that page afterwards (only paths on this site). Wrong email or password gets one message; an unverified email gets a "send a new link" button. The access token is kept in memory only |
| `/verify?token=…` | The page the verification email links to: verified, expired (with a form for a new link), or not valid |

With `npm run dev:mock`, `/verify?token=expired` and `/verify?token=used` show the error states, and logging in with password `wrong` or as `unverified@myumanitoba.ca` shows the login errors.

## Testing components

`src/shared/testing/render.tsx` has two helpers: `renderWithProviders(<Component />)` renders with a fresh TanStack Query client, and `mockFetch(...)` gives each API call a fake response in order. See `src/features/auth/ui/SignupForm.test.tsx` for an example. Tests use absolute API URLs (`NEXT_PUBLIC_API_BASE_URL` is set in `vitest.config.mts`).
