"""Use case: tell people something (#146). Each message becomes an in-app notification in
the bell and an email.

Event handlers call this inside the transaction that records the event in
``processed_events``, so a repeated event notifies nobody twice. If Accounts can't give the
email addresses, or an email can't be handed to the mail server, it raises: the in-app
notifications roll back too, and the whole event is retried. A retry after some emails of
a multi-person event went out sends those again; only ``TripCancelled`` has more than one.
"""

import logging
from collections.abc import Sequence

from notifications.application.notification_bell import Clock, utc_now
from notifications.application.ports import ContactDirectory, EmailSender, NotificationStore
from notifications.domain.messages import Message
from notifications.domain.notification_email import notification_email
from notifications.domain.notifications import Notification

logger = logging.getLogger(__name__)


class Notify:
    def __init__(
        self,
        *,
        store: NotificationStore,
        contacts: ContactDirectory,
        sender: EmailSender,
        web_base_url: str,
        clock: Clock = utc_now,
    ) -> None:
        self._store = store
        self._contacts = contacts
        self._sender = sender
        self._web_base_url = web_base_url
        self._clock = clock

    async def __call__(self, messages: Sequence[Message]) -> None:
        if not messages:
            return
        found = await self._contacts.contacts(list(dict.fromkeys(m.user_id for m in messages)))

        now = self._clock()
        for message in messages:
            await self._store.add(
                Notification(
                    user_id=message.user_id,
                    type=message.type,
                    title=message.title,
                    body=message.body,
                    created_at=now,
                    trip_id=message.trip_id,
                    request_id=message.request_id,
                )
            )

        for message in messages:
            contact = found.get(message.user_id)
            if contact is None:
                # E.g. a deleted account. They still get the in-app notification.
                logger.warning(
                    "No contact for user %s; %s sent in-app only", message.user_id, message.type
                )
                continue
            await self._sender.send(notification_email(contact, message, self._web_base_url))
