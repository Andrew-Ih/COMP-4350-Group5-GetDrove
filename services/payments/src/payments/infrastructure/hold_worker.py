"""A durable two-phase hold worker: snapshot card references, then call the provider."""

import asyncio
import contextlib
import logging
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


class HoldWorker:
    def __init__(
        self,
        sessions: async_sessionmaker[AsyncSession],
        cards: SavedCardLookup,
        gateway: PaymentGatewayPort,
    ) -> None:
        self.sessions = sessions
        self.cards = cards
        self.gateway = gateway

    def use_case(self, session: AsyncSession, correlation_id: str | None) -> HoldPayments:
        return HoldPayments(
            SQLAlchemyHolds(session),
            self.cards,
            self.gateway,
            OutboxHoldEvents(
                OutboxPublisher(session, outbox, producer="payments", correlation_id=correlation_id)
            ),
        )

    async def process(self, request_id: UUID, now: datetime | None = None) -> None:
        now = now or datetime.now(UTC)
        async with self.sessions() as session, session.begin():
            hold = await SQLAlchemyHolds(session).lock(request_id)
            if hold is None:
                return
            await self.use_case(session, hold.correlation_id).prepare(request_id, now)
        # Credentials and first-attempt time are committed before any authorization call.
        async with self.sessions() as session, session.begin():
            hold = await SQLAlchemyHolds(session).lock(request_id)
            if hold is None:
                return
            await self.use_case(session, hold.correlation_id).authorize(request_id, now)
            current = await SQLAlchemyHolds(session).lock(request_id)
            if current and current.status is HoldStatus.SCHEDULED and current.retry_at is None:
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
            if hold and hold.status is HoldStatus.SCHEDULED and hold.retry_at is not None:
                await repository.save(
                    replace(hold, retry_at=datetime.now(UTC) + timedelta(seconds=30))
                )

    async def run(self, stop: asyncio.Event) -> None:
        while not stop.is_set():
            try:
                async with self.sessions() as session:
                    due = await SQLAlchemyHolds(session).due(datetime.now(UTC))
                for request_id in due:
                    try:
                        await self.process(request_id)
                    except Exception:
                        logger.exception(
                            "Hold processing failed", extra={"seat_request_id": str(request_id)}
                        )
                        await self.defer(request_id)
            except Exception:
                logger.exception("Could not poll scheduled holds")
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(stop.wait(), timeout=2)
