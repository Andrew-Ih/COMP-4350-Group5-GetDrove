"""The demo seed command (#111, #180) against a real PostgreSQL, with the real
infra/seed/demo.json: the accounts it creates can log in straight away, the drivers are
approved (or left pending) with their cars and placeholder documents, and running it twice
is safe."""

import io
import json
from pathlib import Path
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from accounts.adapters.document_storage import FileDocumentStorage
from accounts.adapters.persistence.tables import driver_profiles, outbox, users
from accounts.application.seed_accounts import SeedResult
from accounts.application.seed_drivers import SeedDriversResult
from accounts.infrastructure import seed as seed_command

DEMO_FILE = Path(__file__).resolve().parents[4] / "infra" / "seed" / "demo.json"
PASSWORD = "demo password 2026"  # noqa: S105 (a test password)


def demo() -> dict[str, Any]:
    raw: dict[str, Any] = json.loads(DEMO_FILE.read_text(encoding="utf-8"))
    return raw


def demo_emails() -> list[str]:
    raw = demo()
    return [p["email"] for p in [*raw["drivers"], *raw["riders"], raw["admin"]]]


def drivers_by_approval(approval: str) -> list[str]:
    return [d["email"] for d in demo()["drivers"] if d.get("approval", "approved") == approval]


async def run_seed(
    session: AsyncSession, tmp_path: Path, raw: str | None = None, *, make_admin: bool = False
) -> tuple[SeedResult, SeedDriversResult]:
    return await seed_command.seed(
        raw if raw is not None else DEMO_FILE.read_text(encoding="utf-8"),
        PASSWORD,
        async_sessionmaker(session.bind, expire_on_commit=False),
        FileDocumentStorage(tmp_path / "documents"),
        make_admin=make_admin,
    )


async def test_every_demo_person_gets_a_verified_account(
    session: AsyncSession, tmp_path: Path
) -> None:
    accounts, _ = await run_seed(session, tmp_path)

    assert accounts.created == demo_emails()
    rows = (await session.execute(select(users.c.email, users.c.email_verified_at))).all()
    assert {row.email for row in rows} == set(demo_emails())
    assert all(row.email_verified_at is not None for row in rows)


async def test_drivers_are_approved_or_left_pending_as_demo_json_says(
    session: AsyncSession, tmp_path: Path
) -> None:
    _, drivers = await run_seed(session, tmp_path)

    assert drivers.approved == drivers_by_approval("approved")
    assert drivers.pending == drivers_by_approval("pending")
    assert drivers.pending, "demo.json should leave someone for the admin to review"
    rows = (
        await session.execute(
            select(users.c.email, driver_profiles)
            .join(driver_profiles, driver_profiles.c.user_id == users.c.id)
            .order_by(users.c.email)
        )
    ).all()
    by_email = {row.email: row for row in rows}
    for driver in demo()["drivers"]:
        row = by_email[driver["email"]]
        assert row.status == driver.get("approval", "approved")
        assert row.vehicle_plate == driver["vehicle"]["plate"]
        # Placeholder documents the admin page can open.
        for key in (row.licence_key, row.insurance_key):
            assert (tmp_path / "documents" / key).read_bytes().startswith(b"%PDF-")


async def test_only_driver_approved_events_are_published(
    session: AsyncSession, tmp_path: Path
) -> None:
    """DriverApproved, so Trips lets the drivers post; no UserRegistered, so no
    verification emails go out."""
    await run_seed(session, tmp_path)

    envelopes = (await session.execute(select(outbox.c.envelope).order_by(outbox.c.id))).all()
    assert [e.envelope["type"] for e in envelopes] == ["DriverApproved"] * len(
        drivers_by_approval("approved")
    )


async def test_the_demo_admin_is_an_admin_only_when_asked(
    session: AsyncSession, tmp_path: Path
) -> None:
    admin_email = demo()["admin"]["email"]
    is_admin = select(users.c.is_admin).where(users.c.email == admin_email)

    _, drivers = await run_seed(session, tmp_path)
    assert drivers.admins == []
    assert (await session.execute(is_admin)).scalar_one() is False

    _, drivers = await run_seed(session, tmp_path, make_admin=True)
    assert drivers.admins == [admin_email]
    assert (await session.execute(is_admin)).scalar_one() is True


