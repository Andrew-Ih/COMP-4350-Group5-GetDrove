# Local setup guide

> Back to [README](../../README.md). Related: [Local Docker setup](docker-setup.md) (how the stack works) · [infra/README.md](../../infra/README.md) (Compose commands) · [web/README.md](../../web/README.md) (frontend) · [Testing strategy](../testing/testing-strategy.md) · [Git workflow](../process/git-workflow.md)

How to get GetDrove running on your own machine, from nothing, on macOS or Windows. Follow it top to bottom the first time; after that, [Day to day](#7-day-to-day) is all you need.

There are three ways to work, and most people use more than one:

| You want to… | Use | Section |
|---|---|---|
| Use the whole app, or test a change end to end | Everything in Docker | [3](#3-run-everything-with-docker) |
| Work on a backend service with instant reload | That service with uv, the rest in Docker | [4](#4-work-on-a-backend-service) |
| Work on screens | The Next.js dev server, with the real backend or the mock API | [5](#5-work-on-the-frontend) |

## 1. Install the tools

| Tool | Version | Why | Check |
|---|---|---|---|
| [Git](https://git-scm.com/downloads) | any recent | The code. On Windows this also installs **Git Bash**, which the `.sh` scripts need. | `git --version` |
| [Docker Desktop](https://www.docker.com/products/docker-desktop/) | recent (Compose v2.20 or newer) | Runs the database, Redis, the gateway, OSRM, the services and the web app | `docker compose version` |
| [uv](https://docs.astral.sh/uv/getting-started/installation/) | any recent | The backend's Python tooling. It installs Python 3.13 for you; you don't need Python installed. | `uv --version` |
| [Node.js](https://nodejs.org/) | **24** (`web/.nvmrc`) | The frontend | `node --version` |
| [GitHub CLI](https://cli.github.com/) (optional) | any | Opening PRs and checking CI from the terminal | `gh --version` |

**Docker Desktop settings:** give it at least **4 GB of memory** (Settings → Resources) and keep about **5 GB of disk** free. The first build downloads base images and the Winnipeg map for OSRM. On Windows, use the WSL 2 backend (the default).

**Node version:** if you already have another Node version, a version manager makes switching easy: [nvm](https://github.com/nvm-sh/nvm) on macOS (`nvm install` in `web/` reads `.nvmrc`), [nvm-windows](https://github.com/coreybutler/nvm-windows) or [fnm](https://github.com/Schniz/fnm) on Windows.

## 2. Get the code

```bash
git clone https://github.com/Andrew-Ih/COMP-4350-Group5-GetDrove.git
cd COMP-4350-Group5-GetDrove
git checkout develop
```

Work always starts from `develop` ([Git workflow](../process/git-workflow.md)).

**Windows and line endings.** Git for Windows can convert line endings to CRLF on checkout, which breaks shell scripts inside Linux containers (`exec /app/entrypoint.sh: no such file or directory`). The repo's `.gitattributes` keeps every `.sh` file as LF, so a fresh clone is fine. If you cloned before that file existed, fix your copy once:

```powershell
git rm --cached -r .
git reset --hard
```

(This only rewrites your working copy from what's committed; commit or stash your changes first.)

## 3. Run everything with Docker

With Docker Desktop running, from the repo root:

```bash
docker compose up --build -d
docker compose ps
```

The **first build takes several minutes**: it builds the five service images and the web app, and OSRM downloads the Manitoba map (about 200 MB) and builds the Winnipeg routing graphs. Later builds take seconds. `docker compose ps` should show every container as `healthy` (give it a minute after the build).

Then open:

| What | Where |
|---|---|
| The app | http://localhost |
| Emails the app sends (verification links) | http://localhost:8025 (Mailpit) |
| API docs for a service | http://localhost/api/trips/docs (and `accounts`, `routing`, `payments`, `notifications`) |
| Gateway dashboard | http://localhost:8080 |

**Try it end to end:**

1. Sign up at http://localhost/signup with any `@myumanitoba.ca` address. No real email is sent: it lands in Mailpit.
2. Open http://localhost:8025, open the verification email and click the link.
3. Log in, post a trip as a driver, then sign up a second account and search for it as a rider.

To check the routing engine on its own: `bash infra/osrm/check.sh` (Git Bash on Windows) should print two `OK` lines.

**Stopping:**

```bash
docker compose down        # stop everything; the database is kept
docker compose down -v     # stop and DELETE the database, Redis data and your test accounts
```

More commands and what each container does: [infra/README.md](../../infra/README.md).

## 4. Work on a backend service

Install the Python workspace once (and again whenever `uv.lock` changes):

```bash
uv sync
```

To edit a service with instant reload, run the infrastructure in Docker and the service with uv. For example, Trips:

```bash
docker compose up -d postgres redis mailpit osrm-car osrm-foot
uv run --package trips uvicorn trips.infrastructure.main:app --reload --port 8002
```

| Service | Port | API docs |
|---|---|---|
| Accounts | 8001 | http://localhost:8001/docs |
| Trips | 8002 | http://localhost:8002/docs |
| Routing | 8003 | http://localhost:8003/docs |
| Payments | 8004 | http://localhost:8004/docs |
| Notifications | 8005 | http://localhost:8005/docs |

Each service's defaults already point at `localhost` (Postgres on 5432, Redis on 6379, OSRM on 5050/5051), so no `.env` file is needed. Each service's README has the details, including how its architecture rules are checked.

A service started with uv doesn't run its migrations by itself (the Docker containers do). After pulling changes that add a migration:

```bash
cd services/trips
uv run alembic upgrade head
cd ../..
```

## 5. Work on the frontend

```bash
cd web
npm install        # first time, and after package.json / package-lock.json change
```

Then either:

- **With the real backend:** start the stack (section 3), then `npm run dev`. Open http://localhost:3000. The dev server forwards `/api/*` to the gateway, so it uses the real services.
- **Without any backend:** `npm run dev:mock`. Every endpoint is answered by the mock API in `src/shared/mocks/`, with demo data typed against the contracts. Special inputs that trigger error states are listed at the top of `src/shared/mocks/handlers.ts` and in [web/README.md](../../web/README.md).

## 6. Run the tests and checks

**Everything CI runs, in one go** (macOS, Linux or Git Bash on Windows):

```bash
bash scripts/check.sh
```

**Backend tests need Docker running.** The Accounts, Notifications and events integration tests start their own throwaway Postgres, Redis and Mailpit. The Trips and Routing database tests currently need the stack's Postgres with their tables created (this is being moved to the same throwaway setup):

```bash
docker compose up -d postgres redis
cd services/trips && uv run alembic upgrade head && cd ../..
cd services/routing && uv run alembic upgrade head && cd ../..
uv run pytest
```

In PowerShell, run the same commands with `;` instead of `&&`, or use `uv run --directory services/trips alembic upgrade head`, which works everywhere.

**The checks one by one** (what `check.sh` runs; these work in PowerShell too):

```bash
uv run ruff format --check .
uv run ruff check .
uv run mypy
uv run pytest
cd web
npm run check      # API types, lint, TypeScript, tests
```

Coverage: `uv run pytest --cov --cov-report=html` and `npm run test:coverage` in `web/` ([Testing strategy](../testing/testing-strategy.md#coverage)).

## 7. Day to day

```bash
git checkout develop
git pull
uv sync                              # if uv.lock changed
cd web && npm install && cd ..       # if package-lock.json changed
docker compose up --build -d         # rebuilds only what changed
```

Then branch off `develop` for your task ([Git workflow](../process/git-workflow.md#feature-work-day-to-day)).

## 8. Common problems

| What you see | Cause and fix |
|---|---|
| `Cannot connect to the Docker daemon` / `error during connect` | Docker Desktop isn't running. Start it and wait for "Engine running". |
| `port is already allocated` | Something else uses that port. Stop it, or move ours in a `.env` file at the repo root, e.g. `GATEWAY_PORT=8000` or `POSTGRES_PORT=5433` ([infra/README.md](../../infra/README.md#configuration)). |
| `exec /app/entrypoint.sh: no such file or directory` (Windows) | The script was checked out with CRLF line endings. See [Windows and line endings](#2-get-the-code), then `docker compose up --build`. |
| Trips or Routing tests fail with `Connect call failed ('127.0.0.1', 5432)` | Postgres isn't running: `docker compose up -d postgres`, then run their migrations ([section 6](#6-run-the-tests-and-checks)). |
| Trips or Routing tests fail with `relation "…" does not exist` | Postgres is running but the tables aren't there: run their migrations. |
| A service keeps restarting | `docker compose logs <service>`. Usually a failed migration. If your local database is out of date beyond repair, `docker compose down -v` starts it fresh (deletes local data). |
| The first build stops while downloading the map | A network hiccup: run `docker compose up --build -d` again. It continues from the cached steps. |
| Search or posting a trip says routing is unavailable | OSRM isn't up: `docker compose ps osrm-car osrm-foot` should say `healthy`. Its logs are empty on purpose (it doesn't log requests). |
| Postgres is slow to start on an Apple silicon Mac | The PostGIS image is x86-64 only, so Docker emulates it. It works; the first start takes longer. |
| TypeScript errors about `.next/types` after switching branches | Old generated types: delete `web/.next` (`rm -rf .next`, or `Remove-Item -Recurse -Force .next` in PowerShell) and run the command again. |
| `npm run dev:mock` logs `ECONNREFUSED` for `/health` | The status page checks the real services, which aren't running. Harmless with the mock API. |
| `uv: command not found` / `npm: command not found` | Open a new terminal after installing, so the tool is on your `PATH`. |
| `npm install` complains about the engine or behaves oddly | Wrong Node version: `node --version` should start with `v24`. |

Still stuck: post the command and the full error in the team's dev channel.
