"""What route handlers need, provided per request by FastAPI's ``Depends``."""

from typing import Annotated

from fastapi import Depends, Request

from accounts.adapters.clock import SystemClock
from accounts.adapters.persistence.unit_of_work import SqlUnitOfWork
from accounts.application.ports import Clock, UnitOfWork


def get_unit_of_work(request: Request) -> UnitOfWork:
    return SqlUnitOfWork(request.app.state.sessions)


def get_clock() -> Clock:
    return SystemClock()


Uow = Annotated[UnitOfWork, Depends(get_unit_of_work)]
AppClock = Annotated[Clock, Depends(get_clock)]
