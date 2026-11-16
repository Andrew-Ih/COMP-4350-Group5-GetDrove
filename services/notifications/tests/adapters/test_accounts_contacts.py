"""HTTPContactDirectory (#146): asks Accounts' /internal/contacts, in batches of 50, and
turns any failure into ContactsUnavailableError so the event is retried."""

import json
from uuid import UUID, uuid4

import httpx
import pytest

from notifications.adapters.accounts import HTTPContactDirectory
from notifications.application.ports import ContactsUnavailableError
from notifications.domain.notification_email import Contact


def directory(handler: httpx.MockTransport) -> HTTPContactDirectory:
    return HTTPContactDirectory(httpx.AsyncClient(transport=handler, base_url="http://accounts"))


def accounts_knowing(
    known: dict[UUID, tuple[str, str]], calls: list[list[str]]
) -> httpx.MockTransport:
    """A fake Accounts that knows ``known`` (ID: first name, email) and records each call."""

    def handle(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/internal/contacts"
        ids = request.url.params.get_list("ids")
        calls.append(ids)
        contacts = [
            {"id": i, "firstName": known[UUID(i)][0], "email": known[UUID(i)][1]}
            for i in ids
            if UUID(i) in known
        ]
        return httpx.Response(200, json={"contacts": contacts})

    return httpx.MockTransport(handle)


async def test_returns_contacts_by_id_and_leaves_unknown_users_out() -> None:
    ada, stranger = uuid4(), uuid4()
    calls: list[list[str]] = []

    found = await directory(accounts_knowing({ada: ("Ada", "ada@myumanitoba.ca")}, calls)).contacts(
        [ada, stranger]
    )

    assert found == {ada: Contact("Ada", "ada@myumanitoba.ca")}
    assert calls == [[str(ada), str(stranger)]]


async def test_asks_in_batches_of_50() -> None:
    users = [uuid4() for _ in range(120)]
    calls: list[list[str]] = []

    found = await directory(
        accounts_knowing({u: ("A", f"{u}@myumanitoba.ca") for u in users}, calls)
    ).contacts(users)

    assert [len(call) for call in calls] == [50, 50, 20]
    assert set(found) == set(users)


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(503),
        httpx.Response(501, json={"detail": "Not implemented"}),
        httpx.Response(200, content=b"not JSON"),
        httpx.Response(200, json={"contacts": [{"id": "nope"}]}),
    ],
)
async def test_any_failure_means_contacts_are_unavailable(response: httpx.Response) -> None:
    transport = httpx.MockTransport(lambda request: response)

    with pytest.raises(ContactsUnavailableError):
        await directory(transport).contacts([uuid4()])


async def test_a_timeout_means_contacts_are_unavailable() -> None:
    def time_out(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("Accounts is slow", request=request)

    with pytest.raises(ContactsUnavailableError):
        await directory(httpx.MockTransport(time_out)).contacts([uuid4()])


async def test_failures_never_log_what_accounts_sent(caplog: pytest.LogCaptureFixture) -> None:
    body = json.dumps({"contacts": [{"id": str(uuid4()), "email": "ada@myumanitoba.ca"}]})
    transport = httpx.MockTransport(lambda request: httpx.Response(200, content=body))

    with pytest.raises(ContactsUnavailableError):
        await directory(transport).contacts([uuid4()])

    assert "ada@" not in caplog.text
