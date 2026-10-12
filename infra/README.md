# Local infrastructure

Everything needed to run GetDrove on your laptop with one command (issue #105).

For a full explanation of how the stack is set up (database permissions, gateway routing, the service image), see [Local Docker setup](../docs/deployment/docker-setup.md).

## Requirements

- [Docker Desktop](https://www.docker.com/products/docker-desktop/), running
- Nothing else: no local Python, Postgres or Redis needed to run the stack

## Run it

From the repo root:

```bash
docker compose up --build        # build images and start everything (Ctrl+C to stop)
docker compose up --build -d     # same, in the background
docker compose ps                # what's running and whether it's healthy
docker compose logs -f trips     # follow one service's logs
docker compose down              # stop everything (data is kept)
docker compose down -v           # stop and DELETE the database and Redis data
```

The first build takes a few minutes. After that, code changes rebuild in seconds.

## What's running

| What | URL / port | Notes |
|---|---|---|
| Gateway (Traefik) | http://localhost | All APIs at `/api/<service>/...` |
| Service APIs | http://localhost/api/accounts/health (and `trips`, `routing`, `payments`, `notifications`) | Swagger UI at `/api/<service>/docs` |
| Traefik dashboard | http://localhost:8080 | Shows routes and which services are up |
| Mailpit | http://localhost:8025 | Every email the app sends lands here |
| PostgreSQL + PostGIS | `localhost:5432`, database `getdrove` | One user and schema per service (below) |
| Redis | `localhost:6379` | Event streams; append-only file turned on |

OSRM (the routing engine) joins once the OSRM spike (#23) prepares the Winnipeg map data.

## How the pieces fit

- **Gateway:** Traefik routes `/api/<service>/...` to that service and strips the prefix, so a service's own routes start at `/` (e.g. `/health`). Each service runs with `--root-path /api/<service>` so its Swagger UI works through the gateway.
- **Internal endpoints are not exposed:** anything under `/api/<service>/internal` is blocked at the gateway. Services call each other directly inside Docker, e.g. `http://routing:8000/internal/...`.
- **Database:** `postgres/init/20-create-service-schemas.sh` runs once, on first start. It enables PostGIS and creates one database user and one schema per service (`accounts`, `trips`, `routing`, `payments`, `notifications`). Each user can only create and read tables in its own schema. To run it again, delete the data with `docker compose down -v`.
- **Migrations:** each service container runs `alembic upgrade head` before starting, so `docker compose up` always gives you an up-to-date database. Set `RUN_MIGRATIONS=false` on a service to skip this.
- **Images:** all five services use one Dockerfile, `docker/python-service.Dockerfile`, with a `SERVICE` build argument. It installs dependencies from `uv.lock` in a cached layer, then copies the code, and runs as a non-root user.

## Running one service outside Docker

For fast edit-and-reload on the service you're working on, start just the infrastructure in Docker and run your service with uv:

```bash
docker compose up -d postgres redis mailpit
uv run --package trips uvicorn trips.infrastructure.main:app --reload --port 8002
```

The service's default `*_DATABASE_URL` already points at `localhost:5432` with its own user. Alembic works the same way: `cd services/trips && uv run alembic upgrade head`.

## Configuration

Every setting has a local default in `docker-compose.yml`, so no `.env` file is needed. To change one (for example if port 5432 or 80 is already in use on your machine), create `.env` in the repo root:

```bash
POSTGRES_PORT=5433
GATEWAY_PORT=8000
```

The passwords here are for local development only. The live server sets its own in a `.env` file that is never committed.

## Common problems

| Problem | Fix |
|---|---|
| `port is already allocated` | Something else uses that port. Stop it, or change the port in `.env` (see above). |
| Postgres is slow to start on a Mac with Apple silicon | The PostGIS image is x86-64 only, so Docker emulates it. It works; first start takes longer. |
| Changed `20-create-service-schemas.sh` but nothing happened | It only runs on an empty database: `docker compose down -v`, then `up` again. |
| A service keeps restarting | `docker compose logs <service>`: usually a failed migration or a database it can't reach. |
| `client version 1.24 is too old` from Traefik | Your Traefik image is older than v3.6. Run `docker compose pull traefik`. |
