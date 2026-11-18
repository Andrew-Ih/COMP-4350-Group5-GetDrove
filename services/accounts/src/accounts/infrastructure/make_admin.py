"""Gives an existing account the admin role (#127), so it can approve drivers.

Run it where Accounts runs. The student signs up (or is seeded) first:

    docker compose exec accounts python -m accounts.infrastructure.make_admin ada@myumanitoba.ca

They get the admin role at their next login (or within 15 minutes, when their access token
is refreshed). There's no endpoint for this on purpose: only someone who can run commands
on the server can make an admin.
"""

import asyncio
import sys

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from accounts.adapters.persistence.unit_of_work import SqlUnitOfWork
from accounts.application.admin import MakeAdmin
from accounts.domain.user import User
from accounts.infrastructure.settings import get_settings
from common_web import DomainError


async def make_admin(email: str) -> User:
    engine = create_async_engine(get_settings().database_url)
    try:
        uow = SqlUnitOfWork(async_sessionmaker(engine, expire_on_commit=False))
        return await MakeAdmin(uow)(email)
    finally:
        await engine.dispose()


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print("Usage: python -m accounts.infrastructure.make_admin <email>", file=sys.stderr)
        return 2
    try:
        user = asyncio.run(make_admin(argv[0]))
    except DomainError as exc:  # not a UofM email, or no such account
        print(f"Nobody was made an admin: {exc}", file=sys.stderr)
        return 1
    print(f"{user.email.value} is an admin. They get the role at their next login.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
