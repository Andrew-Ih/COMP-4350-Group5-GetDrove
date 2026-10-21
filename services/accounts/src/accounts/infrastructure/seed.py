"""Creates the verified demo accounts listed in infra/seed/demo.json (#111).

Run it where Accounts runs, with demo.json on standard input and the shared demo password
in SEED_PASSWORD (never committed):

    docker compose -f infra/docker-compose.yml exec -T -e SEED_PASSWORD accounts \\
        python -m accounts.infrastructure.seed < infra/seed/demo.json

It uses the service's own database settings, writes only Accounts' tables, and sends no
email. Running it again skips accounts that already exist. See infra/seed/README.md.
"""

import asyncio
import json
import os
import sys
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from accounts.adapters.clock import SystemClock
from accounts.adapters.persistence.unit_of_work import SqlUnitOfWork
from accounts.adapters.security.password_hasher import Argon2PasswordHasher
from accounts.application.seed_accounts import DemoAccount, SeedAccounts, SeedResult
from accounts.infrastructure.settings import get_settings
from common_web import InvalidInputError


def demo_accounts(raw: Any) -> list[DemoAccount]:
    """The drivers and riders in demo.json. Only the account fields are read; the rest of
    the file (homes, trips) is for the trips script."""
    if not isinstance(raw, dict):
        raise ValueError("demo.json must be a JSON object with drivers and riders")
    people = [*raw.get("drivers", []), *raw.get("riders", [])]
    try:
        return [DemoAccount(p["email"], p["firstName"], p["lastName"]) for p in people]
    except (KeyError, TypeError) as exc:
        raise ValueError(f"every person needs email, firstName and lastName ({exc})") from exc


async def seed(
    raw_json: str, password: str, sessions: async_sessionmaker[AsyncSession]
) -> SeedResult:
    # Windows PowerShell adds a byte-order mark when piping a file in; JSON refuses it.
    accounts = demo_accounts(json.loads(raw_json.lstrip("\ufeff")))
    use_case = SeedAccounts(SqlUnitOfWork(sessions), Argon2PasswordHasher(), SystemClock())
    return await use_case(accounts, password)


async def _main(raw_json: str, password: str) -> SeedResult:
    engine = create_async_engine(get_settings().database_url)
    try:
        return await seed(raw_json, password, async_sessionmaker(engine, expire_on_commit=False))
    finally:
        await engine.dispose()


def main() -> int:
    password = os.environ.get("SEED_PASSWORD", "")
    if not password:
        print("Set SEED_PASSWORD to the demo accounts' password.", file=sys.stderr)
        return 2
    try:
        result = asyncio.run(_main(sys.stdin.read(), password))
    except (ValueError, InvalidInputError) as exc:
        print(f"Nothing was created: {exc}", file=sys.stderr)
        return 1
    for email in result.created:
        print(f"created   {email}")
    for email in result.already_there:
        print(f"exists    {email}")
    print(f"{len(result.created)} created, {len(result.already_there)} already there.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
