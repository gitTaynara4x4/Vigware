from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from backend.app.core.database import get_db
from backend.app.schemas.monitoring import StatusIn, CommandIn
from backend.app.services import occurrence_service as service
from backend.app.services.websocket_manager import manager

router = APIRouter(prefix="/api/occurrences", tags=["occurrences"])


@router.get("/{occurrence_id}")
def detail(occurrence_id: int, db: Session = Depends(get_db)):
    data = service.get_detail(db, occurrence_id)
    if not data:
        raise HTTPException(status_code=404, detail="Ocorrência não encontrada")
    return data


@router.get("/{occurrence_id}/timeline")
def timeline(occurrence_id: int, db: Session = Depends(get_db)):
    data = service.get_detail(db, occurrence_id)
    if not data:
        raise HTTPException(status_code=404, detail="Ocorrência não encontrada")
    return {"items": data["timeline"]}


@router.post("/{occurrence_id}/watch")
async def watch(occurrence_id: int, db: Session = Depends(get_db)):
    occ = service.watch_occurrence(db, occurrence_id)
    if not occ:
        raise HTTPException(status_code=404, detail="Ocorrência não encontrada")
    await manager.broadcast({"type": "occurrence_watch", "occurrence_id": occurrence_id})
    return {"ok": True, "occurrence": service.make_card(db, occ)}


@router.post("/{occurrence_id}/unwatch")
async def unwatch(occurrence_id: int, db: Session = Depends(get_db)):
    service.unwatch_occurrence(db, occurrence_id)
    await manager.broadcast({"type": "occurrence_unwatch", "occurrence_id": occurrence_id})
    return {"ok": True}


@router.post("/{occurrence_id}/status")
async def status(occurrence_id: int, payload: StatusIn, db: Session = Depends(get_db)):
    try:
        occ = service.update_status(db, occurrence_id, payload.status, payload.note)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if not occ:
        raise HTTPException(status_code=404, detail="Ocorrência não encontrada")
    await manager.broadcast({"type": "status_changed", "occurrence_id": occurrence_id, "status": occ.status})
    return {"ok": True, "occurrence": service.make_card(db, occ)}


@router.post("/{occurrence_id}/command")
async def command(occurrence_id: int, payload: CommandIn, db: Session = Depends(get_db)):
    try:
        result = service.request_account_command(db, occurrence_id, payload.command, payload.partition, payload.note)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if not result:
        raise HTTPException(status_code=404, detail="Ocorrência não encontrada")
    await manager.broadcast({"type": "command_requested", "occurrence_id": occurrence_id, "command": result["command"]})
    return result
