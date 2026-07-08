from __future__ import annotations

import hashlib
import hmac
import re
import time
from datetime import datetime, timedelta

from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app import models
from backend.app.core.config import (
    RECEIVER_ALLOWED_DRIFT_SECONDS,
    RECEIVER_AUTH_MODE,
    REQUIRE_RECEIVER_KEY,
    VIGWARE_RECEIVER_KEY,
    load_bridge_secrets,
)
from backend.app.core.database import get_db

_NONCE_RE = re.compile(r"^[A-Za-z0-9_.:-]{8,120}$")


def _unauthorized(detail: str) -> None:
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail)


def _check_simple_key(x_vigware_key: str | None) -> None:
    if not VIGWARE_RECEIVER_KEY:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="VIGWARE_RECEIVER_KEY não configurada no servidor",
        )
    if not hmac.compare_digest(str(x_vigware_key or ""), VIGWARE_RECEIVER_KEY):
        _unauthorized("Chave do receiver inválida")


def _check_replay_nonce(db: Session, bridge_id: str, nonce: str) -> None:
    now = datetime.utcnow()

    # Limpeza simples para não crescer infinito.
    db.query(models.ReceiverNonce).filter(models.ReceiverNonce.expires_at < now).delete(synchronize_session=False)

    existing = (
        db.query(models.ReceiverNonce)
        .filter(models.ReceiverNonce.bridge_id == bridge_id, models.ReceiverNonce.nonce == nonce)
        .first()
    )
    if existing:
        _unauthorized("Nonce já usado. Possível replay bloqueado.")

    db.add(
        models.ReceiverNonce(
            bridge_id=bridge_id,
            nonce=nonce,
            expires_at=now + timedelta(seconds=RECEIVER_ALLOWED_DRIFT_SECONDS),
        )
    )
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        _unauthorized("Nonce já usado. Possível replay bloqueado.")


async def verify_receiver_request(
    request: Request,
    db: Session = Depends(get_db),
    x_vigware_key: str | None = Header(default=None, alias="X-Vigware-Key"),
    x_vigware_bridge_id: str | None = Header(default=None, alias="X-Vigware-Bridge-Id"),
    x_vigware_timestamp: str | None = Header(default=None, alias="X-Vigware-Timestamp"),
    x_vigware_nonce: str | None = Header(default=None, alias="X-Vigware-Nonce"),
    x_vigware_signature: str | None = Header(default=None, alias="X-Vigware-Signature"),
) -> dict[str, str] | None:
    """Protege endpoints públicos de evento.

    Modo recomendado em produção: HMAC.
    Assinatura:
        sha256=HMAC(secret, f"{timestamp}.{nonce}." + raw_body)

    Isso evita endpoint aberto, evento falso simples e replay básico.
    """
    if not REQUIRE_RECEIVER_KEY:
        return None

    mode = RECEIVER_AUTH_MODE.lower().strip()
    if mode in {"simple", "api_key", "key"}:
        _check_simple_key(x_vigware_key)
        return {"auth_mode": "simple"}

    if mode != "hmac":
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"RECEIVER_AUTH_MODE inválido: {RECEIVER_AUTH_MODE}",
        )

    bridge_id = str(x_vigware_bridge_id or "").strip()
    timestamp_text = str(x_vigware_timestamp or "").strip()
    nonce = str(x_vigware_nonce or "").strip()
    signature = str(x_vigware_signature or "").strip()

    if not bridge_id:
        _unauthorized("Header X-Vigware-Bridge-Id ausente")
    if not timestamp_text:
        _unauthorized("Header X-Vigware-Timestamp ausente")
    if not nonce or not _NONCE_RE.match(nonce):
        _unauthorized("Header X-Vigware-Nonce inválido")
    if not signature.startswith("sha256="):
        _unauthorized("Header X-Vigware-Signature inválido")

    try:
        timestamp = int(timestamp_text)
    except ValueError:
        _unauthorized("Timestamp inválido")

    now = int(time.time())
    if abs(now - timestamp) > RECEIVER_ALLOWED_DRIFT_SECONDS:
        _unauthorized("Timestamp fora da janela permitida")

    secrets = load_bridge_secrets()
    secret = secrets.get(bridge_id)
    if not secret:
        _unauthorized("Bridge não autorizado")

    body = await request.body()
    message = timestamp_text.encode("utf-8") + b"." + nonce.encode("utf-8") + b"." + body
    expected = "sha256=" + hmac.new(secret.encode("utf-8"), message, hashlib.sha256).hexdigest()

    if not hmac.compare_digest(expected, signature):
        _unauthorized("Assinatura HMAC inválida")

    _check_replay_nonce(db, bridge_id, nonce)

    return {"auth_mode": "hmac", "bridge_id": bridge_id}
