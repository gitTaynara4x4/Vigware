from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.app.core.config import APP_NAME, CORS_ORIGINS, FRONTEND_DIR
from backend.app.core.database import Base, engine, SessionLocal
from backend.app.services.seed import ensure_seed
from backend.app.routers import health, monitoring, occurrences, receiver, demo, activenet

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


@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        ensure_seed(db)
    finally:
        db.close()


app.include_router(health.router)
app.include_router(monitoring.router)
app.include_router(occurrences.router)
app.include_router(receiver.router)
app.include_router(demo.router)
app.include_router(activenet.router)

app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")


@app.get("/")
def index():
    return FileResponse(FRONTEND_DIR / "index.html")
