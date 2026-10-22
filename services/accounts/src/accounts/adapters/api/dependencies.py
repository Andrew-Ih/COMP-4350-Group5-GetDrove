"""What route handlers need, provided per request by FastAPI's ``Depends``."""

from typing import Annotated

from fastapi import Depends, Request

from accounts.adapters.clock import SystemClock
from accounts.adapters.persistence.unit_of_work import SqlUnitOfWork
from accounts.adapters.security.access_tokens import JwtAccessTokenIssuer
from accounts.adapters.security.password_hasher import Argon2PasswordHasher
from accounts.application.ports import AccessTokenIssuer, Clock, PasswordHasher, UnitOfWork

# One per process: building it makes the dummy hash that login's timing relies on.
_password_hasher = Argon2PasswordHasher()


def get_unit_of_work(request: Request) -> UnitOfWork:
    return SqlUnitOfWork(request.app.state.sessions)


def get_clock() -> Clock:
    return SystemClock()


def get_password_hasher() -> PasswordHasher:
    return _password_hasher


def get_access_token_issuer(request: Request) -> AccessTokenIssuer:
    # Signs with the same key the app publishes at /.well-known/jwks.json.
    return JwtAccessTokenIssuer(request.app.state.signing_key)


Uow = Annotated[UnitOfWork, Depends(get_unit_of_work)]
AppClock = Annotated[Clock, Depends(get_clock)]
Hasher = Annotated[PasswordHasher, Depends(get_password_hasher)]
AccessTokens = Annotated[AccessTokenIssuer, Depends(get_access_token_issuer)]
