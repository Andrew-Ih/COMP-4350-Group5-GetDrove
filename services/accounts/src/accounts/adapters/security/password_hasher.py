"""The real ``PasswordHasher``: Argon2id via argon2-cffi (ADR 0020)."""

from argon2 import PasswordHasher as Argon2
from argon2.exceptions import InvalidHashError, VerificationError


class Argon2PasswordHasher:
    """Uses argon2-cffi's defaults (RFC 9106 low-memory profile: 64 MiB, 3 passes, 4 lanes).

    Each hash stores its own salt and settings, so hashes made with older settings still
    verify if the defaults change.
    """

    def __init__(self, hasher: Argon2 | None = None) -> None:
        self._hasher = hasher or Argon2()
        # Made once, so verify_dummy costs the same as a real check and no more.
        self._dummy_hash = self._hasher.hash("not a real password, for timing only")

    def hash(self, password: str) -> str:
        return self._hasher.hash(password)

    def verify(self, password_hash: str, password: str) -> bool:
        # argon2 raises on a mismatch; the port answers True or False instead.
        try:
            return self._hasher.verify(password_hash, password)
        except (VerificationError, InvalidHashError):
            return False

    def verify_dummy(self, password: str) -> None:
        self.verify(self._dummy_hash, password)
