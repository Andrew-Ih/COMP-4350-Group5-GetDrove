# Payments service

**Owner:** Chimdi

Pricing quotes, card setup, holds, captures and releases in Stripe test mode, driver earnings.

## Run locally

From the repo root:

```bash
uv sync
uv run --package payments uvicorn payments.infrastructure.main:app --reload --port 8004
```

Then open http://localhost:8004/health and the API docs at http://localhost:8004/docs.

## Test and check

```bash
uv run pytest services/payments
uv run mypy services/payments/src
cd services/payments && uv run lint-imports
```

## Database migrations

Tables live in the `payments` Postgres schema. With the database running and `PAYMENTS_DATABASE_URL` set:

```bash
cd services/payments
uv run alembic revision --autogenerate -m "create users table"   # after changing adapters/persistence/tables.py
uv run alembic upgrade head
```

## Layout

| Folder | What goes there |
|---|---|
| `src/payments/domain/` | Entities, value objects, rules, domain errors. Pure Python. |
| `src/payments/application/` | Use cases, and the ports (`ports.py`) they need. |
| `src/payments/adapters/` | FastAPI routers (`api/`), SQLAlchemy tables and repositories (`persistence/`), HTTP clients, event consumers. |
| `src/payments/infrastructure/` | App factory (`main.py`), settings, dependency wiring. |
| `tests/` | Tests, mirroring the layers. |

import-linter enforces that inner layers never import outer ones, and that `domain` and `application` never import FastAPI, SQLAlchemy or settings.

## API

_To be filled in as endpoints are added: link to the OpenAPI spec in `contracts/openapi/payments.yaml`._

## Events

_Published and consumed events, linking to `contracts/events/`._

## Stripe test mode

The official async Stripe Python SDK lives in `adapters/stripe_gateway.py`, behind
`application/ports.py::PaymentGatewayPort`. The infrastructure factory accepts Settings;
use cases must depend on the port, never import Stripe. Every write requires an explicit
idempotency key. Reuse it when retrying the same logical operation. Card HTTP endpoints
remain placeholders until #151. This setup does not store customer IDs or process events.

1. Create a Stripe account and select its testing environment (test mode or a Sandbox).
2. Copy the **test secret key** (`sk_test_...`) from Stripe's API keys page to your local,
   gitignored `.env` as `PAYMENTS_STRIPE_SECRET_KEY`. Never paste keys into chat or commit them.
   Live keys are rejected. No key is needed for health or pricing.
3. Ask a repository administrator to add the same test secret key as the GitHub Actions
   secret `PAYMENTS_STRIPE_SECRET_KEY`. The deploy workflow checks it and writes it into
   the server's protected `.env`; production Compose passes it only to Payments.
   See [deployment](../../docs/deployment/deployment.md#3-secrets). Account creation and
   secret provisioning are manual prerequisites, not performed by this code change.
4. Frontend Stripe Elements will need the matching publishable **test** key when card UI
   is wired. It must belong to the same testing environment; never expose the secret key.

### Mock testing

With Docker Desktop's Linux engine running:

```bash
uv run pytest services/payments
```

`test_stripe_mock.py` starts and removes its own pinned `stripe/stripe-mock:v0.197.0`
container and verifies customer + SetupIntent creation through the real SDK.
The mock is pinned to match stripe-python 14: mock 0.206.0's newer schema renames
`payment_method_types` to `allowed_payment_method_types`. Upgrade the SDK and mock together. Unit tests
also inspect SDK requests for manual capture, off-session setup and idempotency headers.

For a persistent mock while developing:

```bash
docker compose -f infra/docker-compose.yml --profile payments-test up -d stripe-mock
```

Use `PAYMENTS_STRIPE_SECRET_KEY=sk_test_mock` and
`PAYMENTS_STRIPE_API_BASE=http://localhost:12111` for a service running on the host.
When Payments itself runs in Compose, use `http://stripe-mock:12111` instead.
Do not override the API base on the deployed server.

stripe-mock validates request schemas; it does not simulate card declines, authorization
expiry or the payment lifecycle. Verify those flows in Stripe's testing environment as
holds and failure handling are implemented. See [stripe-mock](https://github.com/stripe/stripe-mock).

### Holds spike (#68)

- Save a card using a customer-bound SetupIntent with `usage=off_session`; Stripe Elements
  collects the card directly and confirms setup. Persist the customer mapping in #151.
- On acceptance (#70), create and confirm a PaymentIntent for the agreed amount in cents,
  with `capture_method=manual` and the customer's saved payment method. Off-session
  authorization can still require authentication or fail; #153 must handle those outcomes.
  Only `requires_capture` means funds were held; creating an intent alone is insufficient.
- After trip completion, capture that same intent. Before capture, cancellation releases
  the hold by cancelling the intent. After capture, cancellation needs a Refund (#72),
  not the gateway's `cancel` method.
- Authorizations expire. Use Stripe's actual `capture_before` deadline rather than assuming
  every card has a seven-day window. #154 will schedule authorization closer to departure
  for distant bookings and account for trip duration before attempting a hold.
- Persist payment IDs, state and operation keys before implementing event-driven retries;
  duplicate events must not create duplicate holds or captures. Real completion/failure
  handling and webhook verification belong to the follow-up payment tasks.

References: [manual capture](https://docs.stripe.com/payments/place-a-hold-on-a-payment-method),
[save cards for later](https://docs.stripe.com/payments/save-and-reuse).
