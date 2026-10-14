"""Reads events from Redis Streams and handles each one exactly once.

Delivery from Redis is "at least once": after a crash or a retry the same event can
arrive again. Each consuming service records the IDs of events it has handled in its own
``processed_events`` table, in the same transaction as the handler's work, so a repeat
is recognised and skipped.

How a message is handled:

1. Insert its ``event_id`` into ``processed_events``. Already there? It's a duplicate:
   acknowledge it and stop.
2. Run the handler in the same transaction, commit, then acknowledge (XACK).
3. If the handler fails, roll back and don't acknowledge. Redis keeps the message as
   pending, and it's retried after ``retry_after_ms``. After ``max_attempts`` deliveries
   it's "parked": logged, saved in ``failed_events`` and acknowledged, so one broken
   message can't block the stream forever.
"""

import asyncio
import logging
import os
import socket
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError
from redis.asyncio import Redis
from redis.exceptions import ResponseError
from sqlalchemy import Column, DateTime, Integer, MetaData, String, Table, Text, Uuid, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from events.envelope import EventEnvelope, EventPayload
from events.streams import ENVELOPE_FIELD

logger = logging.getLogger(__name__)

Handler = Callable[[EventEnvelope, AsyncSession], Awaitable[None]]
"""A handler gets the event and the open database session. It must not commit."""


@dataclass(frozen=True)
class ConsumerTables:
    processed: Table
    failed: Table


