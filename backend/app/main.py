from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi import Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from backend.app.core.config import APP_NAME, CORS_ORIGINS, FRONTEND_DIR, AUTH_COOKIE_NAME
from backend.app.core.database import Base, engine, SessionLocal
from backend.app.services.seed import ensure_seed
from backend.app.services.auth_service import ensure_default_auth, user_from_session
from backend.app.routers import health, monitoring, occurrences, receiver, demo, activenet, auth

# Importa models para o Base.metadata enxergar todas as tabelas.
from backend.app import models  # noqa: F401

app = FastAPI(title=APP_NAME)

origins = ["*"] if CORS_ORIGINS == "*" else [x.strip() for x in CORS_ORIGINS.split(",") if x.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


PUBLIC_API_PREFIXES = (
    "/api/auth",
    "/api/health",
    "/api/receiver",
    "/api/activenet",
)


@app.middleware("http")
async def protect_panel_api(request: Request, call_next):
    path = request.url.path
    is_panel_api = path.startswith("/api/") and not path.startswith(PUBLIC_API_PREFIXES)

    if is_panel_api and request.method != "OPTIONS":
        db = SessionLocal()
        try:
            user = user_from_session(db, request.cookies.get(AUTH_COOKIE_NAME))
            if not user:
                return JSONResponse(
                    status_code=401,
                    content={"detail": "Sessão expirada ou não autenticada"},
                )
            request.state.user = user
        finally:
            db.close()

    return await call_next(request)


@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        ensure_seed(db)
        ensure_default_auth(db)
    finally:
        db.close()


app.include_router(health.router)
app.include_router(auth.router)
app.include_router(monitoring.router)
app.include_router(occurrences.router)
app.include_router(receiver.router)
app.include_router(demo.router)
app.include_router(activenet.router)

app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")


@app.get("/")
def index():
    return FileResponse(FRONTEND_DIR / "index.html")
