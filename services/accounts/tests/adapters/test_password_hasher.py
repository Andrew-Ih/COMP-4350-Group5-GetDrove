"""Argon2PasswordHasher (#4, ADR 0020)."""

import time
from collections.abc import Callable

from accounts.adapters.security.password_hasher import Argon2PasswordHasher

PASSWORD = "correct horse battery"  # noqa: S105 (a test password)

hasher = Argon2PasswordHasher()


def test_hashes_are_argon2id_and_never_contain_the_password() -> None:
    password_hash = hasher.hash(PASSWORD)

    assert password_hash.startswith("$argon2id$")
    assert PASSWORD not in password_hash
    assert len(password_hash) <= 255  # fits users.password_hash


def test_the_same_password_hashes_differently_each_time() -> None:
    assert hasher.hash(PASSWORD) != hasher.hash(PASSWORD)


def test_the_right_password_verifies() -> None:
    assert hasher.verify(hasher.hash(PASSWORD), PASSWORD) is True


def test_a_wrong_password_doesnt_verify() -> None:
    password_hash = hasher.hash(PASSWORD)

    assert hasher.verify(password_hash, "correct horse battery!") is False
    assert hasher.verify(password_hash, "Correct horse battery") is False
    assert hasher.verify(password_hash, "") is False


def test_a_damaged_hash_doesnt_verify_or_crash() -> None:
    assert hasher.verify("not-a-hash", PASSWORD) is False
    assert hasher.verify("", PASSWORD) is False


def test_a_dummy_check_takes_about_as_long_as_a_real_one() -> None:
    """Login runs it for unknown emails, so timing doesn't reveal who has an account."""
    real_hash = hasher.hash(PASSWORD)

    def seconds(check: Callable[[], object]) -> float:
        started = time.perf_counter()
        for _ in range(5):
            check()
        return time.perf_counter() - started

    real = seconds(lambda: hasher.verify(real_hash, "wrong password"))
    dummy = seconds(lambda: hasher.verify_dummy("wrong password"))

    # Loose bounds so a busy CI machine doesn't make this flaky; skipping the hash entirely
    # would be hundreds of times faster.
    assert 0.3 < dummy / real < 3
