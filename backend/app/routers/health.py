from fastapi import APIRouter
from backend.app.core.config import APP_NAME, APP_ENV

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health")
def health():
    return {"ok": True, "app": APP_NAME, "env": APP_ENV}
