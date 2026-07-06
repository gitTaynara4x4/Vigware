from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from backend.app.core.database import get_db
from backend.app.schemas.monitoring import ReceiverEventIn
from backend.app.services.seed import ensure_seed
from backend.app.services.occurrence_service import receive_event, make_card, reset_demo
from backend.app.services.websocket_manager import manager

router = APIRouter(prefix="/api/demo", tags=["demo"])


@router.post("/seed")
async def create_seed(db: Session = Depends(get_db)):
    ensure_seed(db)
    await manager.broadcast({"type": "seed_created"})
    return {"ok": True, "message": "Demo criada/confirmada"}


@router.post("/reset")
async def reset(db: Session = Depends(get_db)):
    reset_demo(db)
    ensure_seed(db)
    await manager.broadcast({"type": "demo_reset"})
    return {"ok": True, "message": "Ocorrências demo apagadas"}


@router.post("/simulate/e130")
async def simulate_e130(db: Session = Depends(get_db)):
    payload = ReceiverEventIn(account_code="0594", event_code="E130", partition="001", zone="005", raw="SIMULATED:E130:0594:001:005")
    raw_event, occurrence = receive_event(db, payload)
    data = {"ok": True, "raw_event_id": raw_event.id, "occurrence_id": occurrence.id if occurrence else None, "occurrence": make_card(db, occurrence) if occurrence else None}
    await manager.broadcast({"type": "event_received", **data})
    return data


@router.post("/simulate/e301")
async def simulate_e301(db: Session = Depends(get_db)):
    payload = ReceiverEventIn(account_code="0594", event_code="E301", partition="001", zone="000", raw="SIMULATED:E301:0594")
    raw_event, occurrence = receive_event(db, payload)
    data = {"ok": True, "raw_event_id": raw_event.id, "occurrence_id": occurrence.id if occurrence else None, "occurrence": make_card(db, occurrence) if occurrence else None}
    await manager.broadcast({"type": "event_received", **data})
    return data
