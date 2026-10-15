"""Verification token rules (#5): 24 hours, single use, only the hash is kept."""

from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from accounts.domain.errors import InvalidVerificationTokenError, VerificationTokenExpiredError
from accounts.domain.verification import TOKEN_LIFETIME, VerificationToken, hash_token

NOW = datetime(2026, 10, 15, 9, 0, tzinfo=UTC)


def test_the_saved_hash_matches_the_token_in_the_link() -> None:
    saved, token = VerificationToken.issue(uuid4(), NOW)

    assert saved.token_hash == hash_token(token)
    assert len(saved.token_hash) == 64


def test_the_token_itself_is_never_kept() -> None:
    saved, token = VerificationToken.issue(uuid4(), NOW)

    assert token not in str(asdict(saved))


def test_tokens_are_long_enough_and_unique() -> None:
    tokens = {VerificationToken.issue(uuid4(), NOW)[1] for _ in range(100)}

    assert len(tokens) == 100
    assert all(len(token) >= 43 for token in tokens)


def test_a_token_is_valid_for_24_hours() -> None:
    saved, _ = VerificationToken.issue(uuid4(), NOW)

    assert saved.expires_at == NOW + TOKEN_LIFETIME == NOW + timedelta(hours=24)


def test_a_token_can_be_used_just_before_it_expires() -> None:
    saved, _ = VerificationToken.issue(uuid4(), NOW)
    used_at = NOW + timedelta(hours=23, minutes=59)

    saved.consume(used_at)

    assert saved.consumed_at == used_at


def test_a_token_expires_at_24_hours() -> None:
    saved, _ = VerificationToken.issue(uuid4(), NOW)

    with pytest.raises(VerificationTokenExpiredError):
        saved.consume(NOW + timedelta(hours=24))
    assert saved.consumed_at is None


def test_a_token_can_only_be_used_once() -> None:
    saved, _ = VerificationToken.issue(uuid4(), NOW)
    saved.consume(NOW + timedelta(minutes=5))

    with pytest.raises(InvalidVerificationTokenError):
        saved.consume(NOW + timedelta(minutes=6))


def test_a_used_and_expired_token_says_it_was_used() -> None:
    saved, _ = VerificationToken.issue(uuid4(), NOW)
    saved.consume(NOW + timedelta(minutes=5))

    with pytest.raises(InvalidVerificationTokenError):
        saved.consume(NOW + timedelta(days=3))


def test_errors_match_the_contract() -> None:
    assert (InvalidVerificationTokenError.status, InvalidVerificationTokenError.code) == (
        400,
        "invalid_token",
    )
    assert (VerificationTokenExpiredError.status, VerificationTokenExpiredError.code) == (
        410,
        "token_expired",
    )
