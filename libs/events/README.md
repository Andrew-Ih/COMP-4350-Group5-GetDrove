# events

How GetDrove services tell each other that something happened (ADR 0005, issue #104).

```
Producer (e.g. Accounts)                       Redis                   Consumer (e.g. Notifications)
1. save the change   ┐ one DB transaction
2. save the event    ┘ (outbox table)
3. OutboxRelay ───XADD───▶ stream "events.accounts" ──XREADGROUP──▶ StreamConsumer
                                                    group "notifications"     handles once, then ACK
```

- **Never lost:** the event is committed together with the change (transactional outbox).
- **Never for a rolled-back change:** if the transaction rolls back, so does the event.
- **Handled once:** delivery can repeat, so consumers record handled event IDs in `processed_events` and skip repeats.
- **Retried, then parked:** a failing handler is retried after 30 s; after 5 deliveries the event is logged, saved to `failed_events` and acknowledged, so it can't block the stream.

## The envelope

```json
{
  "eventId": "6f1c…",
  "type": "UserRegistered",
  "version": 1,
  "occurredAt": "2026-10-14T15:00:00Z",
  "producer": "accounts",
  "correlationId": "req-81f2…",
  "payload": { "userId": "…", "email": "…" }
}
```

Define each event as a payload class. Event classes shared between services belong in the event contracts (#108):

```python
from typing import ClassVar
from uuid import UUID
from events import EventPayload

class UserRegistered(EventPayload):
    event_type: ClassVar[str] = "UserRegistered"
    event_version: ClassVar[int] = 1

    user_id: UUID
    email: str
```

Payloads carry IDs and only what consumers need (never home addresses). Adding a field keeps the version; a breaking change is a new version.

## Publishing (producer services)

**1. Add the outbox table** to the service's tables, then generate a migration:

```python
# adapters/persistence/tables.py
from events.outbox import outbox_table
outbox = outbox_table(metadata)
```

**2. Depend on the port in use cases.** `events.EventPublisher` is framework-free, so the application layer can use it:

```python
# application/register_user.py
from events import EventPublisher

class RegisterUser:
    def __init__(self, uow: UnitOfWork, events: EventPublisher) -> None: ...

    async def __call__(self, cmd: RegisterUserCommand) -> None:
        async with self.uow:
            user = ...                      # save the user
            await self.events.publish(UserRegistered(user_id=user.id, email=user.email))
            # the unit of work commits the user and the event together
```

**3. Wire the adapter** with the same session as the unit of work:

```python
from events.outbox import OutboxPublisher
publisher = OutboxPublisher(session, outbox, producer="accounts", correlation_id=request_id)
```

**4. Run the relay** for the lifetime of the app:

```python
from events.outbox import OutboxRelay

relay = OutboxRelay(session_factory=sessions, redis=redis, table=outbox, producer="accounts")

@asynccontextmanager
async def lifespan(app: FastAPI):
    stop = asyncio.Event()
    task = asyncio.create_task(relay.run(stop))
    yield
    stop.set()
    await task
```

## Consuming (consumer services)

**1. Add the consumer tables** (`processed_events`, `failed_events`), then generate a migration:

```python
from events.consumer import consumer_tables
consumer = consumer_tables(metadata)
```

**2. Register handlers and run the consumer** in the lifespan, like the relay:

```python
from events import EventEnvelope, stream_name
from events.consumer import StreamConsumer

consumer = StreamConsumer(
    redis=redis,
    session_factory=sessions,
    group="notifications",                  # one group per consuming service
    streams=[stream_name("accounts")],      # one stream per producer
    tables=consumer_tables_from_step_1,
)

@consumer.on(UserRegistered)
async def send_verification_email(event: EventEnvelope, session: AsyncSession) -> None:
    data = event.payload_as(UserRegistered)
    ...                                     # use `session` for DB work; don't commit
```

A handler runs inside the same transaction that records the event as handled. If it raises, everything it wrote is rolled back and the event is retried. Work outside the database (like sending an email) can happen twice in rare crash cases, so make it safe to repeat where it matters.

| Option | Default | Meaning |
|---|---|---|
| `max_attempts` | 5 | Deliveries before an event is parked in `failed_events` |
| `retry_after_ms` | 30 000 | How long a failed or abandoned message waits before it's retried |
| `batch_size` | 10 | Messages read at a time |
| `block_ms` | 5 000 | How long to wait for new messages before checking for retries |

A new consumer group starts at the **beginning** of each stream, so events sent before the consumer first ran are still handled.

## Tests

```bash
uv run pytest libs/events
```

Envelope tests are plain unit tests. The outbox and consumer tests start a real PostgreSQL and Redis with testcontainers, so **Docker must be running**; without it they're skipped.
