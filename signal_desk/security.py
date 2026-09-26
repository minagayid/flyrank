from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from signal_desk.config import SESSION_TTL_SECONDS
from signal_desk.database import reader, transaction

PBKDF2_ITERATIONS = 240_000


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _stamp(value: datetime) -> str:
    return value.isoformat(timespec="seconds")


def password_digest(password: str, salt_hex: str) -> str:
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), PBKDF2_ITERATIONS
    )
    return digest.hex()


def create_user(username: str, password: str) -> None:
    salt = secrets.token_hex(16)
    with transaction() as connection:
        connection.execute(
            "INSERT INTO users(username, password_hash, salt, created_at) VALUES (?, ?, ?, ?)",
            (username, password_digest(password, salt), salt, _stamp(_now())),
        )


def login(username: str, password: str) -> dict[str, Any] | None:
    with reader() as connection:
        row = connection.execute(
            "SELECT id, username, password_hash, salt FROM users WHERE username = ?",
            (username,),
        ).fetchone()
    if row is None:
        # Run the same KDF for unknown usernames to reduce username timing signals.
        password_digest(password, "00" * 16)
        return None
    candidate = password_digest(password, row["salt"])
    if not hmac.compare_digest(candidate, row["password_hash"]):
        return None

    token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(token.encode("ascii")).hexdigest()
    expires_at = _stamp(_now() + timedelta(seconds=SESSION_TTL_SECONDS))
    with transaction() as connection:
        connection.execute(
            "INSERT INTO sessions(token_hash, user_id, expires_at, created_at) VALUES (?, ?, ?, ?)",
            (token_hash, row["id"], expires_at, _stamp(_now())),
        )
    return {"access_token": token, "token_type": "bearer", "expires_at": expires_at, "user": {"id": row["id"], "username": row["username"]}}


def authenticate(token: str | None) -> dict[str, Any] | None:
    if not token or len(token) > 512:
        return None
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    with reader() as connection:
        row = connection.execute(
            """SELECT users.id, users.username, sessions.expires_at
               FROM sessions JOIN users ON users.id = sessions.user_id
               WHERE sessions.token_hash = ?""",
            (token_hash,),
        ).fetchone()
    if row is None or row["expires_at"] <= _stamp(_now()):
        return None
    return {"id": row["id"], "username": row["username"]}


def revoke(token: str | None) -> None:
    if not token:
        return
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    with transaction() as connection:
        connection.execute("DELETE FROM sessions WHERE token_hash = ?", (token_hash,))