def consumer_tables(metadata: MetaData) -> ConsumerTables:
    """Defines ``processed_events`` and ``failed_events`` in a consumer's own schema.

    Call it once in ``adapters/persistence/tables.py``; the service's Alembic migration
    then creates both tables.
    """
    processed = Table(
        "processed_events",
        metadata,
        Column("event_id", Uuid, primary_key=True),
        Column("type", String(200), nullable=False),
        Column("processed_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    )
    failed = Table(
        "failed_events",
        metadata,
        Column("event_id", Uuid, primary_key=True),
        Column("type", String(200), nullable=False),
        Column("stream", String(200), nullable=False),
        Column("envelope", JSONB, nullable=False),
        Column("error", Text, nullable=False),
        Column("attempts", Integer, nullable=False),
        Column("failed_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    )
    return ConsumerTables(processed=processed, failed=failed)


class StreamConsumer:
    """Consumes one or more producers' streams as this service's consumer group.

    Usage::

        consumer = StreamConsumer(redis=redis, session_factory=sessions, group="notifications",
                                  streams=[stream_name("accounts")], tables=tables)

        @consumer.on(UserRegistered)
        async def send_verification_email(event: EventEnvelope, session: AsyncSession) -> None:
            data = event.payload_as(UserRegistered)
            ...

        # in the FastAPI lifespan:
        task = asyncio.create_task(consumer.run(stop))
    """

    def __init__(
        self,
        *,
        redis: Redis,
        session_factory: async_sessionmaker[AsyncSession],
        group: str,
        streams: list[str],
        tables: ConsumerTables,
        consumer_name: str | None = None,
        max_attempts: int = 5,
        retry_after_ms: int = 30_000,
        batch_size: int = 10,
        block_ms: int = 5_000,
    ) -> None:
        # redis-py's async command types are too loose for mypy --strict to check usefully.
        self._redis: Any = redis
        self._session_factory = session_factory
        self._group = group
        self._streams = streams
        self._tables = tables
        self._consumer = consumer_name or f"{group}-{socket.gethostname()}-{os.getpid()}"
        self._max_attempts = max_attempts
        self._retry_after_ms = retry_after_ms
        self._batch_size = batch_size
        self._block_ms = block_ms
        self._handlers: dict[tuple[str, int], Handler] = {}

    # ------------------------------------------------------------------ registration

    def handler(self, event_type: str, version: int = 1) -> Callable[[Handler], Handler]:
        """Registers a handler for one event type and version."""

        def register(func: Handler) -> Handler:
            key = (event_type, version)
            if key in self._handlers:
                raise ValueError(f"A handler for {event_type} v{version} is already registered")
            self._handlers[key] = func
            return func

        return register

    def on(self, payload: type[EventPayload]) -> Callable[[Handler], Handler]:
        """Same as ``handler()``, using the payload class's type and version."""
        return self.handler(payload.event_type, payload.event_version)

    # ------------------------------------------------------------------ running

    async def ensure_groups(self) -> None:
        """Creates this service's consumer group on each stream, if it doesn't exist.

        A new group starts at the beginning of the stream ("0"), so events sent before
        this consumer first ran are still handled. Duplicates are skipped anyway.
        """
        for stream in self._streams:
            try:
                await self._redis.xgroup_create(stream, self._group, id="0", mkstream=True)
                logger.info("Created consumer group %s on %s", self._group, stream)
            except ResponseError as exc:
                if "BUSYGROUP" not in str(exc):
                    raise

    async def run(self, stop: asyncio.Event | None = None) -> None:
        """Consumes until ``stop`` is set or the task is cancelled."""
        await self.ensure_groups()
        logger.info("Consumer %s started on %s", self._consumer, ", ".join(self._streams))
        while stop is None or not stop.is_set():
            try:
                await self.process_once()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Consumer loop failed; retrying in 1s")
                await asyncio.sleep(1)

    async def process_once(self, *, block_ms: int | None = None) -> int:
        """Retries due pending messages, then reads and handles new ones.

        Returns the number of messages handled (including duplicates and parked ones).
        ``block_ms`` overrides how long to wait for new messages (0 = don't wait).
        """
        handled = 0
        for stream in self._streams:
            handled += await self._retry_pending(stream)

        block = self._block_ms if block_ms is None else block_ms
        response = await self._redis.xreadgroup(
            self._group,
            self._consumer,
            dict.fromkeys(self._streams, ">"),
            count=self._batch_size,
            block=block or None,
        )
        for stream, messages in _iter_stream_messages(response):
            for message_id, fields in messages:
                await self._handle(stream, message_id, fields)
                handled += 1
        return handled

    # ------------------------------------------------------------------ internals

    async def _retry_pending(self, stream: str) -> int:
        """Claims messages that have been pending for ``retry_after_ms``: ones whose
        handler failed, or that a crashed consumer never acknowledged."""
        response = await self._redis.xautoclaim(
            stream,
            self._group,
            self._consumer,
            min_idle_time=self._retry_after_ms,
            start_id="0-0",
            count=self._batch_size,
        )
        messages = response[1] if response else []
        for message_id, fields in messages:
            await self._handle(stream, message_id, fields)
        return len(messages)

    async def _handle(self, stream: str, message_id: Any, fields: Any) -> None:
        message_id = _text(message_id)
        if not fields:  # the entry was deleted from the stream
            await self._ack(stream, message_id)
            return

        raw = _field(fields, ENVELOPE_FIELD)
        try:
            envelope = EventEnvelope.from_json(raw or "")
        except ValidationError:
            logger.error("Unreadable event %s on %s; skipping it", message_id, stream)
            await self._ack(stream, message_id)
            return

        handler = self._handlers.get((envelope.type, envelope.version))
        if handler is None:  # not an event this service cares about
            await self._ack(stream, message_id)
            return

        try:
            await self._run_once(envelope, handler)
        except Exception as exc:
            attempts = await self._delivery_count(stream, message_id)
            if attempts >= self._max_attempts:
                await self._park(stream, envelope, exc, attempts)
                await self._ack(stream, message_id)
            else:
                logger.warning(
                    "Handler for %s %s failed (attempt %d of %d); will retry: %s",
                    envelope.type,
                    envelope.event_id,
                    attempts,
                    self._max_attempts,
                    exc,
                )
            return

        await self._ack(stream, message_id)

    async def _run_once(self, envelope: EventEnvelope, handler: Handler) -> None:
        processed = self._tables.processed
        async with self._session_factory() as session, session.begin():
            inserted = await session.execute(
                pg_insert(processed)
                .values(event_id=envelope.event_id, type=envelope.type)
                .on_conflict_do_nothing(index_elements=[processed.c.event_id])
                .returning(processed.c.event_id)
            )
            if inserted.first() is None:
                logger.debug("Skipping duplicate event %s", envelope.event_id)
                return
            await handler(envelope, session)

    async def _delivery_count(self, stream: str, message_id: str) -> int:
        pending = await self._redis.xpending_range(
            stream, self._group, min=message_id, max=message_id, count=1
        )
        if not pending:
            return 1
        return int(pending[0]["times_delivered"])

    async def _park(
        self, stream: str, envelope: EventEnvelope, exc: Exception, attempts: int
    ) -> None:
        logger.error(
            "Giving up on %s %s after %d attempts; saved to failed_events: %s",
            envelope.type,
            envelope.event_id,
            attempts,
            exc,
        )
        failed = self._tables.failed
        async with self._session_factory() as session, session.begin():
            await session.execute(
                pg_insert(failed)
                .values(
                    event_id=envelope.event_id,
                    type=envelope.type,
                    stream=stream,
                    envelope=envelope.to_dict(),
                    error=f"{type(exc).__name__}: {exc}",
                    attempts=attempts,
                )
                .on_conflict_do_nothing(index_elements=[failed.c.event_id])
            )

    async def _ack(self, stream: str, message_id: str) -> None:
        await self._redis.xack(stream, self._group, message_id)


def _text(value: Any) -> str:
    return value.decode() if isinstance(value, bytes) else str(value)


def _field(fields: Any, name: str) -> str | None:
    """Reads a field from a stream entry, whether Redis returned bytes or str."""
    value = fields.get(name)
    if value is None:
        value = fields.get(name.encode())
    return None if value is None else _text(value)


def _iter_stream_messages(response: Any) -> list[tuple[str, list[tuple[Any, Any]]]]:
    """Normalises XREADGROUP's reply (a list, or a dict with RESP3) to (stream, messages)."""
    if not response:
        return []
    items = response.items() if isinstance(response, dict) else response
    result: list[tuple[str, list[tuple[Any, Any]]]] = []
    for stream, messages in items:
        result.append((_text(stream), list(messages)))
    return result
