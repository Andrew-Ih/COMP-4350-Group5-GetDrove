# Architecture

> Back to [README](../../README.md) · [Sprint 0](../../sprint0.md) · [Technology stack](tech-stack.md) · [Decision records](adr/README.md)

This page describes the major parts of GetDrove and how they interact. It shows the full design decided in Sprint 0, updated at the end of Sprint 1, and marks which parts are built so far ([Sprint 1 status](#sprint-1-status)). It's updated every sprint. A detailed, editable version of the diagrams is in [`getdrove-architecture.drawio`](getdrove-architecture.drawio) (open it with diagrams.net or the VS Code Draw.io Integration extension).

## Components

```mermaid
flowchart TB
    users(["Riders & drivers"]) --> web

    subgraph client["Browser"]
        web["Web app<br/>Next.js + TypeScript<br/>MapLibre · TanStack Query · Stripe Elements"]
    end

    subgraph vm["Google Cloud VM · Docker Compose"]
        traefik["Traefik<br/>HTTPS · routing"]
        next["Next.js server"]

        subgraph services["Backend services · Python 3.13 + FastAPI"]
            accounts["Accounts<br/>signup · login · JWT · approval · ratings"]
            trips["Trips<br/>trips · requests · seats · execution"]
            routing["Routing<br/>routes · matching · pickups · detours"]
            payments["Payments<br/>quotes · holds · capture · earnings"]
            notify["Notifications<br/>email · reminders · in-app · chat"]
        end

        subgraph data["PostgreSQL + PostGIS · one schema per service"]
            accountsDb[("accounts")]
            tripsDb[("trips")]
            routingDb[("routing")]
            payDb[("payments")]
            notifyDb[("notifications")]
        end

        redis[["Redis<br/>event streams · cache"]]
        osrm["OSRM<br/>car + foot"]
    end

    subgraph external["External services"]
        stripe["Stripe (test mode)"]
        brevo["Brevo (email)"]
        tiles["OpenFreeMap (map tiles)"]
    end

    web -->|"HTTPS /api/*"| traefik
    web -.->|map tiles| tiles
    web -.->|card entry| stripe
    traefik --> next
    traefik --> accounts & trips & routing & payments & notify

    trips -->|reputation · blocks| accounts
    trips -->|routes · matches · pickups · detours| routing
    trips -->|quotes| payments
    routing --> osrm

    accounts <-->|events| redis
    trips <-->|events| redis
    payments <-->|events| redis
    routing <-->|events · cache| redis
    notify <-->|events| redis

    accounts --> accountsDb
    trips --> tripsDb
    routing --> routingDb
    payments --> payDb
    notify --> notifyDb

    payments --> stripe
    notify --> brevo

    classDef built fill:#e6f4ea,stroke:#2e8b57,stroke-width:2px
    classDef partial fill:#fff4e0,stroke:#d9822b,stroke-width:2px
    classDef later fill:#f5f5f5,stroke:#9e9e9e,stroke-dasharray:4 3,color:#555
    class web,traefik,next,accounts,notify,accountsDb,tripsDb,routingDb,payDb,notifyDb,redis,brevo,tiles built
    class trips,routing,osrm partial
    class payments,stripe later
```

**Key:** green = built in Sprint 1 · orange = partly built (in progress) · grey dashed = later sprints. Each box lists everything the component will do, not only what's built; see [Sprint 1 status](#sprint-1-status).

| Component | Responsibility |
|---|---|
| **Web app** | Next.js + TypeScript client for riders and drivers. Mobile-first, responsive. Pages stay thin; logic lives in feature modules. |
| **Traefik** | The only public entry point. HTTPS via Let's Encrypt (the live site is plain HTTP until [#110](https://github.com/Andrew-Ih/COMP-4350-Group5-GetDrove/issues/110)); routes `/api/<service>/*` to services and everything else to the Next.js server. No business or auth logic. |
| **Accounts** | Signup restricted to `@myumanitoba.ca`, email verification, login, JWT issuing (RS256) and the JWKS endpoint, driver documents and vehicle, admin approval, ratings, reputation, blocks, reports. |
| **Trips** | One-off and recurring trips, seat requests, eligibility rules, manual and automatic acceptance, atomic seat counting, trip execution (start, pickup, no-show, complete), share links. |
| **Routing** | Computes and stores driving routes (PostGIS), finds trips that pass near a rider by road-network distance, suggests pickup points, calculates detours with pickup ordering, and returns rider-safe route geometry (driver's start hidden). Uses OSRM. |
| **Payments** | Distance-based price quotes, rider card setup, holds on acceptance, capture after completion, release on cancellation, earnings ledger with simulated weekly settlement. Uses Stripe in test mode. |
| **Notifications** | In-app and email notifications, scheduled reminders, and trip group chat. The browser polls for new messages and notifications every few seconds. Uses Brevo for email in production and Mailpit locally. |
| **PostgreSQL + PostGIS** | One instance; each service has its own schema and database user, so services can't read each other's data. |
| **Redis** | Event streams between services and a cache for routing data. Runs with AOF persistence. |
| **OSRM** | Self-hosted routing engine with car and foot profiles, built from a Winnipeg map extract ([infra/osrm](../../infra/osrm/README.md)). |

## Communication boundaries

- **Browser to backend:** REST over HTTPS, always through Traefik. One origin, so no CORS in production. Trip chat and notifications are polled every 3–5 seconds while they're open; there are no WebSockets in the core design. Live driver tracking is a stretch goal ([ADR 0018](adr/0018-live-tracking-as-stretch-goal.md)).
- **Authentication:** Accounts issues short-lived JWTs (15 minutes). **Each service validates tokens itself** using Accounts' public key (JWKS). Traefik does no auth. The web app keeps the access token in memory and gets a new one with a refresh token in an `HttpOnly` cookie, which is swapped on every use ([ADR 0022](adr/0022-login-sessions.md)).
- **Synchronous calls between services:** REST over the private Docker network to `/internal/…` endpoints, which Traefik never exposes. Used when the caller needs an answer immediately (e.g. Trips asking Routing for a detour quote).
- **Asynchronous events:** published to **Redis Streams** through a **transactional outbox** (the event is saved in the same database transaction as the change, then relayed). Each consuming service reads with its own consumer group and processes events idempotently, so events survive restarts and duplicates are harmless.
- **Data ownership:** a service only reads and writes its own schema. Other services' data is reached only through APIs or events.
- **External services:** Stripe (payments), Brevo (email), and OpenFreeMap (map tiles, loaded directly by the browser). Card details go from the browser straight to Stripe and never touch our servers.

## Sprint 1 status

| Part | Status at the end of Sprint 1 |
|---|---|
| **Web app** | Built: signup, email verification, login (stays logged in, log out), rider home, search results with routes on the map, post a trip. Screens whose endpoints aren't live yet run on the mock API (`npm run dev:mock`). |
| **Traefik** | Built: routes `/api/<service>/*` to the services and everything else to the web app, never exposes `/internal`. HTTPS is [#110](https://github.com/Andrew-Ih/COMP-4350-Group5-GetDrove/issues/110). |
| **Accounts** | Built: signup (UofM emails only), email verification and resend, login, refresh and logout with reuse detection, `GET /me`, JWKS. Driver approval, ratings and blocks come later. |
| **Notifications** | Built: consumes `UserRegistered` and `VerificationEmailRequested` and sends the verification email, handling each event once and parking ones that keep failing. |
| **Trips** | In progress: contract written for posting, my trips, trip detail and search; trip posting in review. |
| **Routing** | In progress: contract written for routes, matches and route geometry; OSRM runs locally ([infra/osrm](../../infra/osrm/README.md)). Storing routes and matching are next; OSRM on the live server is [#233](https://github.com/Andrew-Ih/COMP-4350-Group5-GetDrove/issues/233). |
| **Payments** | Contract only (internal price quote). |
| **PostgreSQL, Redis** | Built: one schema and user per service, migrations run on start; the outbox and Redis Streams carry the Accounts events. |
| **Deployment** | Built: merging to `main` builds the images in GitHub Actions, deploys them to the VM and runs a smoke test. Real emails go out through Brevo. |

## Flow built in Sprint 1: signing up and verifying an email

This is the first flow that crosses services, and it runs end to end today.

```mermaid
%%{init: {'sequence': {'mirrorActors': false}}}%%
sequenceDiagram
    autonumber
    actor Student
    participant Web as Web app
    participant Accounts
    participant Streams as Redis Streams
    participant Notify as Notifications
    participant Email as Brevo (Mailpit locally)

    Student->>Web: Sign up with a @myumanitoba.ca email
    Web->>Accounts: POST /api/accounts/auth/signup
    Note over Accounts: Saves the user and UserRegistered (outbox) in one transaction
    Accounts-->>Web: 201, check your email
    Accounts->>Streams: Outbox relay publishes UserRegistered
    Streams->>Notify: UserRegistered (consumer group "notifications")
    Notify->>Email: Verification email with a 24-hour link
    Email->>Student: "Verify your GetDrove account"
    Student->>Web: Opens the link
    Web->>Accounts: POST /api/accounts/auth/verify
    Accounts-->>Web: Verified
    Student->>Web: Log in
    Web->>Accounts: POST /api/accounts/auth/login
    Accounts-->>Web: Access token (body) + refresh cookie
```

If Notifications is down, `UserRegistered` waits in the stream and the email goes out when it's back. Asking for a new link publishes `VerificationEmailRequested`, which takes the same path.

## Example flow (planned): a rider requests a seat and the driver accepts

```mermaid
%%{init: {'sequence': {'mirrorActors': false}}}%%
sequenceDiagram
    autonumber
    actor Rider
    participant Trips
    participant Routing
    participant Accounts
    participant Streams as Redis Streams
    participant Payments
    participant Notify as Notifications
    actor Driver

    Rider->>Trips: Request a seat (pickup point)
    Trips->>Accounts: Blocked? Reputation?
    Trips->>Routing: How much detour does this pickup add?
    Routing-->>Trips: +3 minutes, pickup 2nd in order
    Trips-->>Rider: Request pending
    Trips->>Streams: SeatRequested (via outbox)
    Streams->>Notify: SeatRequested
    Notify->>Driver: New request, adds 3 min

    Driver->>Trips: Accept
    Note over Trips: Atomic seat update, then RequestAccepted saved to outbox
    Trips->>Streams: RequestAccepted
    Streams->>Payments: RequestAccepted
    Payments->>Payments: Hold the rider's share in Stripe
    Streams->>Routing: Update pickup order and ETAs
    Streams->>Notify: RequestAccepted
    Notify->>Rider: Confirmed, pickup at 7:48
```

## Deployment

Everything runs as Docker containers on one **Google Cloud Compute Engine VM** (e2-standard-2, Ubuntu 24.04, Toronto region), started with Docker Compose. Every pull request into `develop` or `main` runs the tests in GitHub Actions. Every merge to `main` (a release or hotfix) builds `linux/amd64` images, pushes them to GitHub Container Registry, deploys them to the live site and runs a smoke test. Planned: building images on every merge to `develop` ([#176](https://github.com/Andrew-Ih/COMP-4350-Group5-GetDrove/issues/176)) and publishing versioned images to DockerHub on release tags ([#189](https://github.com/Andrew-Ih/COMP-4350-Group5-GetDrove/issues/189)). The same Compose setup runs the whole system locally with one command. See [ADR 0016](adr/0016-google-cloud-hosting-and-deploy-from-main.md) and the [server setup guide](../deployment/server-setup.md).

## How the design supports our non-functional expectations

- **Routing is isolated** because it's the most expensive service and the main scalability bottleneck. It can be load-tested and optimized on its own, and if it's down, accepted trips are unaffected.
- **Notifications is decoupled through events**, so trips keep running if it's down; events wait in Redis and are delivered once it recovers.
- **One schema per service** keeps data ownership clear and stops services depending on each other's internals.
- **The outbox and idempotent consumers** mean no event is lost or applied twice.

See [non-functional expectations](../product/non-functional.md).
