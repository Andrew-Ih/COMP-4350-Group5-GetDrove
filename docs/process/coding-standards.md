# Coding Standards

> Part of the [team process docs](../../CONTRIBUTING.md). Back to [README](../../README.md).

## Tech stack

See the [technology stack](../architecture/tech-stack.md). The backend framework (Spring Boot or FastAPI) is decided in Sprint 1; the backend formatting and linting tools below are confirmed at the same time.

## Formatting and linting

| Area | Formatter | Linter |
|---|---|---|
| Frontend (React + TypeScript) | Prettier | ESLint |
| Backend | TODO (decided with the framework in Sprint 1) | TODO |

- Run the formatter before every commit. Pull requests with lint errors are not merged; CI runs the linters on every pull request.

## Naming

- TypeScript: `camelCase` for variables and functions, `PascalCase` for components, types, and classes, `UPPER_SNAKE_CASE` for constants.
- Backend: follow the standard convention of the chosen language (Java or Python).
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

- Each service owns its own database schema and never reads another service's data directly.
- Services communicate only through documented APIs or events. Changes to an API or event format are discussed with the team first.
- Every service has a README covering what it does, how to run it, its API, and the tools its owner chose and why.
- The whole system must keep running locally with a single Docker Compose command. If you add a service or dependency, add it to the Compose file.

## Documentation

Documentation is updated in the same pull request as the code it describes.

## Testing

- New backend logic comes with unit tests. We aim for around 70% coverage on core logic.
- Tests run automatically in CI (GitHub Actions) on every pull request.
- Each user story's acceptance criteria should be covered by at least one test where practical.
- Concurrency-sensitive code (such as seat booking) must have a test that simulates simultaneous requests.
- Run the full test suite locally before opening a pull request.
