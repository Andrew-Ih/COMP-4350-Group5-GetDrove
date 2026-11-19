# Deployment

> Back to [README](../../README.md). Related: [Server setup](server-setup.md) · [Local Docker setup](docker-setup.md) · [Git workflow](../process/git-workflow.md#deployment-and-branches) · Decision: [ADR 0016](../architecture/adr/0016-google-cloud-hosting-and-deploy-from-main.md), [ADR 0026](../architecture/adr/0026-releases-reuse-develop-images.md)

How the live site is deployed, which secrets it uses, how to tell whether a deploy worked, and how to roll back. The server itself is described in [Server setup](server-setup.md).

**Live site:** https://getdrove.duckdns.org (HTTPS with a Let's Encrypt certificate; the domain and certificate are described in [Server setup](server-setup.md#9-domain-and-https))

## The workflows at a glance

| Workflow | Runs on | What it does | Changes the live site? | Secrets it uses |
|---|---|---|---|---|
| [CI](../../.github/workflows/ci.yml) | Every pull request into `develop`, `main` or `feature/*` | Every check and test; both jobs are required to merge ([regression testing](../testing/regression.md)) | No | None |
| [Delivery](../../.github/workflows/delivery.yml) | Every merge into `develop` | CI again, then builds and publishes the eight images ([below](#continuous-delivery-on-develop)) | No | `GITHUB_TOKEN` only |
| [Deploy](../../.github/workflows/deploy.yml) | Every merge into `main` (a release or hotfix), or by hand | Reuses or builds the images, deploys them, smoke test, Discord alert (section 1) | **Yes** | The server, database, Stripe, JWT, email and Discord secrets (section 3) |
| [Seed demo data](../../.github/workflows/seed-demo.yml) | By hand, from `main` | Creates the demo accounts and their trips on the live site ([infra/seed](../../infra/seed/README.md)) | Adds demo data | `DEPLOY_*`, `DEMO_ACCOUNT_PASSWORD` |
| [CodeQL](../../.github/workflows/codeql.yml) | Pull requests into `develop` and `main`, and every Monday | Security analysis of the Python and TypeScript code | No | None |

Each one's result is a green or red run in the Actions tab and a check on the commit. Only Deploy alerts on Discord, since only it can break the live site.

## 1. How a deploy happens

The live site tracks **`main`**, so it only changes when we release ([Git workflow](../process/git-workflow.md#making-a-release)):

```text
release/x.y.z ──PR──▶ main ──▶ Deploy workflow (.github/workflows/deploy.yml)
                                 1. images  reuse the images Delivery built for develop, tagged with this commit
                                 2. build   only if there's nothing to reuse: eight images → GitHub Container Registry
                                 3. deploy  copy files to the server, write .env, pull, restart
                                 4. smoke   home page + every /health over HTTPS, http redirects,
                                            then a browser test: a demo rider logs in and searches
                                 5. alert   a message on Discord if any step failed
```

1. **Images.** A release merges `develop` into `main`, so the release commit has exactly the files of a `develop` commit whose images the [Delivery workflow](#continuous-delivery-on-develop) already built and tested. The first job checks that (same files as the merge's `develop` parent, and all eight images published for it) and adds the release commit's tag to those same images in the registry, which takes seconds and doesn't download anything. What goes live is then exactly what was tested on `develop` (#177).
2. **Build, only when there's nothing to reuse:** a hotfix committed to `main` directly, a release merged before Delivery finished publishing `develop`'s images, or a run with **refresh_map** ticked. GitHub Actions builds one image per service, one for the web app, and two for OSRM (car and foot, with the Winnipeg map built in; see [Routing engine](#routing-engine-osrm)), for `linux/amd64`, and pushes them to GitHub Container Registry as `ghcr.io/andrew-ih/getdrove-<name>:<commit SHA>`. Builds are cached, so unchanged images take seconds. The run's summary says which of the two happened.
3. **Deploy.** Actions connects to the server over SSH with the deploy key and:
   - copies `infra/docker-compose.prod.yml` and the database setup script to `/opt/getdrove`
   - writes `/opt/getdrove/.env` from GitHub Secrets (readable only by the server user)
   - logs in to the registry for the pull only, then runs `docker compose pull` and `docker compose up -d --wait`, which restarts only the containers whose image changed and waits until every container is healthy
   - checks from inside the Routing container that both OSRM instances return a realistic Osborne Village → University Centre route
   - removes images older than a week, so the disk doesn't fill up
4. **Smoke test.** Actions calls the live site from outside over HTTPS (which also checks the certificate is valid): the home page, every service's `/health`, and Accounts' public key (`/.well-known/jwks.json`). It checks that plain `http://` redirects to HTTPS and that `/api/<service>/internal/...` is **not** reachable. Then a browser test ([`e2e/`](../../e2e/README.md), Playwright in Chromium) does what a student does: logs in as the demo rider Priya and searches for a ride from Osborne Village to campus on the next weekday morning. It passes when the results heading shows ("3 trips tomorrow" or "No trips tomorrow"); whether trips come back depends on when the demo seed last ran. A failed browser test keeps a screenshot and trace as the run's `smoke-test-report` artifact.
5. **Alert.** If the build, deploy or smoke test fails, a last job posts the commit and a link to the run in our Discord channel (`DISCORD_WEBHOOK_URL`), so a broken release is noticed without anyone watching Actions.

Database migrations run automatically: each service container applies its migrations when it starts.

### Saved-card payment holds (#428)

How holds work is in [ADR 0025](../architecture/adr/0025-payment-holds.md). What matters for deploying them:

Production Compose enables `PAYMENTS_HOLD_PROCESSING_ENABLED=true` and sets
`PAYMENTS_REDIS_URL=redis://redis:6379/0`. The normal lookup uses the `payments.customers`
table and Stripe, so a per-rider reference map is no longer needed. Local Compose still
defaults to disabled.

Before releasing story #150 to main:

- Merge the card setup and hold integration together. The Payments startup migration must
  include the customer table (`a15100000001`) and joined head (`a15115400001`), including
  the hold migrations. Containers apply these automatically before serving requests.
- Set GitHub Actions secret `PAYMENTS_STRIPE_SECRET_KEY` to an `sk_test_` key. The existing
  deployment secrets check and production Compose requirement remain in place; missing
  keys block deployment and live keys are rejected. The browser's publishable test key
  must belong to the same Stripe sandbox, using the existing frontend build configuration.
- Riders add their card through Stripe Elements. New authorizations resolve their current
  saved card only when due. No saved card produces the existing `PaymentFailed/no_card`
  flow; lookup outages retry without falsely returning seats. Already prepared retries
  keep their committed card references and idempotency key.

**First-deploy impact on existing seats.** On its first production start, the Payments
consumer group is created at `id="0"` and reads Trips' event history, including previous
`RequestAccepted` events. Past departures and zero-cent shares are acknowledged without
authorizing. Accepted requests for upcoming trips are scheduled for authorization under
the normal timing rules. Riders could not save cards before #151: if they still have no
saved card when authorization becomes due, `PaymentFailed/no_card` makes Trips mark the
request failed and return the seat, and Notifications tells the rider and cancels their
reminder. Existing accepted seats on upcoming trips can therefore be removed by this
first rollout, immediately for due holds or later when a far-ahead hold becomes due.

Immediately before the release, run this read-only check against the production database:

```sql
SELECT count(*)
FROM trips.seat_requests r
JOIN trips.trips t ON t.id = r.trip_id
WHERE r.status = 'accepted'
  AND t.departure_at > now();
```

If the count is not zero, identify and ask those riders to add a card before their hold
becomes due, or explicitly accept that riders without a card will lose their seats and
receive a payment-failure notification. The count identifies potentially affected seats;
it does not check whether a rider has since saved a card. Card setup must be available
for riders to add a card; if it is not yet available, make that rollout decision before
enabling holds rather than assuming the existing seats will be preserved.

This change places uncaptured test-mode holds only; final trip capture and no-show
charging remain #71 and #155.


### Continuous delivery on develop

`develop` is our main development branch, so every merged pull request goes through the **Delivery** workflow ([`.github/workflows/delivery.yml`](../../.github/workflows/delivery.yml), [runs](https://github.com/Andrew-Ih/COMP-4350-Group5-GetDrove/actions/workflows/delivery.yml)):

```text
feature/task branch ──PR (CI checks)──▶ develop ──▶ Delivery workflow
                                                     1. checks   the same checks as on pull requests (ci.yml)
                                                     2. images   eight images → GitHub Container Registry, tagged with the commit
                                                     3. summary  the published images, on the run's summary page
```

| | |
|---|---|
| **Trigger** | Every push to `develop` (a merged pull request), or by hand from the Actions tab |
| **Automated steps** | Lint, strict type checks, architecture rules, every unit and integration test with coverage, the frontend's contract check, tests and production build; then building and publishing all eight images for `linux/amd64` |
| **Environment updated** | None: it publishes deployable images (`ghcr.io/andrew-ih/getdrove-<name>:<commit SHA>`) but doesn't change the live site, which only changes when a release reaches `main` |
| **Secrets** | Only GitHub's built-in `GITHUB_TOKEN`, to push to the registry. No server secrets are used |
| **Success or failure** | A green or red run in Actions, the commit's check mark on GitHub, and the README badge. If any check fails, no images are published |

The image build is shared with the Deploy workflow ([`build-images.yml`](../../.github/workflows/build-images.yml)), so what's published from `develop` is built exactly the way it will be built for a release. Pull requests into `develop` must pass CI before they can be merged (branch protection), so a red `develop` should be rare; if it happens, the author of the merge fixes or reverts it the same day.

The workflow can also be run by hand: **Actions → Deploy → Run workflow** (from `main`). Use this to redeploy without a new release, or to roll back (section 5).

## 2. What runs on the server

`/opt/getdrove` on the server contains only what the deploy copies there:

| File | What it is |
|---|---|
| `docker-compose.prod.yml` | The production stack (from `infra/docker-compose.prod.yml`) |
| `.env` | Passwords, the token signing key and the image tag. Written by every deploy; never edit it by hand. |
| `postgres/init/20-create-service-schemas.sh` | Creates one database user and schema per service, the first time Postgres starts |

The production stack is the local one with these differences:

| | Local (`infra/docker-compose.yml`) | Live (`infra/docker-compose.prod.yml`) |
|---|---|---|
| Images | Built on your machine | Pulled from GitHub Container Registry, tagged with the commit |
| Passwords and keys | Local defaults | From `.env`, which comes from GitHub Secrets; missing values stop the deploy |
| Reachable from outside | Gateway, database, Redis, Mailpit, Traefik dashboard | **Only the gateway:** HTTPS on 443 for `getdrove.duckdns.org`; port 80 only redirects to HTTPS |
| Gateway access log | — | Off: request URLs hold riders' locations, which must never be stored. Each service logs its own requests, path only. |
| Email | Caught by Mailpit (http://localhost:8025) | Sent for real through Brevo's SMTP relay ([ADR 0010](../architecture/adr/0010-email.md)) |
| OSRM | Built from `infra/osrm/Dockerfile` on your machine, ports 5050/5051 for running Routing outside Docker | The same Dockerfile, built in Actions; no ports, only Routing reaches it |
| Accounts | Temporary signing key | `ACCOUNTS_ENVIRONMENT=production`: refuses to start without the real key |
| Limits | None | Memory limit per container, logs rotated at 3 × 10 MB |

## 3. Secrets

All secrets live in **GitHub → Settings → Secrets and variables → Actions**. They're never committed and never printed in the workflow logs.

| Secret | What it is |
|---|---|
| `DEPLOY_HOST`, `DEPLOY_USER`, `DEPLOY_SSH_KEY` | Server address, user and the deploy key ([Server setup](server-setup.md#8-deploy-key-for-github-actions)) |
| `POSTGRES_PASSWORD` | Database admin password |
| `ACCOUNTS_DB_PASSWORD`, `TRIPS_DB_PASSWORD`, `ROUTING_DB_PASSWORD`, `PAYMENTS_DB_PASSWORD`, `NOTIFICATIONS_DB_PASSWORD` | One database password per service |
| `PAYMENTS_STRIPE_SECRET_KEY` | Stripe test secret key (`sk_test_...`); see [Payments setup](../../services/payments/README.md#stripe-test-mode) |
| `ACCOUNTS_JWT_PRIVATE_KEY` | Accounts' private key for signing access tokens (PEM, RSA 2048) |
| `NOTIFICATIONS_SMTP_USERNAME`, `NOTIFICATIONS_SMTP_PASSWORD` | Brevo's SMTP login and SMTP key (see [Email](#email-brevo)) |
| `NOTIFICATIONS_EMAIL_FROM` | The From address, a sender verified in Brevo, e.g. `GetDrove <team@example.com>` |
| `DISCORD_WEBHOOK_URL` | Repository secret. The webhook the failure alert posts to: in Discord, **channel settings → Integrations → Webhooks → New Webhook → Copy Webhook URL**. Without it the alert job only shows a warning. |
| `DEMO_ACCOUNT_PASSWORD` | In the **production** environment. The demo accounts' password, used by Seed demo data and by the browser smoke test |

The registry login uses the workflow's own temporary `GITHUB_TOKEN`; no registry secret is needed. Links in emails use `SITE_URL` from the top of `deploy.yml`, which isn't a secret.

**Variables** (same page, the **Variables** tab) hold settings that aren't secret:

| Variable | What it is |
|---|---|
| `STRIPE_PUBLISHABLE_KEY` | Stripe's publishable **test** key (`pk_test_...`) for the Add card form. It's built into the web image, since the browser needs it; it's public by design. The secret key belongs to the Payments service only. Without it, the Add card screen says card payments aren't set up |

**Creating them.** With the [GitHub CLI](https://cli.github.com/) logged in to the repository, each value goes straight into GitHub without being shown or saved on your computer:

```bash
for name in POSTGRES_PASSWORD ACCOUNTS_DB_PASSWORD TRIPS_DB_PASSWORD ROUTING_DB_PASSWORD PAYMENTS_DB_PASSWORD NOTIFICATIONS_DB_PASSWORD; do
  openssl rand -hex 24 | gh secret set "$name"
done
openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:2048 2>/dev/null | gh secret set ACCOUNTS_JWT_PRIVATE_KEY
gh secret set NOTIFICATIONS_SMTP_USERNAME    # paste Brevo's SMTP login
gh secret set NOTIFICATIONS_SMTP_PASSWORD    # paste the Brevo SMTP key
gh secret set NOTIFICATIONS_EMAIL_FROM       # e.g. GetDrove <team@example.com>
gh secret list
```

### Email (Brevo)

Production email goes through [Brevo](https://www.brevo.com/)'s SMTP relay (free plan: 300 emails a day). Setting it up once:

1. Create a Brevo account.
2. **Senders, Domains & Dedicated IPs → Senders → Add a sender**, with an address the team controls. Brevo emails it a confirmation link; until it's confirmed, Brevo refuses to send. Once we have a domain (#110), verify the domain instead and send from it.
3. **SMTP & API → SMTP**: copy the **Login** and generate an **SMTP key**. Put them in the two secrets above, and the confirmed sender in `NOTIFICATIONS_EMAIL_FROM`.

The server name (`smtp-relay.brevo.com`), port 587 and STARTTLS are set in `docker-compose.prod.yml`, since they aren't secret.

**Changing them later:**

- **Database passwords** only take effect when the database is first created (the init script runs once, on an empty data volume). Changing one later means changing it inside Postgres too (`ALTER ROLE trips PASSWORD '...'`), then updating the secret and redeploying. Avoid it unless a password leaks.
- **The signing key** can be replaced at any time: set the new secret and redeploy. Everyone is logged out, because tokens signed with the old key stop working.
- **The Brevo SMTP key** can be replaced at any time: generate a new one in Brevo, set the secret, redeploy, then delete the old key in Brevo.

### Routing engine (OSRM)

The Routing service needs OSRM for driving routes and walking times ([ADR 0008](../architecture/adr/0008-routing-engine.md)). The server never prepares map data itself: `infra/osrm/Dockerfile` downloads the Manitoba OpenStreetMap extract, clips it to Winnipeg and builds the graph, and the result is part of the `getdrove-osrm-car` and `getdrove-osrm-foot` images.

- **The map is cached.** It's only downloaded and built again when the Dockerfile changes (the OSRM version or the area) or when asked to. Other deploys reuse it, so they stay fast.
- **Newer map data** (new streets): **Actions → Deploy → Run workflow** from `main` with **refresh_map** ticked.
- **Memory:** each instance is limited to 512 MB; the Winnipeg graphs need much less.
- **Privacy:** OSRM runs with `--verbosity WARNING`, because at its default level it logs every request URL, which holds riders' and drivers' coordinates. The services don't log httpx's request URLs either.

## 4. Did the deploy work?

- **Actions tab → Deploy:** a green run means the site is up and the smoke test passed (the build job shows as skipped when the images were reused, and the alert job is skipped when nothing failed). The deploy job also prints `docker compose ps`. A red run has also been posted to Discord.
- **If the deploy job fails,** its last step prints the last 50 log lines of every container. The usual causes:

| What you see | Cause |
|---|---|
| `GitHub secret X is not set` | Add the secret (section 3) |
| `Permission denied (publickey)` | The deploy key or `DEPLOY_USER` secret is wrong ([Server setup](server-setup.md#troubleshooting)) |
| A service is `unhealthy` and its log shows a migration error | Fix the migration and release a hotfix |
| Accounts exits with an error about `ACCOUNTS_JWT_PRIVATE_KEY` | The secret isn't a valid PEM private key; create it again (section 3) |
| `OSRM car returned …` / `OSRM foot returned …` | OSRM is running but its map is wrong or empty: check the `osrm-car` / `osrm-foot` build logs in the build job |

- **If the smoke test's HTTPS checks fail,** the containers are running but the site doesn't answer from outside: check the VM's HTTP/HTTPS firewall settings and the Traefik logs. A certificate error means Traefik couldn't get one from Let's Encrypt ([Server setup](server-setup.md#troubleshooting)).
- **If the browser test fails,** download the run's `smoke-test-report` artifact and open the trace (`npx playwright show-trace <trace.zip>`) to see each step and screenshot. "Wrong email or password" means the demo accounts aren't on the site (run **Seed demo data**) or `DEMO_ACCOUNT_PASSWORD` doesn't match them. A search error means a service behind search (Trips, Routing, Payments) is down. The same test runs from your machine against the live site: see [e2e/README.md](../../e2e/README.md).
- **Checking the alert:** **Actions → Deploy → Run workflow** from `main` with **test_alert** ticked. Nothing is deployed; the browser test runs with a wrong password, fails on purpose, and the alert posts "Test alert" to Discord.
- **If sign-up works but no email arrives,** check the Notifications logs (`logs notifications`, below). `Authentication failed` means the Brevo login or key is wrong; a refusal about the sender means `NOTIFICATIONS_EMAIL_FROM` isn't a confirmed sender in Brevo. Brevo's **Transactional → Logs** page shows what it received and whether it was delivered. Failed emails are retried, then kept in the `notifications.failed_events` table after 5 tries. Also check the student's junk folder.

On the server, from `/opt/getdrove`:

```bash
docker compose -f docker-compose.prod.yml ps                 # status and health
docker compose -f docker-compose.prod.yml logs -f trips      # one service's logs
docker compose -f docker-compose.prod.yml logs traefik       # certificates and gateway errors (no access log)
```

## 5. Rolling back

Every deploy is tagged with its commit SHA, so an earlier version can be put back in about a minute:

1. Find the last good deploy: **Actions → Deploy**, open its run, and copy the commit SHA (the full 40 characters). Reused images are tagged with the release commit too, so every deploy's SHA works.
2. **Actions → Deploy → Run workflow**, branch `main`, paste the SHA into **image_tag**, and run it. This skips reusing and building, redeploys those images, and runs the smoke test (and the alert, if it fails) as usual.
3. Fix the problem with a hotfix ([Git workflow](../process/git-workflow.md#hotfixes)); its release deploys normally.

Rolling back to a deploy from before OSRM was added (#233) isn't possible: those commits have no OSRM images, and the Compose file needs them.

A rollback doesn't undo database migrations. Migrations should only add things (new tables or columns), so older code keeps working with a newer database.

## 6. Why it's set up this way

- **Images are built in GitHub Actions, not on the server,** so the server's memory goes to running the app, and the server only ever runs images built from reviewed code.
- **One environment, deployed from `main`,** so the live site the instructor sees only changes with releases ([ADR 0016](../architecture/adr/0016-google-cloud-hosting-and-deploy-from-main.md)). A separate staging environment would double the server cost and work.
- **`docker compose up -d --wait`** restarts only the containers that changed and fails the deploy if any container doesn't become healthy, so a broken release shows up as a red workflow instead of a silently broken site.

- **Releases reuse `develop`'s images** instead of building again, so what goes live is byte for byte what passed every check on `develop`, and a release deploys in a few minutes.
- **A browser smoke test, not only health checks,** because every service can be healthy while logging in or searching is broken. It's one short test on purpose: it runs against the live site after every release, so it has to be quick and must never change real data (searching doesn't).
- **Failures go to Discord,** where the team already talks, so nobody has to watch Actions to notice a broken release.
