# Local Docker Setup

> Back to [README](../../README.md). Related: [Server setup](server-setup.md) · [Monorepo structure](../architecture/monorepo.md)

How the local development stack is set up with Docker Compose, what each part does, and how the pieces connect. It was set up in issue #105. For the quick "how do I run it" reference, see [infra/README.md](../../infra/README.md); for how the Python code is organised, see [Monorepo structure](../architecture/monorepo.md).

## 1. The big picture

- **One command runs everything.** `docker compose up --build` from the repo root starts the database, Redis, the email catcher, the gateway and all five services.
- **The same containers locally and on the server.** The images built here are the ones the live server will run (with production settings), so "works on my machine" and "works on the server" mean the same thing.
- **Nothing to install except Docker Desktop.** No local Postgres, Redis or Python is needed to run the stack. (Python and uv are still used for writing code and running tests outside Docker.)
- **Safe local defaults.** Every setting has a default in the Compose file, so no `.env` file is needed. The passwords are for local development only; the live server sets its own.

```text
                 browser / curl
                       │
                       ▼
          ┌──────────────────────────┐
          │   Traefik (gateway) :80  │   dashboard :8080
          └────────────┬─────────────┘
       /api/accounts   │   /api/trips   /api/routing   /api/payments   /api/notifications
          ┌────────────┼──────────────┬──────────────┬───────────────┐
          ▼            ▼              ▼              ▼               ▼
      accounts       trips         routing       payments     notifications
          │            │              │              │               │
          └────────────┴──────┬───────┴──────────────┴───────────────┘
                              │
             ┌────────────────┼─────────────────┐
             ▼                ▼                 ▼
     PostgreSQL + PostGIS   Redis           Mailpit (SMTP)
       :5432, 5 schemas     :6379           UI :8025
```

## 2. Files

```text
COMP-4350-Group5-GetDrove/
├── compose.yaml                     # Entry point: includes infra/docker-compose.yml (lets you run from the root)
├── .dockerignore                    # Keeps .venv, .git, .env, docs and tests out of images
└── infra/
    ├── README.md                    # Quick reference: commands, URLs, common problems
    ├── docker-compose.yml           # The whole stack: infrastructure + five services
    ├── docker/
    │   ├── python-service.Dockerfile  # One image recipe for all five services
    │   └── entrypoint.sh              # Container start-up: migrations, then Uvicorn
    └── postgres/
        └── init/
            └── 20-create-service-schemas.sh   # First-start database setup
```

`compose.yaml` at the root only contains `include: infra/docker-compose.yml`. Paths inside the included file are relative to `infra/`, so the build context `..` is the repo root.

## 3. The containers

| Container | Image | Host port | What it's for |
|---|---|---|---|
| `postgres` | `postgis/postgis:17-3.5` | 5432 | PostgreSQL 17 with PostGIS. One database (`getdrove`) with a schema per service. Data kept in the `postgres-data` volume. |
| `redis` | `redis:7.4-alpine` | 6379 | Event streams between services. Append-only file on, so events survive a restart. Data in the `redis-data` volume. |
| `mailpit` | `axllent/mailpit:v1.27` | 8025 (UI), 1025 (SMTP) | Catches every email the app sends (e.g. verification emails) so nothing reaches a real inbox. |
| `traefik` | `traefik:v3.6` | 80 (gateway), 8080 (dashboard) | The gateway: routes `/api/<service>` to the right service. |
| `accounts`, `trips`, `routing`, `payments`, `notifications` | Built from `python-service.Dockerfile` | none | The five FastAPI services, reached only through Traefik. |

Why these choices:

- **Image versions are pinned** (e.g. `17-3.5`, `v3.6`) so everyone gets the same versions and an upstream release can't break the stack overnight.
- **Traefik v3.6 or newer is required:** older versions can't talk to Docker Engine 29+, which current Docker Desktop ships.
- **PostGIS runs as `linux/amd64`:** the PostGIS image is only built for x86-64. On Apple silicon Macs, Docker emulates it (slower start, otherwise fine). The live server is x86-64, so it runs natively there.
- **Services have no host ports:** they're only reachable through the gateway, the same as on the live server. To work on one service with fast reloads, run it outside Docker (see section 8).

## 4. Start-up order and health checks

Containers start in dependency order:

