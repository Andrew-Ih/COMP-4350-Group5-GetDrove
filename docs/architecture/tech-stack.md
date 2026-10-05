# Technology Stack

> Back to [README](../../README.md) · [Sprint 0](../../sprint0.md)

These are our starting choices for Sprint 0. We expect some to change as the project develops; changes are recorded here.

## Team-wide choices

| Area | Choice | Status | Why |
|---|---|---|---|
| Architecture | Microservices | Decided | Each service is owned end to end, services can be built in parallel, and a failure in one doesn't take down the others. See [architecture](architecture.md). |
| Source control and CI/CD | GitHub and GitHub Actions | Decided | Tests run on every pull request, and `main` deploys automatically. Security and dependency scanning added for the final iteration. |
| Backend | Spring Boot **or** FastAPI | Decide in Sprint 1 | See below. |
| Frontend | React with TypeScript | Decided | Familiar to the team, and TypeScript catches mismatches with the service APIs early. |
| Database | PostgreSQL, one schema per service, with PostGIS where needed | Decided | Reliable and widely used. Separate schemas keep each service's data private, and PostGIS supports the location queries needed for route matching. |
| Message broker | Redis Streams | Tentative | Lets services react to events without calling each other directly, and is simpler to run than the alternatives. RabbitMQ is the alternative. |
| API gateway | Traefik | Tentative | A single entry point for the frontend that forwards each request to the right service and can check login tokens in one place. |
| Local environment | Docker Compose | Decided | The whole system, including the routing engine, runs with one command, so everyone is on the same setup and nobody loses time to environment problems. Images published to DockerHub for the final release. |
| Payments | Stripe (test mode) | Decided | Supports holding funds on acceptance and capturing them after the trip. No real card data touches our systems. |

### Backend: Spring Boot or FastAPI

- **Spring Boot** is stronger on team familiarity, since most of us know Java from coursework. It's opinionated about structure, which helps when several people are writing services that should look alike.
- **FastAPI** is lighter, faster to write, and generates OpenAPI docs with no extra setup.

We'll decide in Sprint 1.

## Owner choices

Each service's owner chooses the tools used inside their service, such as the routing engine, map library, file storage, or email provider, and documents the choice and reasoning in that service's README.

- PostgreSQL is the default database for all services. An owner can choose a different one if their service has a clear need.
- Any choice that affects other services, such as a new API or event format, is discussed with the team first.

## Still to decide as a team

- Backend framework (Spring Boot or FastAPI)
- Message broker (Redis Streams or RabbitMQ)
- API gateway
- Where we deploy for the Sprint 1 demo
