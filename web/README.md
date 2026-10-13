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
├── vitest.config.mts                  # Unit tests
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
        ├── api/                       # Typed API clients, error handling, generated types
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
| `NEXT_PUBLIC_API_BASE_URL` | `/api` | Base URL of the APIs, as the browser sees it |
| `API_PROXY_URL` | `http://localhost` | Where `npm run dev` forwards `/api/*` |

Put local overrides in `web/.env.local` (gitignored). Anything starting with `NEXT_PUBLIC_` is built into the JavaScript that browsers download, so never put secrets in it.

## Still to do in #107

The infrastructure is in place. Still to come: design tokens from the mockups, shared UI components (Button, BottomSheet, …), the map component (MapLibre, client-only) and mock API responses for building pages before endpoints exist. The pages themselves (sign-up, login, post trip, …) belong to their own feature issues.
