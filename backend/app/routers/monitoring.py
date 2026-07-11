from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session
from backend.app.core.database import get_db, SessionLocal
from backend.app.services.occurrence_service import monitoring_board, ACTIVE_STATUSES, STATUS_LABELS
from backend.app.services.websocket_manager import manager
from backend.app.core.config import AUTH_COOKIE_NAME
from backend.app.services.auth_service import user_from_session

router = APIRouter(tags=["monitoring"])


@router.get("/api/monitoring")
def get_monitoring(db: Session = Depends(get_db)):
    return {
        "columns": monitoring_board(db),
        "active_statuses": ACTIVE_STATUSES,
        "status_labels": STATUS_LABELS,
    }


@router.websocket("/ws/monitoring")
async def monitoring_ws(websocket: WebSocket):
    db = SessionLocal()
    try:
        user = user_from_session(db, websocket.cookies.get(AUTH_COOKIE_NAME), touch=False)
    finally:
        db.close()

    if not user:
        await websocket.close(code=4401)
        return

    await manager.connect(websocket)
    try:
        await websocket.send_json({"type": "connected", "message": "Vigware WS conectado"})
        while True:
            # Mantém conexão viva e aceita ping do front.
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:
        manager.disconnect(websocket)
