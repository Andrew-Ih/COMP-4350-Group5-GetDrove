"""Creates the demo people in infra/seed/demo.json (#111, #180): verified accounts for every
driver, rider and the admin; the admin role; and each driver's application to drive, with
placeholder documents and their vehicle, approved (or left pending, where demo.json says).

Run it where Accounts runs, with demo.json on standard input and the shared demo password
in SEED_PASSWORD (never committed). Locally, SEED_DEMO_ADMIN=true also gives the demo
admin the admin role (never on the live site: see SeedDrivers):

    docker compose exec -T -e SEED_PASSWORD -e SEED_DEMO_ADMIN accounts \\
        python -m accounts.infrastructure.seed < infra/seed/demo.json

It uses the service's own database and document folder, writes only Accounts' data, and
sends no email (approving publishes DriverApproved, as the admin page does, so Trips lets
the driver post). Running it again skips what's already there. See infra/seed/README.md.
"""

import asyncio
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from accounts.adapters.clock import SystemClock
from accounts.adapters.document_storage import FileDocumentStorage
from accounts.adapters.persistence.unit_of_work import SqlUnitOfWork
from accounts.adapters.security.password_hasher import Argon2PasswordHasher
from accounts.application.ports import DocumentStorage
from accounts.application.seed_accounts import DemoAccount, SeedAccounts, SeedResult
from accounts.application.seed_drivers import (
    DemoDriver,
    DemoVehicle,
    SeedDrivers,
    SeedDriversResult,
)
from accounts.infrastructure.settings import get_settings
from common_web import DomainError, InvalidInputError


@dataclass(frozen=True)
class DemoPeople:
    accounts: list[DemoAccount]
    drivers: list[DemoDriver]
    admin_email: str


def _account(person: Any, where: str) -> DemoAccount:
    try:
        return DemoAccount(person["email"], person["firstName"], person["lastName"])
    except (KeyError, TypeError) as exc:
        raise ValueError(f"{where} needs email, firstName and lastName ({exc})") from exc


def _driver(person: Any, where: str) -> DemoDriver:
    vehicle = person.get("vehicle")
    try:
        demo_vehicle = DemoVehicle(
            vehicle["make"], vehicle["model"], vehicle["colour"], vehicle["plate"]
        )
    except (KeyError, TypeError) as exc:
        raise ValueError(f"{where}.vehicle needs make, model, colour and plate ({exc})") from exc
    approval = person.get("approval", "approved")
    if approval not in ("approved", "pending"):
        raise ValueError(f"{where}.approval must be approved or pending")
    return DemoDriver(person["email"], demo_vehicle, approved=approval == "approved")


def demo_people(raw: Any) -> DemoPeople:
    """The account fields, vehicles, approvals and the admin in demo.json. The rest of the
    file (homes, trips, requests) is for the trips script."""
    if not isinstance(raw, dict):
        raise ValueError("demo.json must be a JSON object with drivers, riders and an admin")
    drivers = raw.get("drivers", [])
    riders = raw.get("riders", [])
    admin = raw.get("admin")
    if not isinstance(drivers, list) or not isinstance(riders, list):
        raise ValueError("drivers and riders must be lists")
    if not isinstance(admin, dict):
        raise ValueError("admin must be an object with email, firstName and lastName")
    accounts = [_account(p, f"drivers[{i}]") for i, p in enumerate(drivers)]
    accounts += [_account(p, f"riders[{i}]") for i, p in enumerate(riders)]
    admin_account = _account(admin, "admin")
    accounts.append(admin_account)
    demo_drivers = [_driver(p, f"drivers[{i}]") for i, p in enumerate(drivers)]
    return DemoPeople(accounts, demo_drivers, admin_account.email)


async def seed(
    raw_json: str,
    password: str,
    sessions: async_sessionmaker[AsyncSession],
    storage: DocumentStorage,
    *,
    make_admin: bool = False,
) -> tuple[SeedResult, SeedDriversResult]:
    # Windows PowerShell adds a byte-order mark when piping a file in; JSON refuses it.
    people = demo_people(json.loads(raw_json.lstrip("﻿")))
    clock = SystemClock()
    uow = SqlUnitOfWork(sessions)
    accounts = await SeedAccounts(uow, Argon2PasswordHasher(), clock)(people.accounts, password)
    drivers = await SeedDrivers(uow, storage, clock)(
        people.drivers, people.admin_email, make_admin=make_admin
    )
    return accounts, drivers


async def _main(
    raw_json: str, password: str, make_admin: bool
) -> tuple[SeedResult, SeedDriversResult]:
    settings = get_settings()
    engine = create_async_engine(settings.database_url)
    try:
        return await seed(
            raw_json,
            password,
            async_sessionmaker(engine, expire_on_commit=False),
            FileDocumentStorage(Path(settings.documents_dir)),
            make_admin=make_admin,
        )
    finally:
        await engine.dispose()


def main() -> int:
    password = os.environ.get("SEED_PASSWORD", "")
    if not password:
        print("Set SEED_PASSWORD to the demo accounts' password.", file=sys.stderr)
        return 2
    # Only locally: an admin can open every applicant's documents, and the demo password is
    # shared with testers. On the live site, make a team member's own account admin.
    make_admin = os.environ.get("SEED_DEMO_ADMIN", "").lower() in ("1", "true", "yes")
    try:
        accounts, drivers = asyncio.run(_main(sys.stdin.read(), password, make_admin))
    except (ValueError, InvalidInputError) as exc:
        print(f"Nothing was created: {exc}", file=sys.stderr)
        return 1
    except DomainError as exc:
        print(f"Stopped: {exc}", file=sys.stderr)
        return 1
    for email in accounts.created:
        print(f"created   {email}")
    for email in accounts.already_there:
        print(f"exists    {email}")
    for email in drivers.admins:
        print(f"admin     {email}")
    for email in drivers.approved:
        print(f"approved  {email}")
    for email in drivers.pending:
        print(f"pending   {email}")
    for email in drivers.already_approved:
        print(f"driving   {email}")
    print(
        f"{len(accounts.created)} created, {len(accounts.already_there)} already there; "
        f"{len(drivers.approved)} drivers approved now, "
        f"{len(drivers.already_approved)} already approved, {len(drivers.pending)} pending."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
