# ADR 0005: Redis Streams as the message broker

- **Status:** Accepted
- **Date:** 2026-10-04

## Context

Services communicate asynchronously through events (e.g. `RequestAccepted` triggers the payment hold and notifications). Requirements: events must not be lost if a service is down, consumers must resume where they stopped, and the system must run locally with one command. Our event volume is small (thousands per day).

## Options considered

- **Redis Streams:** Consumer groups, acknowledgements, persistence with AOF; Redis is already needed for caching and live locations.
- **RabbitMQ:** Dedicated broker with built-in retries, dead-letter queues, and routing; one more system to run.
- **Kafka:** Industry-standard event log; heavy to run and far beyond our scale.
- **AWS SNS/SQS:** Managed; ties us to AWS and complicates local development.

## Decision

Use **Redis Streams**, one stream per producing service and one consumer group per consuming service, with the **transactional outbox pattern** in producers and **idempotent consumers**.

## Consequences

**Positive**

- One less system to run, learn, and deploy.
- Reliability comes from the outbox (no lost events) and idempotent consumers (safe duplicates).
- The broker sits behind a port in `libs/events`, so swapping to Kafka or RabbitMQ later means writing a new adapter.

**Negative / trade-offs**

- No built-in dead-letter queue; we handle repeated failures ourselves (log and park the message).
- Redis must run with AOF persistence enabled.
