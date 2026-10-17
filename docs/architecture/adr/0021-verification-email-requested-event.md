# ADR 0021: A separate event for resending the verification email

- **Status:** Accepted (approved in [#211](https://github.com/Andrew-Ih/COMP-4350-Group5-GetDrove/pull/211))
- **Date:** 2026-10-15

## Context

Notifications sends every email ([ADR 0010](0010-email.md)); Accounts tells it to through events on Redis Streams ([ADR 0005](0005-message-broker.md)). Sign-up publishes `UserRegistered`, which carries the verification link's token. The Accounts contract also has `POST /auth/resend-verification` ([#5](https://github.com/Andrew-Ih/COMP-4350-Group5-GetDrove/issues/5)), which sends a new link and makes older links stop working, but no event existed to ask Notifications for that email.

## Options considered

- **A new `VerificationEmailRequested` event:** Same fields as `UserRegistered` (`userId`, `email`, `firstName`, `verificationToken`). Each event means one thing, and future consumers of `UserRegistered` (for example, counting sign-ups) aren't fooled by resends.
- **Reuse `UserRegistered` for resends:** No contract change, but the event would no longer mean "someone signed up", which is misleading for any other consumer.
- **Accounts sends the email itself:** Puts email settings and templates in two services, against ADR 0010.

## Decision

Add **`VerificationEmailRequested` (version 1)** to `libs/events/src/events/catalog/accounts.py`, published by Accounts on the `events.accounts` stream when a resend succeeds. It isn't published for unknown or already-verified emails, so the endpoint can always answer 202 without revealing who has an account. Notifications ([#93](https://github.com/Andrew-Ih/COMP-4350-Group5-GetDrove/issues/93)) handles it the same way as `UserRegistered`.

## Consequences

**Positive**

- Each event has one meaning; Notifications can still use one handler for both.
- Uses the same outbox, so a resend's new token and its event are saved together.

**Negative / trade-offs**

- One more event contract to keep in step with Notifications (`contracts/events/verification-email-requested.v1.json`).
- Like `UserRegistered`, the raw token travels in the event and sits in the outbox until it's sent, so outbox rows must never be logged or exposed.
