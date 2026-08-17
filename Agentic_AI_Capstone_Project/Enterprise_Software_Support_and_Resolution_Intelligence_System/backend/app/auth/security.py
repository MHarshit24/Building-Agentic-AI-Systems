import hashlib
import secrets

import bcrypt

def hash_password(password: str) -> str:
    """Hash a password using bcrypt. Passwords are encoded to UTF-8 before hashing."""
    pwd_bytes = password.encode("utf-8")
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(pwd_bytes, salt)
    return hashed.decode("utf-8")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against a bcrypt hash."""
    pwd_bytes = plain_password.encode("utf-8")
    hashed_bytes = hashed_password.encode("utf-8")
    return bcrypt.checkpw(pwd_bytes, hashed_bytes)


def generate_reset_token() -> str:
    """A high-entropy, URL-safe random token for password reset links.
    Sent to the user by email; never stored (see hash_reset_token)."""
    return secrets.token_urlsafe(32)


def hash_reset_token(raw_token: str) -> str:
    """SHA-256 hex digest of a reset token, for at-rest storage. Deliberately
    not bcrypt: the token is already a high-entropy random value (unlike a
    human password), so bcrypt's slow-by-design cost adds latency with no
    security benefit here."""
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
