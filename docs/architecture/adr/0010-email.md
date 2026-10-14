# ADR 0010: Mailpit locally, Brevo in production

- **Status:** Accepted
- **Date:** 2026-10-04

## Context

The system sends verification emails, request updates, and reminders. Development must never send real email; production must be free at our volume.

## Options considered

- **Mailpit (local):** Catches all email with a web UI.
- **Brevo:** Generous free tier, SMTP and API, works without our own domain.
- **Resend:** Modern API; smaller free tier; best with own domain.
- **SendGrid:** Well known; more limited free plan.
- **Oracle Email Delivery:** Included in Oracle's free tier; more setup.

## Decision

Use **Mailpit** in local development and **Brevo** over SMTP in production, behind the Notifications service's email port.

## Consequences

**Positive**

- No real emails during development; standard SMTP works with Spring Boot's mail support.
- Switching providers later only changes configuration or one adapter.

**Negative / trade-offs**

- University email filters may block or spam-folder messages: test delivery to a real `@myumanitoba.ca` address in Sprint 1.
