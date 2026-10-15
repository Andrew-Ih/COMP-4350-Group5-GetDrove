# ADR 0020: Argon2id for password hashing

- **Status:** Proposed
- **Date:** 2026-10-14

## Context

Accounts stores a password for every student (issues [#3](https://github.com/Andrew-Ih/COMP-4350-Group5-GetDrove/issues/3), [#4](https://github.com/Andrew-Ih/COMP-4350-Group5-GetDrove/issues/4), [#6](https://github.com/Andrew-Ih/COMP-4350-Group5-GetDrove/issues/6)). Passwords must never be stored or logged in a form that can be turned back into the original, so a leaked database doesn't leak anyone's password. Sign-up needs to scramble the password before saving it, and login needs to check a typed password against the saved one. [ADR 0006](0006-gateway-and-authentication.md) already decided that Accounts handles login and issues its own tokens.

## Options considered

- **Argon2id in Python (`argon2-cffi`):** The algorithm recommended by OWASP and RFC 9106, and the winner of the Password Hashing Competition. Slow and memory-hungry on purpose, which makes guessing stolen hashes expensive. Random salt per password, stored inside the hash.
- **bcrypt in Python:** Widely used and still acceptable, but not memory-hard and silently ignores anything past 72 bytes of a password.
- **Hash inside PostgreSQL (`pgcrypto`'s `crypt()`):** The plain password would travel to the database inside the SQL query, where it can end up in database logs. It also needs a Postgres extension, which service users can't install (`infra/postgres/init/20-create-service-schemas.sh`), and we already avoid extensions for email handling.
- **An outside login provider (Auth0, Firebase, Supabase Auth):** Would replace Accounts' own tokens, which ADR 0006, `libs/common-security` and the Accounts contract (`contracts/openapi/accounts.json`) are already built around.
- **A plain hash such as SHA-256:** Far too fast to compute, so stolen hashes can be guessed in bulk. Not acceptable for passwords. (SHA-256 is still right for the random verification and refresh tokens, which can't be guessed.)

## Decision

Hash passwords with **Argon2id** using **`argon2-cffi`**, in Python, inside Accounts. The library's defaults are used (RFC 9106 low-memory profile: 64 MiB, 3 iterations, 4 lanes, 16-byte salt). The resulting hash (about 97 characters, starting `$argon2id$`) is stored in `accounts.users.password_hash`.

- Sign-up calls `PasswordHasher.hash(password)`. Login calls `PasswordHasher.verify(saved_hash, password)`; it never hashes again and compares strings, because every hash has its own salt.
- The library is used only in `adapters/` behind a port in `application/ports.py`, so use cases stay framework-free and tests can use a fake. Once the adapter exists, `argon2` is added to the forbidden modules for `domain` and `application` in `services/accounts/pyproject.toml`.
- Login hashes a dummy password when the email is unknown, so the response takes the same time whether or not the account exists.

## Consequences

**Positive**

- A leaked database doesn't reveal passwords; guessing each one is slow and memory-expensive.
- The plain password never leaves the Accounts process: it isn't sent to the database or any outside service.
- Small, well-maintained dependency with prebuilt wheels; Dependabot ([ADR 0014](0014-security-and-load-testing.md)) watches it.

**Negative / trade-offs**

- Each hash takes tens of milliseconds and 64 MiB of memory, so sign-up and login are slower than other endpoints and count against the load-test budget. Parameters can be tuned later; existing hashes keep working because the parameters are stored in each hash.
- Hashing doesn't protect against a password being logged before it's hashed. Code review must check that passwords, tokens and emails are never logged. Using Pydantic's `SecretStr` for password fields would hide them from accidental logging, but it changes the generated contract, so it needs the frontend's agreement first.
- Weak passwords can still be guessed from a leaked hash; the contract's 10-character minimum limits this. Rate limiting login attempts isn't in Sprint 1.
