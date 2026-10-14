"""Transactional outbox: producers save events in their own database, in the same
transaction as the change that caused them, and a relay sends them to Redis.

So an event is never lost (it's committed with the change) and never sent for a change
that was rolled back. The relay may occasionally send an event twice; consumers ignore
duplicates (see ``events.consumer``).
"""

import asyncio
import contextlib
import json
import logging
from typing import Any

from redis.asyncio import Redis
from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    Identity,
    Index,
    MetaData,
    String,
    Table,
    Uuid,
    func,
    insert,
    select,
    text,
    update,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from events.envelope import EventEnvelope, EventPayload
from events.streams import ENVELOPE_FIELD, stream_name

logger = logging.getLogger(__name__)


def outbox_table(metadata: MetaData) -> Table:
    """Defines the ``outbox`` table in a producer's own schema.

    Call it once in ``adapters/persistence/tables.py``; the service's Alembic migration
    then creates it like any other table.
    """
    return Table(
        "outbox",
        metadata,
        # Insertion order, so events are sent in the order they happened.
        Column("id", BigInteger, Identity(), primary_key=True),
        Column("event_id", Uuid, nullable=False, unique=True),
        Column("type", String(200), nullable=False),
        Column("envelope", JSONB, nullable=False),
        Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
        Column("published_at", DateTime(timezone=True), nullable=True),
        Index("ix_outbox_unpublished", "id", postgresql_where=text("published_at IS NULL")),
    )


class OutboxPublisher:
    """``EventPublisher`` adapter: adds events to the outbox in the caller's transaction.

    It never commits. The use case's unit of work commits the change and its events
    together, or rolls both back.
    """

    def __init__(
        self,
        session: AsyncSession,
        table: Table,
        *,
        producer: str,
        correlation_id: str | None = None,
    ) -> None:
        self._session = session
        self._table = table
        self._producer = producer
        self._correlation_id = correlation_id

    async def publish(self, event: EventPayload) -> None:
        envelope = EventEnvelope.wrap(
            event, producer=self._producer, correlation_id=self._correlation_id
        )
        await self._session.execute(
            insert(self._table).values(
                event_id=envelope.event_id,
                type=envelope.type,
                envelope=envelope.to_dict(),
            )
        )


class OutboxRelay:
    """Background task that sends unsent outbox rows to the producer's Redis stream.

    Start it when the service starts (FastAPI ``lifespan``) with ``run()``.
    """

    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        redis: Redis,
        table: Table,
        producer: str,
        batch_size: int = 100,
        poll_interval: float = 1.0,
    ) -> None:
        self._session_factory = session_factory
        # redis-py's async command types are too loose for mypy --strict to check usefully.
        self._redis: Any = redis
        self._table = table
        self._stream = stream_name(producer)
        self._batch_size = batch_size
        self._poll_interval = poll_interval

    async def publish_pending(self) -> int:
        """Sends one batch of unsent events, oldest first. Returns how many were sent."""
        table = self._table
        async with self._session_factory() as session, session.begin():
            rows = (
                await session.execute(
                    select(table.c.id, table.c.type, table.c.envelope)
                    .where(table.c.published_at.is_(None))
                    .order_by(table.c.id)
                    .limit(self._batch_size)
                    # Two copies of a service never send the same rows.
                    .with_for_update(skip_locked=True)
                )
            ).all()
            if not rows:
                return 0

            for row in rows:
                await self._redis.xadd(
                    self._stream,
                    {ENVELOPE_FIELD: json.dumps(row.envelope), "type": row.type},
                )

            # If the process dies before this commit, these rows are sent again next
            # time. That's safe: consumers skip events they've already handled.
            await session.execute(
                update(table)
                .where(table.c.id.in_([row.id for row in rows]))
                .values(published_at=func.now())
            )
        logger.debug("Sent %d events to %s", len(rows), self._stream)
        return len(rows)

    async def run(self, stop: asyncio.Event | None = None) -> None:
        """Keeps sending until ``stop`` is set or the task is cancelled."""
        logger.info("Outbox relay started for %s", self._stream)
        while stop is None or not stop.is_set():
            sent = 0
            try:
                sent = await self.publish_pending()
            except Exception:
                logger.exception("Outbox relay failed; retrying in %ss", self._poll_interval)
            if sent < self._batch_size:  # a full batch means there may be more right away
                await _sleep_or_stop(self._poll_interval, stop)


async def _sleep_or_stop(seconds: float, stop: asyncio.Event | None) -> None:
    if stop is None:
        await asyncio.sleep(seconds)
        return
    with contextlib.suppress(TimeoutError):
        await asyncio.wait_for(stop.wait(), timeout=seconds)
