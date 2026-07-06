from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.core.config import REQUIRE_RECEIVER_KEY, VIGWARE_RECEIVER_KEY
from backend.app.core.database import get_db
from backend.app.schemas.monitoring import ReceiverEventIn
from backend.app.schemas.activenet import ActiveNetBatchIn, ActiveNetEventIn
from backend.app.services.occurrence_service import receive_event, make_card
from backend.app.services.activenet_importer import import_activenet_batch, import_activenet_event
from backend.app.services.websocket_manager import manager

router = APIRouter(prefix="/api/receiver", tags=["receiver"])


def check_receiver_key(x_vigware_key: str | None = Header(default=None)) -> None:
    """Protege os endpoints públicos de receiver.

    Na VPS deixe REQUIRE_RECEIVER_KEY=true e VIGWARE_RECEIVER_KEY preenchido.
    Em dev local pode usar REQUIRE_RECEIVER_KEY=false.
    """
    if not REQUIRE_RECEIVER_KEY:
        return

    if not VIGWARE_RECEIVER_KEY:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="VIGWARE_RECEIVER_KEY não configurada no servidor",
        )

    if x_vigware_key != VIGWARE_RECEIVER_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Chave do receiver inválida",
        )


@router.post("/events")
async def receiver_event(
    payload: ReceiverEventIn,
    db: Session = Depends(get_db),
    _: None = Depends(check_receiver_key),
):
    raw_event, occurrence = receive_event(db, payload)
    data = {
        "ok": True,
        "raw_event_id": raw_event.id,
        "occurrence_id": occurrence.id if occurrence else None,
        "occurrence": make_card(db, occurrence) if occurrence else None,
    }
    await manager.broadcast({"type": "event_received", **data})
    return data


@router.post("/activenet")
async def receiver_activenet_event(
    payload: ActiveNetEventIn,
    db: Session = Depends(get_db),
    _: None = Depends(check_receiver_key),
):
    result = import_activenet_event(db, payload, protocol="ACTIVENET_STOMP")
    await manager.broadcast({"type": "activenet_event", **result})
    return {"ok": True, **result}


@router.post("/activenet/batch")
async def receiver_activenet_batch(
    payload: ActiveNetBatchIn,
    db: Session = Depends(get_db),
    _: None = Depends(check_receiver_key),
):
    result = import_activenet_batch(db, payload.events, protocol=payload.source or "ACTIVENET_STOMP")
    await manager.broadcast({"type": "activenet_batch", **result})
    return result
