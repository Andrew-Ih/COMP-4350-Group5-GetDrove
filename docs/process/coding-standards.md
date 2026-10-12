# Coding Standards

> Part of the [team process docs](../../CONTRIBUTING.md). Back to [README](../../README.md).

## Tech stack

See the [technology stack](../architecture/tech-stack.md): Python 3.13 + FastAPI with uv for the backend, Next.js + TypeScript for the frontend.

## Formatting and linting

| Area | Formatter | Linter |
|---|---|---|
| Frontend (Next.js + TypeScript) | Prettier | ESLint |
| Backend (Python 3.13 + FastAPI) | Ruff (`ruff format`) | Ruff (`ruff check`) and mypy --strict |

- Run the formatter before every commit (`uv run ruff format` and `uv run ruff check --fix` for Python, `npm run format` for the frontend). Pull requests with lint or type errors are not merged; CI runs Ruff, mypy, and ESLint on every pull request.
- Type hints are required on all Python functions and class attributes (mypy strict). Don't silence mypy with `# type: ignore` or `Any` without a comment explaining why.

## Naming

- TypeScript: `camelCase` for variables and functions, `PascalCase` for components, types, and classes, `UPPER_SNAKE_CASE` for constants.
- Python ([PEP 8](https://peps.python.org/pep-0008/)): `snake_case` for variables, functions, and modules; `PascalCase` for classes; `UPPER_SNAKE_CASE` for constants; package names lowercase (`trips.domain`).
- JSON fields in APIs and events use `camelCase` (Pydantic aliases), so the frontend's generated TypeScript types read naturally.
- REST endpoints use plural nouns and kebab-case, e.g. `/trips/{id}/seat-requests`.

## Code quality

- Write clean, readable code with comments that explain *why*, not *what*.
- Keep functions short and focused on one job.
- No emoji in code, comments, or log messages.
- Don't commit code you don't understand, including AI-generated code (see the GenAI rules in the [working agreement](working-agreement.md)).
- Handle errors explicitly. Failed requests return a meaningful error message, never a blank 500, and users never see a blank screen.
- Never hard-code secrets, API keys, or URLs. Use environment variables, and keep a `.env.example` file up to date without real values. Never paste secrets or private data into AI tools.
- Only Stripe **test** keys are used anywhere in this project. No real card data touches our systems.
- Discuss major changes with the team before starting them.

## Services

- Each service follows the Clean Architecture layout (`domain`, `application`, `adapters`, `infrastructure`); import-linter enforces that inner layers never import outer ones, and FastAPI, SQLAlchemy, and other frameworks are only imported in `adapters` and `infrastructure`.
- Code is async end to end: use async drivers and clients (asyncpg, redis.asyncio, httpx), never blocking calls inside request handlers.

- Each service owns its own database schema and never reads another service's data directly.
- Services communicate only through documented APIs or events. Changes to an API or event format are discussed with the team first.
- Every service has a README covering what it does, how to run it, its API, and the tools its owner chose and why.
- The whole system must keep running locally with a single Docker Compose command. If you add a service or dependency, add it to the Compose file.

## Errors and logging

- Every service calls `install(app, service="<name>")` from `common_web.app`, which gives all services the same error format, request IDs and logging. See [libs/common-web](../../libs/common-web/README.md).
- To return an error, raise a subclass of a `common_web` error (`NotFoundError`, `ConflictError`, `ForbiddenError`, `InvalidInputError`, …) with its own `code`, e.g. `NoSeatsLeftError(ConflictError)` with `code = "no_seats_left"`. Don't raise FastAPI's `HTTPException` from domain or application code.
- Error `code` values are part of the API contract: the frontend checks them, so don't rename them without telling the team.
- Log with Python's `logging` (`logger = logging.getLogger(__name__)`), adding fields with `extra={...}` ([ADR 0019](../architecture/adr/0019-standard-library-logging.md)).
- **Never log personal data**: no emails, names, addresses, locations, passwords or tokens. Log IDs instead.
- When calling another service, send the current request ID (`common_web.current_request_id()`) as the `X-Request-ID` header; when publishing an event, use it as the `correlation_id`.

## Documentation

Documentation is updated in the same pull request as the code it describes.

## Testing

- New backend logic comes with unit tests. We aim for around 70% coverage on core logic.
- Tests run automatically in CI (GitHub Actions) on every pull request.
- Each user story's acceptance criteria should be covered by at least one test where practical.
- Concurrency-sensitive code (such as seat booking) must have a test that simulates simultaneous requests.
- Run the full test suite locally before opening a pull request (`uv run pytest` for a service, `npm test` for the frontend).
