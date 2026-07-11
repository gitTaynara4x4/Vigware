from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from backend.app.core.config import APP_ENV, AUTH_COOKIE_NAME, AUTH_SESSION_HOURS
from backend.app.core.database import get_db
from backend.app.schemas.auth import LoginIn
from backend.app.services import auth_service

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _set_session_cookie(response: Response, token: str, request: Request) -> None:
    response.set_cookie(
        key=AUTH_COOKIE_NAME,
        value=token,
        max_age=AUTH_SESSION_HOURS * 60 * 60,
        httponly=True,
        secure=request.url.scheme == "https" or APP_ENV.lower() in {"prod", "production"},
        samesite="lax",
        path="/",
    )


@router.post("/login")
def login(
    payload: LoginIn,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    user = auth_service.authenticate(db, payload.email, payload.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="E-mail ou senha inválidos",
        )

    token = auth_service.create_session(
        db,
        user,
        user_agent=request.headers.get("user-agent"),
        ip_address=request.client.host if request.client else None,
    )
    _set_session_cookie(response, token, request)
    return {"ok": True, "user": auth_service.serialize_user(user)}


@router.get("/me")
def me(request: Request, db: Session = Depends(get_db)):
    token = request.cookies.get(AUTH_COOKIE_NAME)
    user = auth_service.user_from_session(db, token)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sessão não autenticada")
    return {"authenticated": True, "user": auth_service.serialize_user(user)}


@router.post("/logout")
def logout(request: Request, response: Response, db: Session = Depends(get_db)):
    token = request.cookies.get(AUTH_COOKIE_NAME)
    auth_service.destroy_session(db, token)
    response.delete_cookie(AUTH_COOKIE_NAME, path="/")
    return {"ok": True}
