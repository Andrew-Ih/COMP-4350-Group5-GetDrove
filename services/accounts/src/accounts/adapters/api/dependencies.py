"""What route handlers need, provided per request by FastAPI's ``Depends``."""

from typing import Annotated

from fastapi import Depends, Request

from accounts.adapters.clock import SystemClock
from accounts.adapters.persistence.unit_of_work import SqlUnitOfWork
from accounts.adapters.security.password_hasher import Argon2PasswordHasher
from accounts.application.ports import Clock, PasswordHasher, UnitOfWork

_password_hasher = Argon2PasswordHasher()  # stateless, so one is shared by every request


def get_unit_of_work(request: Request) -> UnitOfWork:
    return SqlUnitOfWork(request.app.state.sessions)


def get_clock() -> Clock:
    return SystemClock()


def get_password_hasher() -> PasswordHasher:
    return _password_hasher


Uow = Annotated[UnitOfWork, Depends(get_unit_of_work)]
AppClock = Annotated[Clock, Depends(get_clock)]
Hasher = Annotated[PasswordHasher, Depends(get_password_hasher)]
