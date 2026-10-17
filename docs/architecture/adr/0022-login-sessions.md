# ADR 0022: Login sessions with a short access token and a rotating refresh cookie

- **Status:** Proposed
- **Date:** 2026-10-17

## Context

[ADR 0006](0006-gateway-and-authentication.md) decided that Accounts issues RS256 JWTs and every service checks them with Accounts' public key. It didn't decide how a student stays logged in: how long a token lasts, where the browser keeps it, how it's renewed and how logging out works. User story [#89](https://github.com/Andrew-Ih/COMP-4350-Group5-GetDrove/issues/89) asks for a student to stay logged in across visits until they log out, with one generic error for a wrong email or password. This was built in [#6](https://github.com/Andrew-Ih/COMP-4350-Group5-GetDrove/issues/6) and [#90](https://github.com/Andrew-Ih/COMP-4350-Group5-GetDrove/issues/90), following the Accounts contract (`contracts/openapi/accounts.json`).

## Options considered

- **One long-lived access token (days):** Simple, but a stolen token works until it expires, and other services can't tell it's been revoked, since they never call Accounts.
- **Access token in `localStorage`:** Survives reloads, but any script injected into the page can read and steal it.
- **Short access token plus a refresh token, without rotation:** A stolen refresh token keeps working for its whole lifetime, and nobody notices.
- **Short access token in memory, plus a rotating refresh token in an HttpOnly cookie, with reuse detection:** The common approach for browser apps (OAuth 2.0 Security Best Current Practice, OWASP).

## Decision

Use the last option.

**Tokens**
- **Access token:** RS256 JWT, **15 minutes**, claims `sub`, `roles`, `iat`, `exp`, `iss`, `aud` and `kid` in the header (no email or name). Returned in the login and refresh response bodies; the web app keeps it **in memory only**.
- **Refresh token:** 32 random bytes, **7 days**, sent only as the `refresh_token` cookie with `HttpOnly; Secure; SameSite=Strict; Path=/api/accounts/auth`, so scripts can't read it, it's only sent to the refresh and logout endpoints, and never from other sites. Accounts stores only its **SHA-256 hash** (`accounts.refresh_tokens`).

**Rotation and reuse detection**
- Every `POST /auth/refresh` **swaps** the cookie: the old token is revoked and records its replacement (`replaced_by_id`), and a new one with a fresh 7 days is set.
- A swapped token should never come back. If one does, a copy is in use, by the student or by someone who stole it, so **all of that student's sessions are ended** and they log in again. The lockout is committed before the 401 is returned.
- A token that was only logged out gives a plain 401, so logging out on one device doesn't end the others.
- The token row is locked while it's checked (`SELECT … FOR UPDATE`), so the same cookie can't be swapped twice at once.

**Logging in and out**
- An unknown email and a wrong password give the **same** 401 `invalid_credentials`, and take the same time (a dummy password check runs when there's no account). `email_not_verified` (403) is only returned after the password is right. Neither response reveals whether an account exists.
- `POST /auth/logout` always returns 204, revokes the token if it's still in use, and clears the cookie with the same path, Secure and SameSite it was set with.

## Consequences

**Positive**

- A stolen access token is useful for 15 minutes at most; a stolen refresh token is caught the first time it's reused.
- Other services still check tokens without calling Accounts (ADR 0006); only refresh and logout go to Accounts.
- Students stay logged in across reloads and visits for up to 7 days of inactivity.

**Negative / trade-offs**

- **Needs HTTPS outside localhost.** Browsers don't store a `Secure` cookie from a plain `http://` site, so on the live site refresh and logout only work once it has HTTPS ([#110](https://github.com/Andrew-Ih/COMP-4350-Group5-GetDrove/issues/110)). Login itself works.
- **Two refreshes at once look like reuse.** Two tabs reloading together would send the same cookie, and the second would end the session. The web app allows only one refresh at a time, across tabs too (`navigator.locks`). If that isn't enough, a short grace period for a just-replaced token can be added later.
- A revoked access token keeps working until it expires (up to 15 minutes), because services don't check with Accounts.
- Refresh tokens pile up in `accounts.refresh_tokens`; expired rows can be cleaned up by a scheduled job later.
