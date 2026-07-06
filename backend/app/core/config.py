import os
from pathlib import Path
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parents[3]
ENV_PATH = ROOT_DIR / ".env"
load_dotenv(ENV_PATH)

APP_NAME = os.getenv("APP_NAME", "Vigware Cloud")
APP_ENV = os.getenv("APP_ENV", "dev")
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*")

# Chave usada pelos bridges/receptores para enviar evento para a VPS.
# Em produção, coloque uma chave grande no EasyPanel.
VIGWARE_RECEIVER_KEY = os.getenv("VIGWARE_RECEIVER_KEY", "").strip()
REQUIRE_RECEIVER_KEY = os.getenv("REQUIRE_RECEIVER_KEY", "true").strip().lower() in {"1", "true", "yes", "sim"}

_raw_database_url = os.getenv("DATABASE_URL", "sqlite:///./vigware_dev.db")

# Normaliza URL para driver psycopg v3.
# Evita erro: ModuleNotFoundError: No module named 'psycopg2'
if _raw_database_url.startswith("postgres://"):
    DATABASE_URL = _raw_database_url.replace("postgres://", "postgresql+psycopg://", 1)
elif _raw_database_url.startswith("postgresql://") and not _raw_database_url.startswith("postgresql+psycopg://"):
    DATABASE_URL = _raw_database_url.replace("postgresql://", "postgresql+psycopg://", 1)
else:
    DATABASE_URL = _raw_database_url

FRONTEND_DIR = ROOT_DIR / "frontend"
