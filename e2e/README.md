# Browser smoke tests

Playwright tests that click through the running app like a student would (#177). The Deploy
workflow runs them against the live site after every deploy; if they fail, the run goes red
and Discord is told (see [deployment.md](../docs/deployment/deployment.md#4-did-the-deploy-work)).

- `search.smoke.ts`: a demo rider logs in and searches for a ride to campus.

They need the demo accounts (`infra/seed/`) on the site they run against.

## Run them

```bash
cd e2e
npm ci
npx playwright install chromium
SMOKE_PASSWORD='<demo password>' npm run smoke                                   # the live site
SMOKE_BASE_URL=http://localhost SMOKE_PASSWORD='<seed password>' npm run smoke   # the local stack
```

PowerShell: `$env:SMOKE_PASSWORD = "<demo password>"; npm run smoke`.

| Variable | Default |
|---|---|
| `SMOKE_BASE_URL` | `https://getdrove.duckdns.org` |
| `SMOKE_EMAIL` | `getdrove.demo.priya@myumanitoba.ca` |
| `SMOKE_PASSWORD` | none: required |

A failed run keeps a screenshot and trace in `test-results/`; `npx playwright show-report` opens them.
