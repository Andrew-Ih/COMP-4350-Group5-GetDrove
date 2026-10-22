"""Refresh token rules (#6) and the login errors."""

from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from accounts.domain.errors import (
    EmailNotVerifiedError,
    InvalidCredentialsError,
    InvalidRefreshTokenError,
)
from accounts.domain.refresh_token import REFRESH_TOKEN_LIFETIME, RefreshToken
from accounts.domain.verification import hash_token

NOW = datetime(2026, 10, 16, 9, 0, tzinfo=UTC)


def test_the_saved_hash_matches_the_token_in_the_cookie() -> None:
    saved, token = RefreshToken.issue(uuid4(), NOW)

    assert saved.token_hash == hash_token(token)
    assert len(token) >= 43


def test_the_token_itself_is_never_kept() -> None:
    saved, token = RefreshToken.issue(uuid4(), NOW)

    assert token not in str(asdict(saved))


def test_tokens_are_unique() -> None:
    assert len({RefreshToken.issue(uuid4(), NOW)[1] for _ in range(100)}) == 100


def test_a_token_lasts_7_days() -> None:
    saved, _ = RefreshToken.issue(uuid4(), NOW)

    assert saved.expires_at == NOW + REFRESH_TOKEN_LIFETIME == NOW + timedelta(days=7)
    assert saved.revoked_at is None
    assert saved.replaced_by_id is None


def test_a_token_is_active_until_it_expires() -> None:
    saved, _ = RefreshToken.issue(uuid4(), NOW)

    assert saved.is_active(NOW + timedelta(days=6, hours=23)) is True
    assert saved.is_active(NOW + timedelta(days=7)) is False


def test_a_revoked_token_is_not_active() -> None:
    saved, _ = RefreshToken.issue(uuid4(), NOW)
    saved.revoked_at = NOW + timedelta(minutes=1)

    assert saved.is_active(NOW + timedelta(minutes=2)) is False


def test_login_errors_match_the_contract() -> None:
    assert (InvalidCredentialsError.status, InvalidCredentialsError.code) == (
        401,
        "invalid_credentials",
    )
    assert (EmailNotVerifiedError.status, EmailNotVerifiedError.code) == (
        403,
        "email_not_verified",
    )


def test_rotating_swaps_in_a_new_token_and_records_it() -> None:
    old, old_cookie = RefreshToken.issue(uuid4(), NOW)
    later = NOW + timedelta(hours=1)

    new, new_cookie = old.rotate(later)

    assert new.user_id == old.user_id
    assert new.token_hash == hash_token(new_cookie)
    assert new_cookie != old_cookie
    assert new.expires_at == later + timedelta(days=7)  # a fresh 7 days
    assert new.is_active(later)
    assert old.revoked_at == later
    assert old.replaced_by_id == new.id
    assert not old.is_active(later)


def test_revoking_stops_a_token_and_keeps_the_first_time() -> None:
    token, _ = RefreshToken.issue(uuid4(), NOW)

    token.revoke(NOW + timedelta(minutes=5))
    token.revoke(NOW + timedelta(minutes=9))

    assert token.revoked_at == NOW + timedelta(minutes=5)
    assert not token.is_active(NOW + timedelta(minutes=10))


def test_invalid_refresh_token_matches_the_contract() -> None:
    assert (InvalidRefreshTokenError.status, InvalidRefreshTokenError.code) == (
        401,
        "invalid_refresh_token",
    )
