# Notifications service

**Owner:** Daniel

Emails, in-app notifications, reminders and trip chat.

## Run locally

From the repo root:

```bash
uv sync
uv run --package notifications uvicorn notifications.infrastructure.main:app --reload --port 8005
```

Then open http://localhost:8005/health and the API docs at http://localhost:8005/docs.

Notifications needs PostgreSQL, Redis and an SMTP server; the defaults point at the ones Docker Compose starts on localhost (`docker compose up postgres redis mailpit`). Emails land in Mailpit at http://localhost:8025, and nothing reaches a real inbox. Settings are listed in `.env.example` under "Notifications email", including `NOTIFICATIONS_REMINDER_LEAD_MINUTES`: how long before departure riders are reminded (default 30). Notification emails also need Accounts (`NOTIFICATIONS_ACCOUNTS_URL`, default http://localhost:8001; `http://accounts:8000` in Docker) for each person's name and email address.

In production, email goes out through Brevo's SMTP relay, and links open the live site. The settings come from `infra/docker-compose.prod.yml` and GitHub Secrets; see [Deployment: Email (Brevo)](../../docs/deployment/deployment.md#email-brevo). Production also never emails the demo accounts (`getdrove.demo.*@myumanitoba.ca`, made-up addresses that would bounce): `NOTIFICATIONS_EMAIL_SKIP_PATTERNS` lists them, and they get in-app notifications only (#415).

## Test and check

```bash
uv run pytest services/notifications
uv run mypy services/notifications/src
cd services/notifications && uv run lint-imports
```

## Database migrations

Tables live in the `notifications` Postgres schema. With the database running and `NOTIFICATIONS_DATABASE_URL` set:

```bash
cd services/notifications
uv run alembic revision --autogenerate -m "create users table"   # after changing adapters/persistence/tables.py
uv run alembic upgrade head
```

## Layout

| Folder | What goes there |
|---|---|
| `src/notifications/domain/` | Entities, value objects, rules, domain errors. Pure Python. |
| `src/notifications/application/` | Use cases, and the ports (`ports.py`) they need. |
| `src/notifications/adapters/` | FastAPI routers (`api/`), SQLAlchemy tables and repositories (`persistence/`), HTTP clients, event consumers. |
| `src/notifications/infrastructure/` | App factory (`main.py`), settings, dependency wiring. |
| `tests/` | Tests, mirroring the layers. |

import-linter enforces that inner layers never import outer ones, and that `domain` and `application` never import FastAPI, SQLAlchemy or settings.

## API

The spec is [`contracts/openapi/notifications.json`](../../contracts/openapi/notifications.json). Behind the gateway, paths start with `/api/notifications`. Every endpoint needs an access token.

| Endpoint | What it does |
|---|---|
| `GET /?limit=30` | The logged-in user's latest notifications (1 to 100, default 30), newest first, and `unreadCount`: how many of **all** their notifications are unread. The bell polls this every few seconds while open (ADR 0018). |
| `POST /{notificationId}/read` | Marks one as read (204). Marking it again keeps the first read time. `404 notification_not_found` if the user has no notification with that ID, including someone else's, so IDs can't be probed. |
| `POST /read-all` | Marks all of the user's unread notifications as read (204). |

