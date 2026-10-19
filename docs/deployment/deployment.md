# Deployment

> Back to [README](../../README.md). Related: [Server setup](server-setup.md) · [Local Docker setup](docker-setup.md) · [Git workflow](../process/git-workflow.md#deployment-and-branches) · Decision: [ADR 0016](../architecture/adr/0016-google-cloud-hosting-and-deploy-from-main.md)

How the live site is deployed, which secrets it uses, how to tell whether a deploy worked, and how to roll back. The server itself is described in [Server setup](server-setup.md).

**Live site:** http://34.130.160.109 (a domain with HTTPS follows in #110)

## 1. How a deploy happens

The live site tracks **`main`**, so it only changes when we release ([Git workflow](../process/git-workflow.md#making-a-release)):

```text
release/x.y.z ──PR──▶ main ──▶ Deploy workflow (.github/workflows/deploy.yml)
                                 1. build   eight images → GitHub Container Registry, tagged with the commit
                                 2. deploy  copy files to the server, write .env, pull, restart
                                 3. smoke   home page + every /health through the gateway
```

1. **Build.** GitHub Actions builds one image per service, one for the web app, and two for OSRM (car and foot, with the Winnipeg map built in; see [Routing engine](#routing-engine-osrm)), for `linux/amd64`, and pushes them to GitHub Container Registry as `ghcr.io/andrew-ih/getdrove-<name>:<commit SHA>`. Builds are cached, so unchanged images take seconds.
2. **Deploy.** Actions connects to the server over SSH with the deploy key and:
   - copies `infra/docker-compose.prod.yml` and the database setup script to `/opt/getdrove`
   - writes `/opt/getdrove/.env` from GitHub Secrets (readable only by the server user)
   - logs in to the registry for the pull only, then runs `docker compose pull` and `docker compose up -d --wait`, which restarts only the containers whose image changed and waits until every container is healthy
   - checks from inside the Routing container that both OSRM instances return a realistic Osborne Village → University Centre route
   - removes images older than a week, so the disk doesn't fill up
3. **Smoke test.** Actions calls the live site from outside: the home page, every service's `/health`, and Accounts' public key (`/.well-known/jwks.json`), and checks that `/api/<service>/internal/...` is **not** reachable.

Database migrations run automatically: each service container applies its migrations when it starts.

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
| Reachable from outside | Gateway, database, Redis, Mailpit, Traefik dashboard | **Only the gateway on port 80** |
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
| `ACCOUNTS_JWT_PRIVATE_KEY` | Accounts' private key for signing access tokens (PEM, RSA 2048) |
| `NOTIFICATIONS_SMTP_USERNAME`, `NOTIFICATIONS_SMTP_PASSWORD` | Brevo's SMTP login and SMTP key (see [Email](#email-brevo)) |
| `NOTIFICATIONS_EMAIL_FROM` | The From address, a sender verified in Brevo, e.g. `GetDrove <team@example.com>` |

The registry login uses the workflow's own temporary `GITHUB_TOKEN`; no registry secret is needed. Links in emails use `SITE_URL` from the top of `deploy.yml`, which isn't a secret.

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

- **Actions tab → Deploy:** all three jobs green means the site is up and the smoke test passed. The deploy job also prints `docker compose ps`.
- **If the deploy job fails,** its last step prints the last 50 log lines of every container. The usual causes:

| What you see | Cause |
|---|---|
| `GitHub secret X is not set` | Add the secret (section 3) |
| `Permission denied (publickey)` | The deploy key or `DEPLOY_USER` secret is wrong ([Server setup](server-setup.md#troubleshooting)) |
| A service is `unhealthy` and its log shows a migration error | Fix the migration and release a hotfix |
| Accounts exits with an error about `ACCOUNTS_JWT_PRIVATE_KEY` | The secret isn't a valid PEM private key; create it again (section 3) |
| `OSRM car returned …` / `OSRM foot returned …` | OSRM is running but its map is wrong or empty: check the `osrm-car` / `osrm-foot` build logs in the build job |

- **If the smoke test fails,** the containers are running but the site doesn't answer from outside: check the VM's HTTP firewall setting and the Traefik logs.
- **If sign-up works but no email arrives,** check the Notifications logs (`logs notifications`, below). `Authentication failed` means the Brevo login or key is wrong; a refusal about the sender means `NOTIFICATIONS_EMAIL_FROM` isn't a confirmed sender in Brevo. Brevo's **Transactional → Logs** page shows what it received and whether it was delivered. Failed emails are retried, then kept in the `notifications.failed_events` table after 5 tries. Also check the student's junk folder.

On the server, from `/opt/getdrove`:

```bash
docker compose -f docker-compose.prod.yml ps                 # status and health
docker compose -f docker-compose.prod.yml logs -f trips      # one service's logs
docker compose -f docker-compose.prod.yml logs traefik       # every request through the gateway
```

## 5. Rolling back

Every deploy is tagged with its commit SHA, so an earlier version can be put back in about a minute:

1. Find the last good deploy: **Actions → Deploy**, open its run, and copy the commit SHA (the full 40 characters).
2. **Actions → Deploy → Run workflow**, branch `main`, paste the SHA into **image_tag**, and run it. This skips the build and redeploys those images.
3. Fix the problem with a hotfix ([Git workflow](../process/git-workflow.md#hotfixes)); its release deploys normally.

Rolling back to a deploy from before OSRM was added (#233) isn't possible: those commits have no OSRM images, and the Compose file needs them.

A rollback doesn't undo database migrations. Migrations should only add things (new tables or columns), so older code keeps working with a newer database.

## 6. Why it's set up this way

- **Images are built in GitHub Actions, not on the server,** so the server's memory goes to running the app, and the server only ever runs images built from reviewed code.
- **One environment, deployed from `main`,** so the live site the instructor sees only changes with releases ([ADR 0016](../architecture/adr/0016-google-cloud-hosting-and-deploy-from-main.md)). A separate staging environment would double the server cost and work.
- **`docker compose up -d --wait`** restarts only the containers that changed and fails the deploy if any container doesn't become healthy, so a broken release shows up as a red workflow instead of a silently broken site.

Coming next: HTTPS and a domain (#110); in Sprint 2, images published on every merge to `develop` and a Discord alert when a deploy fails.