1. `postgres` and `redis` start. Each has a health check (`pg_isready`, `redis-cli ping`).
2. The five services wait until Postgres and Redis report **healthy** (`depends_on: condition: service_healthy`), so they never start against a database that isn't ready.
3. Each service runs its migrations, then starts. Its own health check calls `GET /health` every 10 seconds; `docker compose ps` shows the result.
4. Traefik picks up each service as soon as its container is running.

All long-running containers use `restart: unless-stopped`, so a crashed container restarts on its own (and `docker compose ps` / `logs` show why).

## 5. The database

### One schema and one user per service

The first time Postgres starts with an empty volume, it runs `20-create-service-schemas.sh`. The script:

1. Enables **PostGIS** in the `public` schema, so geometry types and functions are available to everyone.
2. Stops ordinary users creating anything in `public`, and removes the default "anyone can connect" permission.
3. For each service (`accounts`, `trips`, `routing`, `payments`, `notifications`):
   - creates a database **user** with the same name and its own password,
   - creates a **schema** with the same name, **owned by that user**,
   - removes everyone else's access to that schema,
   - sets the user's `search_path` to `<service>, public`, so unqualified table names go to its own schema and PostGIS types are still found,
   - lets the user connect to the `getdrove` database.

The result:

| | Own schema | Another service's schema | `public` |
|---|---|---|---|
| Create tables | ✅ | ❌ permission denied | ❌ permission denied |
| Read / write | ✅ | ❌ permission denied | PostGIS functions only |

This enforces at the database level what the architecture says: **a service only reads its own data**. If Trips needs something from Accounts, it asks the Accounts API.

Details worth knowing:

- The script is **mounted as a single file** into `/docker-entrypoint-initdb.d/`, not as a folder. Mounting a folder there would hide the PostGIS image's own setup scripts.
- It only runs on an **empty** database. After changing it, reset with `docker compose down -v` (this deletes all local data).
- Passwords are passed to `psql` as variables (`:'pw'`), not pasted into the SQL, so special characters are handled safely.
- The Postgres entrypoint may *source* the script instead of running it, so it avoids `exit` and doesn't change shell options.

### Migrations

Each service container runs `alembic upgrade head` before starting the web server (see section 7). So:

- a fresh `docker compose up` always gives you the latest tables,
- a broken migration stops that service from starting, and `docker compose logs <service>` shows the error.

Alembic records which migrations have run in an `alembic_version` table **inside each service's own schema**. The schemas themselves are created by the init script, not by Alembic, because service users aren't allowed to create schemas.

## 6. The gateway (Traefik)

Traefik reads its routing rules from **labels** on each service in the Compose file, through the Docker socket (mounted read-only). Only containers with `traefik.enable=true` are exposed.

For each service, the labels set up:

| Label | Effect |
|---|---|
| `rule=PathPrefix(/api/trips) && !PathPrefix(/api/trips/internal)` | Requests to `/api/trips/...` go to Trips, **except** `/api/trips/internal/...`, which is never exposed |
| `middlewares=trips-strip` + `stripprefix.prefixes=/api/trips` | Removes `/api/trips` before passing the request on, so `GET /api/trips/health` arrives at Trips as `GET /health` |
| `loadbalancer.server.port=8000` | Every service listens on port 8000 inside its container |

What this means when writing services:

- **Define routes without the prefix.** A Trips route `@router.post("/")` is reached from outside as `POST /api/trips`; `@router.get("/search")` as `GET /api/trips/search`.
- **Service-to-service calls skip the gateway.** Inside Docker, services reach each other by name: `http://routing:8000/internal/routes`. Those URLs are passed in as environment variables (e.g. `TRIPS_ROUTING_URL`).
- **Swagger UI works through the gateway** (`/api/<service>/docs`) because each service is started with `--root-path /api/<service>`, which tells FastAPI the prefix it's served under.

The dashboard at http://localhost:8080 lists every router and whether its service is up. It's enabled in insecure mode, which is only acceptable locally.

## 7. The service image

All five services are built from **one** Dockerfile, `infra/docker/python-service.Dockerfile`, with a `SERVICE` build argument (Compose sets it per service). It has two stages.

### Build stage

1. Starts from `python:3.13-slim` and copies in the `uv` binary from the official uv image.
2. Copies **only** `pyproject.toml`, `uv.lock` and each package's `pyproject.toml`, then installs the service's third-party dependencies (`uv sync --frozen --no-dev --package <service> --no-install-workspace`).
   - This layer is cached until a dependency changes, so code-only changes rebuild in seconds.
   - `--frozen` installs exactly what `uv.lock` says; `--no-dev` leaves out test and lint tools.