Notifications are stored in the `notifications` table ([#145](https://github.com/Andrew-Ih/COMP-4350-Group5-GetDrove/issues/145)). Every query filters on the user, so nobody reads or changes another user's notifications. To create one (from an event handler, #146, or a reminder, #149), build a `Notification` and call `SQLAlchemyNotificationStore(session).add(...)` with the handler's session, so it's saved in the same transaction that records the event and a repeated event can't add it twice.

## Events

Consumed from the `events.accounts` stream as the `notifications` consumer group:

| Event | What Notifications does |
|---|---|
| [`UserRegistered`](../../contracts/events/user-registered.v1.json) | Emails the verification link ([#93](https://github.com/Andrew-Ih/COMP-4350-Group5-GetDrove/issues/93)) |
| [`VerificationEmailRequested`](../../contracts/events/verification-email-requested.v1.json) | Emails the new verification link |

The link is `NOTIFICATIONS_WEB_BASE_URL` + `/verify?token=…`, the web app's verify page.

Consumed from the `events.trips` stream, to keep trip reminders in step ([#148](https://github.com/Andrew-Ih/COMP-4350-Group5-GetDrove/issues/148)):

| Event | What Notifications does |
|---|---|
| [`RequestAccepted`](../../contracts/events/request-accepted.v1.json) | Schedules the rider's reminder, `NOTIFICATIONS_REMINDER_LEAD_MINUTES` (default 30) before departure |
| [`RequestCancelled`](../../contracts/events/request-cancelled.v1.json) | Cancels the rider's reminder |
| [`RequestDeclined`](../../contracts/events/request-declined.v1.json) | Cancels the reminder if the rider had a seat (`wasAccepted`) |
| [`TripCancelled`](../../contracts/events/trip-cancelled.v1.json) | Cancels every reminder on the trip |

Reminders are rows in `scheduled_notifications` with `type` = `trip_reminder` (the only type so far; the table is meant for anything sent at a set time). There is one per accepted request (`type` + `request_id` is unique, so an acceptance that arrives twice still makes one), with a status of `pending`, `sent`, `skipped` or `cancelled`. Only pending reminders are cancelled. A reminder stores the label of the rider's point on the route, never the rider's own location. Each also keeps the driver (`driver_id`), so the reminder can name them, and the trip's `direction` (#355): going to campus the point is the pickup; leaving campus the rider is picked up on campus and the point is the drop-off.

**Sending them ([#149](https://github.com/Andrew-Ih/COMP-4350-Group5-GetDrove/issues/149)).** While the service runs, `adapters/reminder_scheduler.py` looks for due reminders every `NOTIFICATIONS_REMINDER_INTERVAL_SECONDS` (default 30):

- It claims one due reminder at a time (`status = 'pending' AND send_at <= now()`, `FOR UPDATE SKIP LOCKED`), so two workers never send the same one.
- The rider gets it in the bell and by email, worded by direction (#355): going to campus "Maya leaves on Mon, Jul 6 at 7:45 AM. Be at your pickup point: …"; leaving campus "Maya leaves campus on … Meet them on campus; you'll be dropped off at …"; and for reminders stored before the direction was kept, "… Your stop: …", which is right either way. The driver's first name comes from Accounts (or "Your driver"); the time is the trip's departure. It's then marked `sent`, with `handled_at`, in the same transaction.
- **After an outage** nothing is lost: the first pass after a restart sends every overdue reminder whose trip hasn't left yet, and marks the rest `skipped`.
- **Cancelled** reminders (cancelled request or trip) are never claimed, so a cancelled trip gets none.
- If one can't be sent (Accounts or the mail server is down), it stays `pending` and is retried on the next pass; the others still go out.

Each event is handled once: it's recorded in `processed_events` in the same transaction as the handler, so a repeat delivery or a restart skips it. A failed send is retried, and after 5 tries the event is parked in `failed_events`. If the service dies after the mail server accepted an email but before that commit, the email is sent once more on restart.

### Request, trip, driver and payment notifications ([#146](https://github.com/Andrew-Ih/COMP-4350-Group5-GetDrove/issues/146))

Also consumed, from `events.trips`, `events.accounts` and `events.payments`. Each one is an in-app notification (in the bell) **and** an email:

| Event | Who is told |
|---|---|
| [`SeatRequested`](../../contracts/events/seat-requested.v1.json) | The driver: a rider asked for a seat |
| [`RequestAccepted`](../../contracts/events/request-accepted.v1.json) | The rider: they have a seat, and their stop, worded by `direction` (#355): the pickup going to campus, the drop-off leaving it (picked up on campus), "Your stop" for events without a direction. If it was auto-accepted, the driver too: no `SeatRequested` came first, so it's their only notice |
| [`RequestDeclined`](../../contracts/events/request-declined.v1.json) | The rider: declined, or removed if they had a seat |
| [`RequestCancelled`](../../contracts/events/request-cancelled.v1.json) | The driver: a rider cancelled (and the seat is free, if they had one) |
| [`TripCancelled`](../../contracts/events/trip-cancelled.v1.json) | Every rider with a pending or accepted request |
| [`DriverApproved`](../../contracts/events/driver-approved.v1.json) / [`DriverRejected`](../../contracts/events/driver-rejected.v1.json) | The driver, with the reason if rejected (linking to their driver application, `/account/driver`, to upload new documents) |
| [`PaymentFailed`](../../contracts/events/payment-failed.v1.json) | The rider: why, and that their seat isn't confirmed |

- **Texts** are in `domain/messages.py`: they say "the driver" or "a rider", never another person's name or location, and give times in Winnipeg time.
- **Emails** need the person's name and address, which events don't carry: Notifications asks Accounts' `GET /internal/contacts` (inside Docker only). If Accounts can't answer, the event is retried, in-app notification included, so nobody misses an email. Someone Accounts doesn't know still gets the in-app notification.
- **`trip_members`** is Notifications' own list of who is on each trip, kept from these events: the driver, and riders with a seat (inactive once they cancel, are removed, their payment fails, or the trip is cancelled). It's for messages to everyone on a trip and, later, the trip chat ([#61](https://github.com/Andrew-Ih/COMP-4350-Group5-GetDrove/issues/61), [#63](https://github.com/Andrew-Ih/COMP-4350-Group5-GetDrove/issues/63)).
- `TripUpdated` isn't handled yet: Trips doesn't publish it, and a trip's time can't be changed.

### One handler per event

`StreamConsumer` takes one handler per event type, but `RequestAccepted`, `RequestCancelled`, `RequestDeclined` and `TripCancelled` matter to both the notifications and the reminders. Each feature gives a map of event to handler (`notification_handlers`, `reminder_handlers`), and `adapters/events/registration.py` registers one handler per event that runs both, in the event's transaction: either everything for the event is saved, or nothing is and it's retried. Add a new feature's handlers the same way, never with `consumer.on` directly.

**`failed_events` holds personal data.** A parked event keeps its whole envelope: the student's email and a verification token that works until it expires (24 hours). Look at why it failed, then delete the row; don't copy envelopes into issues or chat.
