"""A durable two-phase hold worker: snapshot card references, then call the provider."""

import asyncio
import contextlib
import logging
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from events.outbox import OutboxPublisher
from payments.adapters.hold_events import OutboxHoldEvents
from payments.adapters.persistence.holds import SQLAlchemyHolds
from payments.adapters.persistence.tables import outbox
from payments.application.holds import HoldPayments
from payments.application.ports import PaymentGatewayPort, SavedCardLookup
from payments.domain.holds import HoldStatus, PaymentHold

logger = logging.getLogger(__name__)


def utc_now() -> datetime:
    return datetime.now(UTC)


class HoldWorker:
    def __init__(
        self,
        sessions: async_sessionmaker[AsyncSession],
        cards: SavedCardLookup,
        gateway: PaymentGatewayPort,
        *,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self.sessions = sessions
        self.cards = cards
        self.gateway = gateway
        self.clock = clock

    def use_case(self, session: AsyncSession, correlation_id: str | None) -> HoldPayments:
        return HoldPayments(
            SQLAlchemyHolds(session),
            self.gateway,
            OutboxHoldEvents(
                OutboxPublisher(session, outbox, producer="payments", correlation_id=correlation_id)
            ),
        )

    async def process(self, request_id: UUID, now: datetime | None = None) -> None:
        current_time = now or self.clock()
        async with self.sessions() as session:
            candidate = await SQLAlchemyHolds(session).get(request_id)
        if candidate is None:
            return
        card = None
        if candidate.needs_card(current_time):
            # Customer discovery/Stripe paging must not hold a transaction, pooled
            # connection, or hold row lock. A failed lookup is never proof of no card.
            card = await self.cards.for_rider(candidate.rider_id)
        elif (
            candidate.card is None
            and not candidate.release_requested
            and current_time < candidate.departure_at
        ):
            return
        current_time = now or self.clock()
        async with self.sessions() as session, session.begin():
            hold = await SQLAlchemyHolds(session).lock(request_id, skip_locked=True)
            if hold is None:
                return
            if not hold.release_requested:
                # Reload under the lock: cancellation or another worker's committed
                # snapshot takes priority over the discovery result above.
                await self.use_case(session, hold.correlation_id).prepare(
                    request_id, current_time, card
                )
        await self._finish(request_id, now or self.clock())

    async def _finish(self, request_id: UUID, now: datetime) -> None:
        # Credentials and first-attempt time are committed before any authorization call.
        async with self.sessions() as session, session.begin():
            hold = await SQLAlchemyHolds(session).lock(request_id, skip_locked=True)
            if hold is None:
                return
            # Keep this row locked across the bounded Stripe call so parallel workers
            # cannot authorize/capture this request concurrently. Stripe also gets the
            # stable request-based key to cover process crashes after provider success.
            if hold.release_requested:
                await self.use_case(session, hold.correlation_id).release(request_id, now)
            else:
                await self.use_case(session, hold.correlation_id).authorize(request_id, now)
            current = await SQLAlchemyHolds(session).lock(request_id)
            if (
                current
                and current.retry_at is None
                and (
                    current.status is HoldStatus.SCHEDULED
                    or (current.release_requested and current.status is not HoldStatus.RELEASED)
                )
            ):
                logger.error(
                    "Hold requires provider reconciliation",
                    extra={"seat_request_id": str(request_id)},
                )

    async def capture(self, request_id: UUID) -> PaymentHold:
        async with self.sessions() as session, session.begin():
            return await self.use_case(session, None).capture(request_id)

    async def defer(self, request_id: UUID) -> None:
        """A missing lookup must not monopolize every batch or mean no_card."""
        async with self.sessions() as session, session.begin():
            repository = SQLAlchemyHolds(session)
            hold = await repository.lock(request_id)
            if (
                hold
                and hold.retry_at is not None
                and (hold.status is HoldStatus.SCHEDULED or hold.release_requested)
            ):
                await repository.save(replace(hold, retry_at=self.clock() + timedelta(seconds=30)))

    async def run_once(self, limit: int = 20) -> int:
        """Claim due work without waiting for rows another worker is processing.

        Release the short claim transaction before card discovery. Concurrent
        discovery is harmless: the prepare lock chooses one immutable snapshot and
        the authorization lock/idempotency key protect the provider operation.
        """
        attempted: set[UUID] = set()
        while len(attempted) < limit:
            request_id = None
            try:
                async with self.sessions() as session, session.begin():
                    repository = SQLAlchemyHolds(session)
                    due = await repository.due(self.clock(), limit=1, skip=attempted)
                    if not due:
                        break
                    request_id = due[0]
                    attempted.add(request_id)
                await self.process(request_id)
            except Exception:
                if request_id is None:
                    raise
                logger.exception(
                    "Hold processing failed", extra={"seat_request_id": str(request_id)}
                )
                await self.defer(request_id)
        return len(attempted)

    async def run(self, stop: asyncio.Event) -> None:
        while not stop.is_set():
            try:
                await self.run_once()
            except Exception:
                logger.exception("Could not poll scheduled holds")
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(stop.wait(), timeout=2)
