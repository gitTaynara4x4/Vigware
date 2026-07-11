from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from backend.app import models
from backend.app.core.config import (
    AUTH_SESSION_HOURS,
    VIGWARE_ADMIN_EMAIL,
    VIGWARE_ADMIN_PASSWORD,
)

PBKDF2_ITERATIONS = 390_000


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _b64decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def hash_password(password: str) -> str:
    if not password:
        raise ValueError("A senha não pode ficar vazia")
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        PBKDF2_ITERATIONS,
    )
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${_b64encode(salt)}${_b64encode(digest)}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, iterations_raw, salt_raw, digest_raw = encoded.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        iterations = int(iterations_raw)
        salt = _b64decode(salt_raw)
        expected = _b64decode(digest_raw)
    except (ValueError, TypeError):
        return False

    calculated = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        iterations,
    )
    return hmac.compare_digest(calculated, expected)


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def serialize_user(user: models.User) -> dict:
    return {
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "role": user.role,
        "company_id": user.company_id,
    }


def ensure_default_auth(db: Session) -> None:
    """Cria a credencial inicial sem alterar usuários ou senhas existentes."""
    email = VIGWARE_ADMIN_EMAIL.strip().lower()
    user = db.query(models.User).filter(models.User.email == email).first()

    if not user:
        user = db.get(models.User, 1)
        if user and email and user.email.lower() != email:
            email_in_use = db.query(models.User).filter(models.User.email == email).first()
            if not email_in_use:
                user.email = email
                db.flush()

    if not user:
        return

    credential = (
        db.query(models.UserCredential)
        .filter(models.UserCredential.user_id == user.id)
        .first()
    )
    if credential:
        return

    db.add(
        models.UserCredential(
            user_id=user.id,
            password_hash=hash_password(VIGWARE_ADMIN_PASSWORD),
        )
    )
    db.commit()


def authenticate(db: Session, email: str, password: str) -> models.User | None:
    normalized_email = (email or "").strip().lower()
    user = (
        db.query(models.User)
        .filter(models.User.email == normalized_email, models.User.active.is_(True))
        .first()
    )
    if not user:
        return None

    credential = (
        db.query(models.UserCredential)
        .filter(models.UserCredential.user_id == user.id)
        .first()
    )
    if not credential or not verify_password(password or "", credential.password_hash):
        return None

    return user


def create_session(
    db: Session,
    user: models.User,
    *,
    user_agent: str | None = None,
    ip_address: str | None = None,
) -> str:
    now = datetime.utcnow()
    db.query(models.UserSession).filter(models.UserSession.expires_at <= now).delete(
        synchronize_session=False
    )

    raw_token = secrets.token_urlsafe(48)
    db.add(
        models.UserSession(
            user_id=user.id,
            token_hash=_token_hash(raw_token),
            user_agent=(user_agent or "")[:300] or None,
            ip_address=(ip_address or "")[:80] or None,
            created_at=now,
            last_seen_at=now,
            expires_at=now + timedelta(hours=AUTH_SESSION_HOURS),
        )
    )
    db.commit()
    return raw_token


def user_from_session(
    db: Session,
    raw_token: str | None,
    *,
    touch: bool = True,
) -> models.User | None:
    if not raw_token:
        return None

    now = datetime.utcnow()
    session = (
        db.query(models.UserSession)
        .filter(models.UserSession.token_hash == _token_hash(raw_token))
        .first()
    )
    if not session:
        return None

    if session.expires_at <= now:
        db.delete(session)
        db.commit()
        return None

    user = db.get(models.User, session.user_id)
    if not user or not user.active:
        db.delete(session)
        db.commit()
        return None

    if touch and (not session.last_seen_at or now - session.last_seen_at >= timedelta(minutes=5)):
        session.last_seen_at = now
        db.commit()

    return user


def destroy_session(db: Session, raw_token: str | None) -> None:
    if not raw_token:
        return
    session = (
        db.query(models.UserSession)
        .filter(models.UserSession.token_hash == _token_hash(raw_token))
        .first()
    )
    if session:
        db.delete(session)
        db.commit()
