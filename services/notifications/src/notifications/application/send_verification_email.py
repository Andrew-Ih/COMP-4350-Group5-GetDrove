"""Use case: email a student their verification link (#93), after UserRegistered or
VerificationEmailRequested from Accounts."""

from notifications.application.ports import EmailSender
from notifications.domain.verification_email import verification_email


class SendVerificationEmail:
    def __init__(self, sender: EmailSender, web_base_url: str) -> None:
        self._sender = sender
        self._web_base_url = web_base_url

    async def __call__(self, *, email: str, first_name: str, verification_token: str) -> None:
        await self._sender.send(
            verification_email(
                to=email,
                first_name=first_name,
                token=verification_token,
                web_base_url=self._web_base_url,
            )
        )
