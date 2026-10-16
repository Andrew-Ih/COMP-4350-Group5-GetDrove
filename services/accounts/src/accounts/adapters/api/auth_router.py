"""Accounts API (Sprint 1 contract, issue #108): sign up, verify, log in, refresh, log out,
the current user, and the public keys other services use to check tokens.

Handlers return 501 Not Implemented until the real code lands (#90). Implemented: sign up
(#4), verify and resend verification (#5), log in and /me (#6), and the JWKS endpoint (#91).
Paths are relative to the gateway prefix /api/accounts, except the JWKS endpoint, which
other services also call directly at http://accounts:8000/.well-known/jwks.json.

Tokens:
- Access token: RS256 JWT, 15 minutes. Claims: sub (user ID), roles, iat, exp,
  iss ("getdrove-accounts"), aud ("getdrove"). Sent as `Authorization: Bearer <token>`.
- Refresh token: 7 days, in the HttpOnly, Secure, SameSite=Strict cookie `refresh_token`
  (path /api/accounts/auth), replaced every time it's used.
"""

from typing import Annotated, Any, NoReturn

from fastapi import APIRouter, Cookie, HTTPException, Request, Response

from accounts.adapters.api.dependencies import AccessTokens, AppClock, Hasher, Uow
from accounts.adapters.api.schemas import (
    JwkSet,
    LoginRequest,
    Problem,
    ResendVerificationRequest,
    SignupRequest,
    SignupResponse,
    TokenResponse,
    User,
    VerifyEmailRequest,
)
from accounts.adapters.security.signing_key import SigningKey
from accounts.application.login import GetMe, LogIn
from accounts.application.signup import SignUp
from accounts.application.verification import ResendVerification, VerifyEmail
from accounts.domain.refresh_token import REFRESH_TOKEN_LIFETIME
from common_security.dependencies import AuthenticatedUser

auth_router = APIRouter(prefix="/auth", tags=["auth"])
users_router = APIRouter(tags=["users"])
keys_router = APIRouter(tags=["keys"])

RefreshCookie = Annotated[
    str | None,
    Cookie(alias="refresh_token", description="Set by login and refresh; HttpOnly."),
]

# Typed to match FastAPI's `responses` parameter, so they can be combined with **.
Responses = dict[int | str, dict[str, Any]]


def _problem(description: str, code: str) -> dict[str, Any]:
    return {"model": Problem, "description": f"{description} (code `{code}`)"}


INVALID: Responses = {422: _problem("Invalid input; `errors` lists the fields", "invalid_input")}


def _not_implemented() -> NoReturn:
    raise HTTPException(status_code=501, detail="Not implemented yet: this is a contract (#108).")


REFRESH_COOKIE = "refresh_token"
# The browser reaches Accounts through the gateway at /api/accounts, so this limits the
# cookie to the refresh and logout endpoints; no other request ever carries it.
REFRESH_COOKIE_PATH = "/api/accounts/auth"


def _set_refresh_cookie(response: Response, token: str) -> None:
    """HttpOnly (JavaScript can't read it), Secure (HTTPS only; browsers allow localhost),
    SameSite=Strict (never sent from other sites), for as long as the token lasts."""
    response.set_cookie(
        REFRESH_COOKIE,
        token,
        max_age=int(REFRESH_TOKEN_LIFETIME.total_seconds()),
        path=REFRESH_COOKIE_PATH,
        secure=True,
        httponly=True,
        samesite="strict",
    )


# ---------------------------------------------------------------- sign up and verify


@auth_router.post(
    "/signup",
    status_code=201,
    summary="Sign up",
    description="Creates an unverified account and sends a verification email whose link "
    "is valid for 24 hours. Publishes the UserRegistered event.",
    responses={
        422: _problem(
            "Invalid input, an email that isn't @myumanitoba.ca, or a password under 10 characters",
            "invalid_input / email_not_uofm",
        ),
        409: _problem("An account with this email already exists", "email_taken"),
    },
)
async def signup(body: SignupRequest, uow: Uow, hasher: Hasher, clock: AppClock) -> SignupResponse:
    user = await SignUp(uow, hasher, clock)(
        body.email, body.password, body.first_name, body.last_name
    )
    return SignupResponse(id=user.id, email=user.email.value, email_verified=False)


@auth_router.post(
    "/verify",
    status_code=204,
    summary="Verify email",
    description="Marks the email as verified using the token from the link.",
    responses={
        **INVALID,
        400: _problem("Unknown or already-used token", "invalid_token"),
        410: _problem(
            "The link has expired; request a new one with /auth/resend-verification",
            "token_expired",
        ),
    },
)
async def verify_email(body: VerifyEmailRequest, uow: Uow, clock: AppClock) -> None:
    await VerifyEmail(uow, clock)(body.token)


@auth_router.post(
    "/resend-verification",
    status_code=202,
    summary="Resend the verification email",
    description="Sends a new link and makes older links stop working. Always returns 202, even "
    "for an unknown or already-verified email, so it can't be used to find out who has "
    "an account.",
    responses=INVALID,
)
async def resend_verification(body: ResendVerificationRequest, uow: Uow, clock: AppClock) -> None:
    await ResendVerification(uow, clock)(body.email)


# ---------------------------------------------------------------- log in, refresh, log out


@auth_router.post(
    "/login",
    summary="Log in",
    description="Returns an access token and sets the `refresh_token` cookie.",
    responses={
        **INVALID,
        401: _problem("Wrong email or password (one message for both)", "invalid_credentials"),
        403: _problem(
            "The email hasn't been verified yet; the user can resend the email",
            "email_not_verified",
        ),
    },
)
async def login(
    body: LoginRequest,
    response: Response,
    uow: Uow,
    hasher: Hasher,
    tokens: AccessTokens,
    clock: AppClock,
) -> TokenResponse:
    result = await LogIn(uow, hasher, tokens, clock)(body.email, body.password)
    _set_refresh_cookie(response, result.refresh_token)  # never in the body
    return TokenResponse(access_token=result.access_token, expires_in=result.expires_in)


@auth_router.post(
    "/refresh",
    summary="Get a new access token",
    description="Uses the `refresh_token` cookie; returns a new access token and replaces "
    "the cookie.",
    responses={
        401: _problem("Missing, expired or already-used refresh token", "invalid_refresh_token")
    },
)
async def refresh(refresh_token: RefreshCookie = None) -> TokenResponse:
    _not_implemented()


@auth_router.post(
    "/logout",
    status_code=204,
    summary="Log out",
    description="Ends the session on this device: the refresh token stops working and the "
    "cookie is cleared.",
)
async def logout(refresh_token: RefreshCookie = None) -> None:
    _not_implemented()


# ---------------------------------------------------------------- the current user


@users_router.get(
    "/me",
    summary="The logged-in user",
    responses={401: _problem("Missing or invalid access token", "unauthorized")},
)
async def me(user: AuthenticatedUser, uow: Uow) -> User:
    account = await GetMe(uow)(user.id)
    return User(
        id=account.id,
        email=account.email.value,
        first_name=account.first_name,
        last_name=account.last_name,
        email_verified=account.email_verified,
        roles=account.roles,
    )


# ---------------------------------------------------------------- public keys


@keys_router.get(
    "/.well-known/jwks.json",
    summary="Public keys for checking access tokens",
    description="Other services fetch this (and cache it) to check access tokens without "
    "calling Accounts on every request.",
)
async def jwks(request: Request) -> JwkSet:
    signing_key: SigningKey = request.app.state.signing_key
    return JwkSet.model_validate(signing_key.jwks())
