"""The RSA key Accounts signs access tokens with (ADR 0006, issue #91).

- Production: the private key comes from ``ACCOUNTS_JWT_PRIVATE_KEY`` (a PEM, written to
  the server's .env from GitHub Secrets on deploy). Accounts refuses to start without it.
- Local development: if it isn't set, a temporary key is generated at startup and a
  warning is logged. Tokens stop working when Accounts restarts, which is fine locally,
  and no private key is ever committed.

Only the public half is ever published (``/.well-known/jwks.json``).
"""

import base64
import hashlib
import json
import logging
from dataclasses import dataclass
from typing import Any

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

logger = logging.getLogger(__name__)

ALGORITHM = "RS256"


class SigningKeyMissingError(RuntimeError):
    pass


@dataclass(frozen=True)
class SigningKey:
    private_key: rsa.RSAPrivateKey
    kid: str

    @classmethod
    def from_pem(cls, pem: str) -> "SigningKey":
        key = serialization.load_pem_private_key(pem.encode(), password=None)
        if not isinstance(key, rsa.RSAPrivateKey) or key.key_size < 2048:
            raise ValueError("The JWT signing key must be an RSA private key of at least 2048 bits")
        return cls(private_key=key, kid=_thumbprint(key))

    @classmethod
    def generate(cls) -> "SigningKey":
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        return cls(private_key=key, kid=_thumbprint(key))

    def public_jwk(self) -> dict[str, Any]:
        """The public key in JWK form; never includes the private parts."""
        public = jwt.algorithms.RSAAlgorithm.to_jwk(self.private_key.public_key(), as_dict=True)
        return {
            "kty": "RSA",
            "kid": self.kid,
            "use": "sig",
            "alg": ALGORITHM,
            "n": public["n"],
            "e": public["e"],
        }

    def jwks(self) -> dict[str, Any]:
        return {"keys": [self.public_jwk()]}


def load_signing_key(private_key_pem: str | None, *, environment: str) -> SigningKey:
    if private_key_pem:
        return SigningKey.from_pem(private_key_pem)
    if environment == "production":
        raise SigningKeyMissingError(
            "ACCOUNTS_JWT_PRIVATE_KEY is not set; Accounts can't sign tokens in production"
        )
    logger.warning(
        "ACCOUNTS_JWT_PRIVATE_KEY is not set: using a temporary signing key. "
        "Tokens will stop working when Accounts restarts (fine for local development)."
    )
    return SigningKey.generate()


def _thumbprint(key: rsa.RSAPrivateKey) -> str:
    """RFC 7638 JWK thumbprint: a stable key ID derived from the public key."""
    public = jwt.algorithms.RSAAlgorithm.to_jwk(key.public_key(), as_dict=True)
    canonical = json.dumps(
        {"e": public["e"], "kty": "RSA", "n": public["n"]}, separators=(",", ":")
    )
    digest = hashlib.sha256(canonical.encode()).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
