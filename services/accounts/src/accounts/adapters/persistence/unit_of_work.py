"""The PostgreSQL ``UnitOfWork``: one session, and so one transaction, per use case."""

from typing import Self

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from accounts.adapters.persistence.refresh_token_repository import SqlRefreshTokenRepository
from accounts.adapters.persistence.tables import outbox
from accounts.adapters.persistence.user_repository import SqlUserRepository
from accounts.adapters.persistence.verification_token_repository import (
    SqlVerificationTokenRepository,
)
from common_web import current_request_id
from events.outbox import OutboxPublisher


class SqlUnitOfWork:
    """The repositories and the outbox share one session, so a change and its events are
    committed together. Leaving ``async with`` without ``commit()`` rolls back."""

    users: SqlUserRepository
    verification_tokens: SqlVerificationTokenRepository
    refresh_tokens: SqlRefreshTokenRepository
    events: OutboxPublisher

    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def __aenter__(self) -> Self:
        self._session = self._sessions()
        self.users = SqlUserRepository(self._session)
        self.verification_tokens = SqlVerificationTokenRepository(self._session)
        self.refresh_tokens = SqlRefreshTokenRepository(self._session)
        # The request ID travels with the event, so one action can be traced across services.
        self.events = OutboxPublisher(
            self._session, outbox, producer="accounts", correlation_id=current_request_id()
        )
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self._session.rollback()  # does nothing if commit() already ran
        await self._session.close()

    async def commit(self) -> None:
        await self._session.commit()