3. Copies `libs/` and `services/`, then installs the shared libraries and the service itself (`--no-editable`), so they live inside the virtual environment and the source folders aren't needed at runtime.

`UV_COMPILE_BYTECODE=1` pre-compiles Python files for faster start-up. A build cache mount keeps uv's download cache between builds.

### Runtime stage

1. Starts again from a clean `python:3.13-slim` (no uv, no build files).
2. Creates a **non-root user** `app`; the container runs as that user.
3. Copies in only what's needed: the virtual environment, the service's `alembic.ini` and `migrations/`, and `entrypoint.sh`.
4. Makes all files readable by `app` (files can arrive owner-only depending on the host).
5. Adds a `HEALTHCHECK` that calls `/health`.

### Entrypoint

`entrypoint.sh` does two things:

1. Runs `alembic upgrade head`, unless `RUN_MIGRATIONS=false`.
2. Starts Uvicorn on `0.0.0.0:8000` with `--root-path /api/<service>` (override with `ROOT_PATH`) and `--proxy-headers`, so the service sees the original client address and protocol behind Traefik.

It uses `exec`, so Uvicorn becomes the container's main process and shuts down cleanly on `docker compose down`.

### What's kept out of images

`.dockerignore` excludes `.git`, `.github`, `.venv`, caches, coverage files, `.env` files, `docs/`, `web/`, tests and the implementation plan. This keeps builds fast and ensures local secrets never end up inside an image.

## 8. Configuration and environment variables

### Settings the services receive

Each service gets environment variables with its own prefix, matching its `infrastructure/settings.py`:

| Variable | Value in Compose | Used by |
|---|---|---|
| `<SERVICE>_DATABASE_URL` | `postgresql+asyncpg://<service>:<password>@postgres:5432/getdrove` | All |
| `<SERVICE>_REDIS_URL` | `redis://redis:6379/0` | All (once events are added) |
| `TRIPS_ROUTING_URL`, `TRIPS_PAYMENTS_URL`, `TRIPS_ACCOUNTS_URL` | `http://<service>:8000` | Trips |
| `NOTIFICATIONS_SMTP_HOST`, `NOTIFICATIONS_SMTP_PORT` | `mailpit`, `1025` | Notifications |

Inside Docker, hosts are container names (`postgres`, `redis`, `mailpit`, `routing`); from your laptop they're `localhost`. Settings a service doesn't define yet are simply ignored.

### Overriding defaults

Compose reads a `.env` file in the repo root, if there is one. Every value in `docker-compose.yml` is written as `${NAME:-default}`, so you only set what you want to change, for example:

```bash
# .env (gitignored, never committed)
POSTGRES_PORT=5433      # if you already run Postgres locally
GATEWAY_PORT=8000       # if port 80 is taken
```

All the optional variables are listed (commented out) in `.env.example`.

### Running one service outside Docker

For fast edit-and-reload on the service you're working on:

```bash
docker compose up -d postgres redis mailpit
uv run --package trips uvicorn trips.infrastructure.main:app --reload --port 8002
```

This works without any configuration: each service's default `DATABASE_URL` points at `localhost:5432` with its own user and password, which match what the init script created. Alembic works the same way (`cd services/trips && uv run alembic upgrade head`).

## 9. Data and volumes

| Volume | Holds | Survives `down` | Deleted by `down -v` |
|---|---|---|---|
| `getdrove_postgres-data` | Every service's tables | ✅ | ✅ |
| `getdrove_redis-data` | Redis append-only file (events) | ✅ | ✅ |

Use `docker compose down -v` when you want a completely fresh start: the database is recreated, the init script runs again, and every migration is applied from scratch.

## 10. Everyday commands

```bash
docker compose up --build            # build and start everything (Ctrl+C stops it)
docker compose up --build -d         # same, in the background
docker compose ps                    # status and health of each container
docker compose logs -f trips         # follow one service's logs
docker compose up --build -d trips   # rebuild and restart one service after a change
docker compose exec postgres psql -U postgres -d getdrove   # SQL shell as admin
docker compose down                  # stop (keeps data)
docker compose down -v               # stop and delete all local data
```

Useful SQL checks inside that shell: `\dn` lists the schemas and their owners, `\du` lists the users, `\dt trips.*` lists Trips' tables.
