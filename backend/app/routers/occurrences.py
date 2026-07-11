from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.schemas.monitoring import (
    BulkCloseIn,
    CommandIn,
    LogIn,
    ManualEventIn,
    MediaNoteIn,
    StatusIn,
    TemporaryNoteIn,
)
from backend.app.services import occurrence_service as service
from backend.app.services.websocket_manager import manager

router = APIRouter(prefix="/api/occurrences", tags=["occurrences"])


@router.get("/bulk/options")
def bulk_options(db: Session = Depends(get_db)):
    return service.bulk_close_options(db)


@router.get("/bulk/search")
def bulk_search(
    query: str | None = Query(default=None),
    event_type: str | None = Query(default=None),
    priority: str | None = Query(default=None),
    company_id: int | None = Query(default=None),
    country: str | None = Query(default=None),
    state: str | None = Query(default=None),
    city: str | None = Query(default=None),
    neighborhood: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    return service.search_bulk_close_occurrences(
        db,
        query=query,
        event_type=event_type,
        priority=priority,
        company_id=company_id,
        country=country,
        state=state,
        city=city,
        neighborhood=neighborhood,
    )


@router.post("/bulk/close")
async def bulk_close(payload: BulkCloseIn, db: Session = Depends(get_db)):
    try:
        result = service.close_occurrences_bulk(db, payload.occurrence_ids, payload.log)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    await manager.broadcast({
        "type": "occurrences_bulk_closed",
        "occurrence_ids": result["closed_ids"],
        "closed_count": result["closed_count"],
    })
    return result


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


@router.post("/{occurrence_id}/log")
async def add_log(occurrence_id: int, payload: LogIn, db: Session = Depends(get_db)):
    try:
        result = service.add_operator_log(db, occurrence_id, payload.text)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if not result:
        raise HTTPException(status_code=404, detail="Ocorrência não encontrada")
    await manager.broadcast({"type": "occurrence_log", "occurrence_id": occurrence_id})
    return result


@router.post("/{occurrence_id}/temporary-note")
async def temporary_note(occurrence_id: int, payload: TemporaryNoteIn, db: Session = Depends(get_db)):
    try:
        result = service.add_temporary_note(db, occurrence_id, payload.note, payload.providence)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if not result:
        raise HTTPException(status_code=404, detail="Ocorrência não encontrada")
    await manager.broadcast({"type": "occurrence_note", "occurrence_id": occurrence_id})
    return result


@router.post("/{occurrence_id}/manual-event")
async def manual_event(occurrence_id: int, payload: ManualEventIn, db: Session = Depends(get_db)):
    try:
        result = service.add_manual_event(db, occurrence_id, payload.event_code, payload.note)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if not result:
        raise HTTPException(status_code=404, detail="Ocorrência não encontrada")
    await manager.broadcast({"type": "manual_event", "occurrence_id": occurrence_id, "event_code": payload.event_code})
    return result


@router.post("/{occurrence_id}/media-note")
async def media_note(occurrence_id: int, payload: MediaNoteIn, db: Session = Depends(get_db)):
    try:
        result = service.add_media_note(db, occurrence_id, payload.filenames)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if not result:
        raise HTTPException(status_code=404, detail="Ocorrência não encontrada")
    await manager.broadcast({"type": "occurrence_media", "occurrence_id": occurrence_id})
    return result
