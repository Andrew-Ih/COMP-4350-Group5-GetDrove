"""Errors the Notifications API turns into HTTP responses."""

from common_web.errors import NotFoundError


class NotificationNotFoundError(NotFoundError):
    """No notification with this ID belongs to the user. Someone else's notification gets
    the same answer as a missing one, so IDs can't be probed."""

    code = "notification_not_found"
    title = "Notification not found"

    def __init__(self) -> None:
        super().__init__("No notification with this ID for you")
