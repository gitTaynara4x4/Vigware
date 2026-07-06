from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.core.config import REQUIRE_RECEIVER_KEY, VIGWARE_RECEIVER_KEY
from backend.app.core.database import get_db
from backend.app.schemas.activenet import ActiveNetBatchIn, ActiveNetEventIn
from backend.app.services.activenet_importer import import_activenet_batch, import_activenet_event
from backend.app.services.websocket_manager import manager

router = APIRouter(prefix="/api/activenet", tags=["activenet"])


def check_receiver_key(x_vigware_key: str | None = Header(default=None)) -> None:
    if not REQUIRE_RECEIVER_KEY:
        return
    if not VIGWARE_RECEIVER_KEY:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="VIGWARE_RECEIVER_KEY não configurada")
    if x_vigware_key != VIGWARE_RECEIVER_KEY:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Chave do receiver inválida")


@router.post("/event")
async def receive_activenet_event(
    payload: ActiveNetEventIn,
    db: Session = Depends(get_db),
    _: None = Depends(check_receiver_key),
):
    result = import_activenet_event(db, payload, protocol="ACTIVENET_TABLE")
    await manager.broadcast({"type": "activenet_event", **result})
    return {"ok": True, **result}


@router.post("/batch")
async def receive_activenet_batch(
    payload: ActiveNetBatchIn,
    db: Session = Depends(get_db),
    _: None = Depends(check_receiver_key),
):
    result = import_activenet_batch(db, payload.events, protocol=payload.source or "ACTIVENET_TABLE")
    await manager.broadcast({"type": "activenet_batch", **result})
    return result
