# common-security

Checks access tokens for every GetDrove service (issue #91, ADR 0006). Accounts signs tokens; every other service checks them itself using Accounts' public key, so no service calls Accounts on each request.

```
Accounts                                  Any service
signs tokens with its private key  ─────▶ checks the signature with the public key
GET /.well-known/jwks.json  ◀──── fetched once, cached 10 min ────  common-security
```

## Use it in a service

```python
# infrastructure/main.py
from common_security.dependencies import install_security

install_security(app)          # after common_web's install(app, service=...)
```

```python
# adapters/api/trips_router.py
from typing import Annotated
from fastapi import Depends
from common_security import CurrentUser
from common_security.dependencies import AuthenticatedUser, require_role

@router.post("/")
async def post_trip(body: PostTripRequest, user: AuthenticatedUser) -> Trip:
    ...  # user.id (UUID), user.roles

@router.post("/admin/drivers/{id}/approve")
async def approve(id: UUID, user: Annotated[CurrentUser, Depends(require_role("admin"))]) -> None:
    ...
```

`CurrentUser` is a plain dataclass, so use cases can take it without importing FastAPI.

## What's checked

| Check | Fails with |
|---|---|
| `Authorization: Bearer <token>` header present | 401 `unauthorized` (with `WWW-Authenticate: Bearer`) |
| Signed with RS256 by Accounts' key (any other algorithm, including `none` and HS256, is rejected) | 401 `invalid_token` |
| Not expired (30 seconds' leeway for clock differences) | 401 `token_expired` |
| Issuer `getdrove-accounts`, audience `getdrove` | 401 `invalid_token` |
| Has `sub` (a user ID), `roles`, `iat`, `exp` | 401 `invalid_token` |
| Has the required role (`require_role`) | 403 `forbidden` |
| Accounts unreachable and no key cached yet | 503 `auth_unavailable` |

Errors use [common-web](../common-web/README.md)'s Problem Details format. A valid token also records the user ID for this request's log lines.

## Keys and caching

- The public keys are fetched from `AUTH_JWKS_URL` and cached for 10 minutes.
- A token with an unknown key ID (Accounts rotated its key) triggers an immediate re-fetch, at most once a minute.
- If Accounts is briefly down, cached keys keep working.

| Setting | Default | In Docker Compose |
|---|---|---|
| `AUTH_JWKS_URL` | `http://localhost:8001/.well-known/jwks.json` (Accounts run with uv) | `http://accounts:8000/.well-known/jwks.json` |

Accounts doesn't fetch its own keys: it passes its signing key directly (`install_security(app, keys=StaticKeys(...))`).

## Tokens (issued by Accounts)

- **Access token:** RS256 JWT, 15 minutes. Claims: `sub` (user ID), `roles` (`["user"]` or `["user", "admin"]`), `iat`, `exp`, `iss`, `aud`. The header's `kid` names the key.
- **Refresh token:** 7 days, in an HttpOnly cookie, handled by Accounts only.
- Accounts' private key comes from `ACCOUNTS_JWT_PRIVATE_KEY` in production (from GitHub Secrets; Accounts won't start without it). Locally, a temporary key is generated at startup. No private key is ever committed.

## Testing protected endpoints

`common_security.testing.TestAuth` makes a throwaway key and tokens, so tests don't need Accounts running:

```python
from common_security.testing import TestAuth

auth = TestAuth()
app = create_app()
auth.install(app)                                   # accept TestAuth's tokens

await client.get("/mine", headers=auth.headers())   # a logged-in user (auth.user_id)
auth.headers(roles=["user", "admin"])               # an admin
auth.headers(expires_in=-120)                       # an expired token
auth.token(aud="someone-else")                      # any claim can be overridden
```

## Service-to-service calls

`/internal/...` endpoints don't take tokens in Sprint 1: the gateway never exposes them, so they're only reachable from inside Docker. This can be tightened in Sprint 3's security work.
