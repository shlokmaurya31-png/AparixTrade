"""Application-layer symmetric encryption for secrets stored at rest —
currently only broker credentials/tokens (domains/broker). Nothing else in
this codebase needs this: passwords are one-way hashed (core/security.py),
JWTs are signed not encrypted. SQLite has no column-level encryption, and
this needs to work identically once Postgres is swapped in, so encryption
happens here, in Python, before a secret ever reaches the DB — not relied on
the database layer.
"""

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import get_settings


class EncryptionNotConfiguredError(Exception):
    """Raised instead of silently storing a broker secret in plaintext."""


class DecryptionFailedError(Exception):
    """The stored ciphertext doesn't decrypt under the current key — e.g.
    BROKER_ENCRYPTION_KEY was rotated without re-encrypting existing rows."""


def _fernet() -> Fernet:
    # Not cached: get_settings() is itself @lru_cache'd, and tests
    # frequently swap BROKER_ENCRYPTION_KEY via monkeypatch + cache_clear().
    # A second cache here would need the same clearing discipline for no
    # real benefit — Fernet construction is cheap.
    key = get_settings().broker_encryption_key
    if not key:
        raise EncryptionNotConfiguredError(
            "BROKER_ENCRYPTION_KEY is not set. Generate one with "
            "`python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\"` "
            "and set it in apps/api/.env before connecting a broker."
        )
    return Fernet(key.encode("utf-8") if isinstance(key, str) else key)


def encrypt_secret(plaintext: str) -> str:
    return _fernet().encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt_secret(ciphertext: str) -> str:
    try:
        return _fernet().decrypt(ciphertext.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise DecryptionFailedError("Stored broker secret could not be decrypted with the current key.") from exc
