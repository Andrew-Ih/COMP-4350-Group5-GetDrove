# Demo seed data

Fills GetDrove with verified demo riders and drivers, and drivers' trips across Winnipeg, so
there is something to search for in a demo (#111). It works the same locally and on the live
site, and running it again is safe.

## The demo people

Everyone has the same password: whatever you set in `SEED_PASSWORD` (locally) or the
`DEMO_ACCOUNT_PASSWORD` secret (live). It must be at least 10 characters and is never
committed. Emails are `getdrove.demo.<first name>@myumanitoba.ca`, for example
`getdrove.demo.maya@myumanitoba.ca`.

| Driver       | Home            | To campus           | From campus         | Seats |
| ------------ | --------------- | ------------------- | ------------------- | ----- |
| Maya Chen    | Osborne Village | Mon, Wed, Fri 07:45 | Mon, Wed, Fri 16:30 | 3     |
| Tomas Rivera | St. Vital       | Mon–Fri 08:00       | Mon–Fri 17:00       | 2     |
| Aisha Okafor | Transcona       | Tue, Thu 07:30      | Tue, Thu 15:45      | 4     |
| Liam Fraser  | River Heights   | Mon–Fri 08:15       | Tue, Thu 16:00      | 3     |

| Rider         | Home                    | For showing                      |
| ------------- | ----------------------- | -------------------------------- |
| Priya Sharma  | Pembina Hwy, Fort Rouge | a rider on Maya's route (Mon, Wed, Fri) |
| Noah Bergen   | Pembina Hwy & Grant Ave | a rider near the drivers' routes |
| Emma Tran     | St. Vital Centre        | a rider near the drivers' routes |
| Owen Campbell | Garden City             | a rider far from every route     |

Times are Winnipeg time. To change the people or their commutes, edit
[`demo.json`](demo.json); the tests check it (emails, places inside Winnipeg, weekdays,
seats 1–6).

## How it works

Two parts, because accounts and trips are created differently:

1. **Accounts**: `python -m accounts.infrastructure.seed`, run inside the Accounts
   container, reads `demo.json` and creates each person already verified. It doesn't go
   through sign-up, because sign-up would email the made-up addresses and the bounces
   would hurt our email sender's reputation. People who already exist are skipped.
2. **Trips**: [`seed_trips.py`](seed_trips.py) logs in as each driver and posts their
   commutes for the next two weeks through the API (`POST /api/trips/`), like the app does.
   That way Routing works out and stores the real route. It compares each driver's plan with
   the trips they already have and posts only the missing ones, so running it again before a
   demo fills the next two weeks back up and never posts the same trip twice.

## Run it locally

With the Docker stack running (see [infra/README.md](../README.md)), from the repo root.

PowerShell:

```powershell
$env:SEED_PASSWORD = "<a demo password, 10+ characters>"
Get-Content infra\seed\demo.json -Raw | docker compose exec -T -e SEED_PASSWORD accounts python -m accounts.infrastructure.seed
uv run python infra/seed/seed_trips.py --site http://localhost
```

macOS / Linux / Git Bash:

```bash
export SEED_PASSWORD='<a demo password, 10+ characters>'
docker compose exec -T -e SEED_PASSWORD accounts python -m accounts.infrastructure.seed < infra/seed/demo.json
uv run python infra/seed/seed_trips.py --site http://localhost
```

You should see `created`/`exists` for the eight accounts, then `posted   Maya Chen: N new trips, 0 already there`
for each driver. Run it again straight away and every driver says `0 new trips`.

## Run it on the live site

From GitHub: **Actions → Seed demo data → Run workflow** on `main`, after the release is
deployed. The workflow ([`seed-demo.yml`](../../.github/workflows/seed-demo.yml)) runs
the accounts part on the server over SSH with the deploy key, then the trips part against
https://getdrove.duckdns.org. Nobody needs server access.

It needs the `DEMO_ACCOUNT_PASSWORD` secret in the `production` environment
(Settings → Environments → production). Whoever sets it shares the password with the team
for demos.

## Common problems

- **`couldn't log in (401 ...)`** from the trips part: the accounts part hasn't run, or it
  ran with a different password. An account keeps the password it was created with.
- **`couldn't list their trips (501 not_implemented)`** locally: your Trips container is
  older than the "my trips" feature. Rebuild it:
  `docker compose up -d --build trips`.
