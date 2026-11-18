"""Sends trip reminders when they're due (#149), every 30 seconds while the service runs.

Each pass claims due reminders one at a time, each in its own transaction:

1. ``SELECT … WHERE status = 'pending' AND send_at <= now() … FOR UPDATE SKIP LOCKED``: the
   row stays locked until the transaction ends, and a second worker passes over it rather
   than sending it too.
2. Send it (or skip it if the trip has left) and mark it ``sent`` or ``skipped`` in the same
   transaction, so a reminder that was sent is never pending again.

Reminders are kept in the database, so nothing is lost while the service is down: the first
pass after a restart sends every overdue reminder whose trip hasn't left yet.

If a reminder can't be sent (Accounts or the mail server is down), its savepoint rolls back:
it stays pending, untouched, and is retried on the next pass. The rest of the pass goes on
without it. As with event handlers, a crash after the mail server accepted the email but
before the commit sends it once more on restart.
"""

import asyncio
import contextlib
import logging
from collections.abc import Callable
from datetime import datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from notifications.adapters.persistence.notification_store import SQLAlchemyNotificationStore
from notifications.adapters.persistence.reminder_store import SQLAlchemyReminderStore
from notifications.application.notification_bell import utc_now
from notifications.application.notify import Notify
from notifications.application.ports import ContactDirectory, EmailSender
from notifications.application.send_reminder import SendReminder

logger = logging.getLogger(__name__)

# How often the scheduler looks for due reminders (#149).
DEFAULT_INTERVAL_SECONDS = 30.0
# At most this many reminders per pass, so one pass can't run on forever.
MAX_PER_PASS = 200


class ReminderScheduler:
    def __init__(
        self,
        *,
        sessions: async_sessionmaker[AsyncSession],
        contacts: ContactDirectory,
        sender: EmailSender,
        web_base_url: str,
        clock: Callable[[], datetime] = utc_now,
        max_per_pass: int = MAX_PER_PASS,
    ) -> None:
        self._sessions = sessions
        self._contacts = contacts
        self._sender = sender
        self._web_base_url = web_base_url
        self._clock = clock
        self._max_per_pass = max_per_pass

    async def run_once(self) -> int:
        """Handles the reminders that are due now. Returns how many were sent or skipped."""
        handled = 0
        failed: set[UUID] = set()  # tried once this pass; the next pass tries again
        while handled + len(failed) < self._max_per_pass:
            async with self._sessions() as session, session.begin():
                store = SQLAlchemyReminderStore(session)
                reminder = await store.claim_next_due(self._clock(), skip=failed)
                if reminder is None:
                    break
                use_case = SendReminder(
                    store=store,
                    notify=Notify(
                        store=SQLAlchemyNotificationStore(session),
                        contacts=self._contacts,
                        sender=self._sender,
                        web_base_url=self._web_base_url,
                        clock=self._clock,
                    ),
                    contacts=self._contacts,
                    clock=self._clock,
                )
                try:
                    async with session.begin_nested():
                        await use_case.execute(reminder)
                except Exception as exc:
                    # Never the email or the pickup: say which reminder, and why.
                    logger.warning(
                        "Reminder %s couldn't be sent; will retry: %s",
                        reminder.id,
                        type(exc).__name__,
                    )
                    failed.add(reminder.id)
                    continue
            handled += 1
        return handled

    async def run(
        self, stop: asyncio.Event, interval_seconds: float = DEFAULT_INTERVAL_SECONDS
    ) -> None:
        """Runs a pass every ``interval_seconds`` until ``stop`` is set."""
        while not stop.is_set():
            try:
                await self.run_once()
            except asyncio.CancelledError:
                raise
            except Exception:
                # E.g. the database is down: try again on the next pass.
                logger.exception("Reminder pass failed; retrying in %ss", interval_seconds)
            # Wait for the next pass, but wake straight away on shutdown.
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(stop.wait(), timeout=interval_seconds)
