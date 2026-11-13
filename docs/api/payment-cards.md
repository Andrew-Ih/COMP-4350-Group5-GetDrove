# Card setup endpoints (#151)

## What this does

Implements the existing Payments card contracts using the Stripe test-mode adapter from
#68. The browser collects card details with Stripe Elements; Payments receives no card
number or CVC.

| Endpoint (gateway prefix `/api/payments`) | Behaviour |
|---|---|
| `POST /setup-intent` | Requires a login token. Creates or reuses that user's Stripe customer and returns `201 {"clientSecret": "..."}`. |
| `GET /methods` | Requires a login token. Reads that customer's cards from Stripe and returns ID, brand, last four digits, expiry and `isDefault`. Returns `[]` for no card. |
| `GET /internal/customers/{user_id}/card` | For Trips on the internal network: returns `userId` and `hasCard`. The gateway blocks `/internal` paths. |

The `payments.customers` table stores the user ID, Stripe customer ID and default
payment-method ID. It stores no card display details. A row lock serializes customer
creation across simultaneous requests. The mapping is committed before SetupIntent
creation, so retrying a failed setup reuses the existing customer.

Card lists are fetched from Stripe each time, including all pages. After Elements
confirms setup, refetch `/methods` to see the saved card. The card with the latest Stripe
creation timestamp becomes the local default; IDs break timestamp ties consistently.
There is no card deletion or default-selection endpoint in Sprint 2. The internal card
check refreshes that same default, for later holds to use. Provider failures return
`503` with code `payments_unavailable` rather than an empty card list.

## Setup and migration

Use the same `PAYMENTS_STRIPE_SECRET_KEY=sk_test_...` in the root `.env` as for #68.
The frontend's `STRIPE_PUBLISHABLE_KEY=pk_test_...` must belong to the same sandbox.
Use the real Stripe API base for a browser test: stripe-mock does not maintain saved-card
state and cannot replace the sandbox for Elements confirmation.

With the local database running and `PAYMENTS_DATABASE_URL` configured:

```powershell
# Run from the repository root so Settings reads the root .env.
uv sync --locked
uv run --package payments alembic -c services/payments/alembic.ini upgrade head
uv run --package payments uvicorn payments.infrastructure.main:app --reload --port 8004
```

Docker images already run Alembic through the shared entrypoint. Only the new
`payments.customers` table is added by this migration.

## Automated tests

Start Docker Desktop's Linux engine, then run from the repository root:

```powershell
uv run pytest services/payments -rs
uv run ruff format --check services/payments
uv run ruff check services/payments
uv run mypy services/payments/src
```

Architecture check:

```powershell
Push-Location services/payments
uv run lint-imports
Pop-Location
```

The tests use fake keys and throwaway containers, never the developer database or real
Stripe account. They cover authentication, isolation between users, customer reuse,
refreshing cards and defaults, provider failures, SDK pagination and error translation,
PostgreSQL persistence, concurrent setup requests, and HTTP endpoints against stripe-mock.
Docker tests are skipped if the engine is stopped; rerun with Docker to verify them.
Stripe/httpx deprecation warnings do not fail the tests.

## Manual sandbox test

1. Run the service and apply the migration. Log into GetDrove and obtain an access token.
2. Call `POST http://localhost:8004/setup-intent` with `Authorization: Bearer <token>`.
   Expect 201 and a client secret. Repeat to verify that the same user has one customer
   mapping, even though each attempt gets its own SetupIntent.
3. Before adding a card, `GET /methods` should return `[]` and the internal check should
   return `hasCard: false`.
4. Use the card form from #152 with the matching publishable sandbox key. Stripe Elements
   confirms the SetupIntent; use Stripe's standard successful test card `4242 4242 4242 4242`,
   a future expiry and a test CVC in the Elements form, never in a Payments API request.
5. Refetch `/methods`: expect the card's last four digits and `isDefault: true`. Check
   `/internal/customers/{your-user-id}/card`: expect `hasCard: true`.
6. Log in as a different user: their methods must be empty until they add their own card.
7. Verify PostgreSQL stores only customer/payment-method references, not card numbers.

Do not paste tokens, secret keys or SetupIntent client secrets into PR descriptions or
screenshots. This task saves cards; holds, captures and refunds remain separate tasks.
