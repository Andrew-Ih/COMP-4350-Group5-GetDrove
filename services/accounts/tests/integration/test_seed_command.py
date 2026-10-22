"""The demo seed command (#111) against a real PostgreSQL, with the real infra/seed/demo.json:
the accounts it creates can log in straight away, and running it twice is safe."""

import io
import json
from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from accounts.adapters.persistence.tables import outbox, users
from accounts.infrastructure import seed as seed_command

DEMO_FILE = Path(__file__).resolve().parents[4] / "infra" / "seed" / "demo.json"
PASSWORD = "demo password 2026"  # noqa: S105 (a test password)


def demo_people() -> list[dict[str, str]]:
    raw = json.loads(DEMO_FILE.read_text(encoding="utf-8"))
    return [*raw["drivers"], *raw["riders"]]


async def test_every_demo_person_gets_a_verified_account(session: AsyncSession) -> None:
    sessions = async_sessionmaker(session.bind, expire_on_commit=False)

    result = await seed_command.seed(DEMO_FILE.read_text(encoding="utf-8"), PASSWORD, sessions)

    emails = [p["email"] for p in demo_people()]
    assert result.created == emails
    rows = (await session.execute(select(users.c.email, users.c.email_verified_at))).all()
    assert {row.email for row in rows} == set(emails)
    assert all(row.email_verified_at is not None for row in rows)
    # No UserRegistered events, so no verification emails go out.
    assert (await session.execute(select(func.count()).select_from(outbox))).scalar_one() == 0


async def test_a_file_piped_in_from_windows_powershell_works(session: AsyncSession) -> None:
    """PowerShell 5.1 puts a byte-order mark in front of text piped to a command."""
    sessions = async_sessionmaker(session.bind, expire_on_commit=False)

    result = await seed_command.seed(
        "\ufeff" + DEMO_FILE.read_text(encoding="utf-8"), PASSWORD, sessions
    )

    assert len(result.created) == len(demo_people())


async def test_a_seeded_driver_can_log_in(api: AsyncClient, session: AsyncSession) -> None:
    sessions = async_sessionmaker(session.bind, expire_on_commit=False)
    await seed_command.seed(DEMO_FILE.read_text(encoding="utf-8"), PASSWORD, sessions)
    driver = demo_people()[0]

    response = await api.post("/auth/login", json={"email": driver["email"], "password": PASSWORD})

    assert response.status_code == 200
    me = await api.get("/me", headers={"Authorization": f"Bearer {response.json()['accessToken']}"})
    assert me.json()["firstName"] == driver["firstName"]
    assert me.json()["emailVerified"] is True


async def test_running_it_twice_creates_nothing_new(session: AsyncSession) -> None:
    sessions = async_sessionmaker(session.bind, expire_on_commit=False)
    raw = DEMO_FILE.read_text(encoding="utf-8")
    await seed_command.seed(raw, PASSWORD, sessions)

    again = await seed_command.seed(raw, PASSWORD, sessions)

    assert again.created == []
    assert len(again.already_there) == len(demo_people())


def test_the_command_reads_stdin_and_reports(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The way it's run: demo.json on stdin, the password in SEED_PASSWORD, and the
    database from ACCOUNTS_DATABASE_URL (the test database here)."""
    monkeypatch.setenv("SEED_PASSWORD", PASSWORD)
    monkeypatch.setattr("sys.stdin", io.StringIO(DEMO_FILE.read_text(encoding="utf-8")))

    assert seed_command.main() == 0
    first = capsys.readouterr().out
    monkeypatch.setattr("sys.stdin", io.StringIO(DEMO_FILE.read_text(encoding="utf-8")))
    assert seed_command.main() == 0
    second = capsys.readouterr().out

    count = len(demo_people())
    assert f"{count} created, 0 already there." in first
    assert f"0 created, {count} already there." in second
    assert f"exists    {demo_people()[0]['email']}" in second


def test_without_a_password_it_creates_nothing(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv("SEED_PASSWORD", raising=False)

    assert seed_command.main() == 2
    assert "SEED_PASSWORD" in capsys.readouterr().err


@pytest.mark.parametrize(
    "stdin",
    ["not json", "[]", '{"drivers": [{"email": "getdrove.demo.x@myumanitoba.ca"}]}'],
)
def test_a_broken_file_creates_nothing(
    stdin: str, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("SEED_PASSWORD", PASSWORD)
    monkeypatch.setattr("sys.stdin", io.StringIO(stdin))

    assert seed_command.main() == 1
    assert "Nothing was created" in capsys.readouterr().err
