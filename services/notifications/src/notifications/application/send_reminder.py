"""Use case: deliver one due trip reminder (#149).

The scheduler claims a due reminder and calls this. If the trip has already left (the
service was down when the reminder was due), it's marked ``skipped``; otherwise the rider
gets it in the app and by email, naming their driver, and it's marked ``sent``. A cancelled
reminder is never claimed, so a cancelled trip gets none.
"""

from notifications.application.notification_bell import Clock, utc_now
from notifications.application.notify import Notify
from notifications.application.ports import ContactDirectory, ReminderStore
from notifications.domain import messages
from notifications.domain.reminders import TripReminder, has_departed


class SendReminder:
    def __init__(
        self,
        *,
        store: ReminderStore,
        notify: Notify,
        contacts: ContactDirectory,
        clock: Clock = utc_now,
    ) -> None:
        self._store = store
        self._notify = notify
        self._contacts = contacts
        self._clock = clock

    async def execute(self, reminder: TripReminder) -> bool:
        """Returns True if it was sent, False if skipped. Raises (and changes nothing) if
        Accounts or the mail server can't be reached, so it's tried again later."""
        now = self._clock()
        if has_departed(reminder, now):
            await self._store.mark_skipped(reminder.id, now)
            return False

        driver_name = None
        if reminder.driver_id is not None:
            found = await self._contacts.contacts([reminder.driver_id])
            if driver := found.get(reminder.driver_id):
                driver_name = driver.first_name

        await self._notify(
            [
                messages.trip_reminder(
                    rider_id=reminder.rider_id,
                    trip_id=reminder.trip_id,
                    request_id=reminder.request_id,
                    departure_at=reminder.departure_at,
                    pickup_label=reminder.pickup_label,
                    driver_first_name=driver_name,
                )
            ]
        )
        await self._store.mark_sent(reminder.id, now)
        return True
