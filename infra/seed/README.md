# Demo seed data

Fills GetDrove with everything a demo needs (#111, #180): verified riders and drivers, the
drivers' cars and approvals (one left pending for the admin to review), trips across
Winnipeg for the next two weeks (one of them a recurring series), saved test cards, and
seat requests, some already accepted. It works the same locally and on the live site, and
running it again is safe.

## The demo people

Everyone has the same password: whatever you set in `SEED_PASSWORD` (locally) or the
`DEMO_ACCOUNT_PASSWORD` secret (live). It must be at least 10 characters and is never
committed. Emails are `getdrove.demo.<first name>@myumanitoba.ca`, for example
`getdrove.demo.maya@myumanitoba.ca`.

| Driver       | Home            | Car                        | To campus                  | From campus         | Seats |
| ------------ | --------------- | -------------------------- | -------------------------- | ------------------- | ----- |
| Maya Chen    | Osborne Village | Blue Toyota Corolla GDMAYA1 | Mon, Wed, Fri 07:45        | Mon, Wed, Fri 16:30 | 3     |
| Tomas Rivera | St. Vital       | Grey Honda Civic GDTOM02   | Mon–Fri 08:00              | Mon–Fri 17:00       | 2     |
| Aisha Okafor | Transcona       | White Kia Sorento GDAIS03  | Tue, Thu 07:30 (a series)  | Tue, Thu 15:45      | 4     |
| Liam Fraser  | River Heights   | Red Mazda 3 GDLIA04        | Mon–Fri 08:15              | Tue, Thu 16:00      | 3     |
| Sam Patel    | Fort Garry      | Black Ford Escape GDSAM05  | **pending approval**: no trips |                 |       |

| Rider         | Home                    | Card      | For showing                                   |
| ------------- | ----------------------- | --------- | --------------------------------------------- |
| Priya Sharma  | Pembina Hwy, Fort Rouge | test Visa | an **accepted** seat on Maya's next trip to campus |
| Noah Bergen   | Pembina Hwy & Grant Ave | test Visa | a **pending** request on the same trip, for Maya to accept or decline |
| Emma Tran     | St. Vital Centre        | test Visa | an **accepted** seat on Tomas's next trip to campus |
| Owen Campbell | Garden City             | none      | a rider far from every route, who's asked to add a card |

| Admin       | For showing                                        |
| ----------- | -------------------------------------------------- |
| Alex Morgan | reviewing Sam's application (admin role: locally only, see below) |

Times are Winnipeg time. "A series" is posted as one recurring series (#15) running four
weeks, so cancelling one occurrence or the whole series can be shown. The test card is
Stripe's `4242 4242 4242 4242`; accepting a request puts a test-mode hold on it, nothing
real is charged.

To change any of this, edit [`demo.json`](demo.json); the tests check it (emails, places
inside Winnipeg, weekdays, seats 1–6, cars, that a requesting rider has a card and the
driver is approved and drives that way).

## How it works

Two parts, because accounts and the rest are created differently:

1. **Accounts**: `python -m accounts.infrastructure.seed`, run inside the Accounts
   container, reads `demo.json` and creates each person already verified. It doesn't go
   through sign-up, because sign-up would email the made-up addresses and the bounces
   would hurt our email sender's reputation. On the live site, Notifications doesn't email
   them later either (`NOTIFICATIONS_EMAIL_SKIP_PATTERNS`, #415): they see their
   notifications in the app's bell.

   It then puts each driver through the same steps as a real one: their car, placeholder
   licence and insurance PDFs (they say "not a real document"), and approval by the demo
   admin, which publishes `DriverApproved` so Trips lets them post. A driver marked
   `"approval": "pending"` is left waiting. People and steps that are already done are
   skipped.

   With `SEED_DEMO_ADMIN=true` it also gives the demo admin the admin role. **Only
   locally**: an admin can open every applicant's documents, and the demo password is
   shared with testers. On the live site, give a team member's own account the role with
   the `make_admin` command (see [infra/README.md](../README.md)).
2. **Cards, trips and requests**: [`seed_trips.py`](seed_trips.py) logs in as each person
   and does what they'd do in the app, through the API:
   - riders with `"card": true` save Stripe's test card, as the card form does (Payments
     makes a SetupIntent; the script confirms it with Stripe using the publishable key);
   - drivers post their commutes for the next two weeks (`POST /api/trips/`), or one
     recurring series (`POST /api/trips/series`) where `"repeat": true`. Routing works out
     and stores the real routes. Only missing trips are posted;
   - each rider in `requests` asks for a seat on that driver's next trip that way (at least
     two hours away), from home, at the nearest pickup point, and the driver accepts it
     where `"status": "accepted"`. A request that's already there is left alone.

   Cards and requests need `STRIPE_PUBLISHABLE_KEY` (`pk_test_...`) from the same Stripe
   sandbox as Payments' secret key. Without it, the script still posts trips and says what
   it skipped.

## Run it locally

With the Docker stack running (see [infra/README.md](../README.md)), from the repo root.
`STRIPE_PUBLISHABLE_KEY` is the `pk_test_` key that goes with your
`PAYMENTS_STRIPE_SECRET_KEY` in `.env`.

macOS / Linux / Git Bash:

```bash
export SEED_PASSWORD='<a demo password, 10+ characters>'
export STRIPE_PUBLISHABLE_KEY='pk_test_...'
docker compose exec -T -e SEED_PASSWORD -e SEED_DEMO_ADMIN=true accounts python -m accounts.infrastructure.seed < infra/seed/demo.json
uv run python infra/seed/seed_trips.py --site http://localhost
```

PowerShell:

```powershell
$env:SEED_PASSWORD = "<a demo password, 10+ characters>"
$env:STRIPE_PUBLISHABLE_KEY = "pk_test_..."
Get-Content infra\seed\demo.json -Raw | docker compose exec -T -e SEED_PASSWORD -e SEED_DEMO_ADMIN=true accounts python -m accounts.infrastructure.seed
uv run python infra/seed/seed_trips.py --site http://localhost
```

The accounts part prints `created` (or `exists`) for the ten people, `admin` for Alex,
`approved` for four drivers and `pending` for Sam. The second part prints a `card` line per
rider with a card, a `posted` line per approved driver (Aisha's says `(1 recurring
series)`), and a `request` line per request. Run both again straight away: everyone
`exists`, the drivers say `driving` and `0 new trips`, the cards say `already has a card`
and the requests keep their status.

## Run it on the live site

From GitHub: **Actions → Seed demo data → Run workflow** on `main`, after the release is
deployed. The workflow ([`seed-demo.yml`](../../.github/workflows/seed-demo.yml)) runs
the accounts part on the server over SSH with the deploy key (without `SEED_DEMO_ADMIN`),
then the second part against https://getdrove.duckdns.org. Nobody needs server access.

It needs the `DEMO_ACCOUNT_PASSWORD` secret in the `production` environment
(Settings → Environments → production), and the `STRIPE_PUBLISHABLE_KEY` variable the web
image is built with. Whoever sets the password shares it with the team for demos.

## Common problems

- **`couldn't log in (401 ...)`** from the second part: the accounts part hasn't run, or it
  ran with a different password. An account keeps the password it was created with.
- **`a trip was refused (403 driver_not_approved)`**: Trips never heard that the driver
  was approved. The script waits about 30 seconds for the `DriverApproved` event; if it
  still fails, check the Accounts outbox relay and the Trips consumer are running
  (`docker compose logs accounts trips`).
- **`Stripe didn't save the test card (401 ...)`**: `STRIPE_PUBLISHABLE_KEY` is wrong.
  **`(400 resource_missing)`**: it's from a different Stripe account than Payments' secret
  key.
- **`the request was refused (409 card_required)`**: the rider has no card. Their `card`
  line above it says why (usually no `STRIPE_PUBLISHABLE_KEY`).
- **`the driver has no upcoming trip that way`**: the driver's trips weren't posted (look
  for their `FAILED` line above it).
- **`couldn't list their trips (501 not_implemented)`** locally: your Trips container is
  older than the "my trips" feature. Rebuild it:
  `docker compose up -d --build trips`.
