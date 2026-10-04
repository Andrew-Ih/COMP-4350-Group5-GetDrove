# ADR 0011: Docker volume for driver documents

- **Status:** Accepted
- **Date:** 2026-10-04

## Context

Drivers upload licence and insurance documents, visible only to the owner and admins. Volume is tiny (a few files per driver).

## Options considered

- **Docker volume:** Files on the VM, mounted into Accounts.
- **MinIO:** S3-compatible storage container.
- **Oracle Object Storage:** Managed, free tier; ties code to Oracle.
- **PostgreSQL bytea:** No extra service; bloats the database.

## Decision

Store documents in a **Docker volume** mounted into Accounts, served only through a permission-checked Accounts endpoint, behind a `DocumentStorage` port.

## Consequences

**Positive**

- Simplest option; nothing extra to run.

**Negative / trade-offs**

- Files live on one server, so the volume must be included in backups.
- Moving to S3-compatible storage later requires a new adapter (but no other changes).