async def test_a_file_piped_in_from_windows_powershell_works(
    session: AsyncSession, tmp_path: Path
) -> None:
    """PowerShell 5.1 puts a byte-order mark in front of text piped to a command."""
    accounts, _ = await run_seed(session, tmp_path, "﻿" + DEMO_FILE.read_text(encoding="utf-8"))

    assert len(accounts.created) == len(demo_emails())


async def test_a_seeded_driver_can_log_in(
    api: AsyncClient, session: AsyncSession, tmp_path: Path
) -> None:
    await run_seed(session, tmp_path)
    driver = demo()["drivers"][0]

    response = await api.post("/auth/login", json={"email": driver["email"], "password": PASSWORD})

    assert response.status_code == 200
    auth = {"Authorization": f"Bearer {response.json()['accessToken']}"}
    me = await api.get("/me", headers=auth)
    assert me.json()["firstName"] == driver["firstName"]
    assert me.json()["emailVerified"] is True


async def test_running_it_twice_creates_and_approves_nothing_new(
    session: AsyncSession, tmp_path: Path
) -> None:
    await run_seed(session, tmp_path)

    accounts, drivers = await run_seed(session, tmp_path)

    assert accounts.created == []
    assert len(accounts.already_there) == len(demo_emails())
    assert drivers.approved == []
    assert drivers.already_approved == drivers_by_approval("approved")
    assert drivers.pending == drivers_by_approval("pending")
    envelopes = (await session.execute(select(outbox.c.id))).all()
    assert len(envelopes) == len(drivers_by_approval("approved"))


def test_the_command_reads_stdin_and_reports(
    session: AsyncSession,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The way it's run: demo.json on stdin, the password in SEED_PASSWORD, and the
    database from ACCOUNTS_DATABASE_URL (the test database here)."""
    monkeypatch.setenv("SEED_PASSWORD", PASSWORD)
    monkeypatch.setenv("ACCOUNTS_DOCUMENTS_DIR", str(tmp_path / "documents"))
    monkeypatch.delenv("SEED_DEMO_ADMIN", raising=False)
    monkeypatch.setattr("sys.stdin", io.StringIO(DEMO_FILE.read_text(encoding="utf-8")))

    assert seed_command.main() == 0
    first = capsys.readouterr().out
    monkeypatch.setenv("SEED_DEMO_ADMIN", "true")
    monkeypatch.setattr("sys.stdin", io.StringIO(DEMO_FILE.read_text(encoding="utf-8")))
    assert seed_command.main() == 0
    second = capsys.readouterr().out

    count = len(demo_emails())
    approved, pending = drivers_by_approval("approved"), drivers_by_approval("pending")
    assert f"{count} created, 0 already there; {len(approved)} drivers approved now" in first
    assert f"approved  {approved[0]}" in first
    assert f"pending   {pending[0]}" in first
    assert "admin     " not in first
    assert f"0 created, {count} already there; 0 drivers approved now" in second
    assert f"driving   {approved[0]}" in second
    assert f"admin     {demo()['admin']['email']}" in second


def test_without_a_password_it_creates_nothing(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv("SEED_PASSWORD", raising=False)

    assert seed_command.main() == 2
    assert "SEED_PASSWORD" in capsys.readouterr().err


ADMIN = (
    '"admin": {"email": "getdrove.demo.admin@myumanitoba.ca", "firstName": "A", "lastName": "B"}'
)


@pytest.mark.parametrize(
    "stdin",
    [
        "not json",
        "[]",
        '{"drivers": [{"email": "getdrove.demo.x@myumanitoba.ca"}]}',
        '{"drivers": [], "riders": []}',  # no admin
        '{"drivers": [{"email": "getdrove.demo.x@myumanitoba.ca", "firstName": "X",'
        ' "lastName": "Y"}], "riders": [], ' + ADMIN + "}",  # a driver without a car
    ],
)
def test_a_broken_file_creates_nothing(
    stdin: str, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("SEED_PASSWORD", PASSWORD)
    monkeypatch.setattr("sys.stdin", io.StringIO(stdin))

    assert seed_command.main() == 1
    assert "Nothing was created" in capsys.readouterr().err
