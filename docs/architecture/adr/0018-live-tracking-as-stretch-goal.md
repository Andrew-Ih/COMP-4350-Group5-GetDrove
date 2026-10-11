# ADR 0018: Live tracking as a stretch goal; polling instead of WebSockets

- **Status:** Accepted
- **Date:** 2026-10-10
- **Amends:** [ADR 0017](0017-python-fastapi-backend.md) (the "Realtime" row)

## Context

Our proposal included live driver location as part of the Trip execution core feature: riders would watch the driver's position on a map in real time. That required WebSocket connections, a location feed from the driver's phone, handling for dropped connections, and storing live positions in Redis. ADR 0017 chose FastAPI's built-in WebSockets for this, and also used them for trip chat and notification push.

The instructor's feedback on the proposal:

> I like the idea of live tracking, but at this stage I think it is better framed as a stretch goal than as a core feature. Live tracking introduces a number of additional considerations, such as real-time updates and potentially push notifications. Since the project was otherwise presented primarily as a website rather than a mobile application, this feature currently feels somewhat underdefined relative to the rest of the system.

Without live location, the remaining real-time needs (trip chat and in-app notifications) don't need delivery within a second.

## Options considered

- **Keep live tracking in core scope:** matches the original proposal, but goes against the feedback and keeps the riskiest technical work on the critical path.
- **Move live tracking to stretch, keep WebSockets for chat and notifications:** builds all the real-time machinery for its least important uses.
- **Move live tracking to stretch, use polling for chat and notifications:** the frontend asks for new messages and notifications every few seconds through normal REST endpoints.

## Decision

- **Live driver tracking becomes a stretch goal.** Its user story and 5 development tasks stay in GitHub under the stretch goal issue "Stretch: Live driver tracking", labelled `stretch`, in the Backlog. They are only started once core work for the sprint is done.
- **Trip execution stays a core feature** with three stories: trip reminders, marking riders picked up or no-show (with trip completion), and the trip group chat. Riders see the planned pickup time and ETA plus **trip status updates** (scheduled, started, picked up, completed) instead of a moving map.
- **No WebSockets in the core design.** Trip chat and in-app notifications use **polling**: the frontend calls `GET` endpoints every 3–5 seconds while the chat or notification panel is open (TanStack Query's `refetchInterval`), and stops when the tab is hidden or the trip completes.
- **The trip share link** shows trip details and status instead of live location.

## Consequences

**Positive**

- Responds directly to instructor feedback, and the change is recorded for the Sprint 1 and Sprint 2 feedback sections.
- Removes the riskiest technical work from the core plan: no WebSocket server, connection authentication, reconnect handling, proxy configuration, or live-location storage.
- Chat and notifications are ordinary REST endpoints: simpler to build, secure, document in OpenAPI, and test.
- Frees roughly a week of Sprint 3 time for testing and hardening.

**Negative / trade-offs**

- Chat messages and notifications can take a few seconds to appear.
- Polling adds a small, steady stream of requests during trips; at our scale (a few people per trip) this is negligible, and it gives the load test a realistic request type.
- The rider no longer sees the driver approaching on a map; trip status updates and the planned ETA take its place unless the stretch goal is built.
- If live tracking is built later, the same endpoints can be moved to server-sent events or WebSockets without changing how users experience chat.
