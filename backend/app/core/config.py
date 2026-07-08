import json
import os
from pathlib import Path
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parents[3]
ENV_PATH = ROOT_DIR / ".env"
load_dotenv(ENV_PATH)

APP_NAME = os.getenv("APP_NAME", "Vigware Cloud")
APP_ENV = os.getenv("APP_ENV", "dev")
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*")

# Segurança dos receivers/bridges.
# Produção recomendada: REQUIRE_RECEIVER_KEY=true + RECEIVER_AUTH_MODE=hmac.
REQUIRE_RECEIVER_KEY = os.getenv("REQUIRE_RECEIVER_KEY", "true").strip().lower() in {"1", "true", "yes", "sim"}
RECEIVER_AUTH_MODE = os.getenv("RECEIVER_AUTH_MODE", "hmac").strip().lower()
RECEIVER_ALLOWED_DRIFT_SECONDS = int(os.getenv("RECEIVER_ALLOWED_DRIFT_SECONDS", "300"))

# Modo antigo/simples. Mantido só para teste e compatibilidade.
VIGWARE_RECEIVER_KEY = os.getenv("VIGWARE_RECEIVER_KEY", "").strip()

# Modo correto: uma credencial por bridge/transmissor.
# Formatos aceitos:
# 1) JSON: {"activenet-matriz":"segredo"}
# 2) Texto: activenet-matriz:segredo,activenet-filial:outrosegredo
VIGWARE_BRIDGE_SECRETS_RAW = os.getenv("VIGWARE_BRIDGE_SECRETS", "").strip()

# Atalho para um único bridge, útil no EasyPanel.
VIGWARE_BRIDGE_ID = os.getenv("VIGWARE_BRIDGE_ID", "").strip()
VIGWARE_BRIDGE_SECRET = os.getenv("VIGWARE_BRIDGE_SECRET", "").strip()


def load_bridge_secrets() -> dict[str, str]:
    secrets: dict[str, str] = {}

    if VIGWARE_BRIDGE_SECRETS_RAW:
        try:
            parsed = json.loads(VIGWARE_BRIDGE_SECRETS_RAW)
            if isinstance(parsed, dict):
                secrets.update({str(k).strip(): str(v).strip() for k, v in parsed.items() if str(k).strip() and str(v).strip()})
        except json.JSONDecodeError:
            for part in VIGWARE_BRIDGE_SECRETS_RAW.split(","):
                if ":" not in part:
                    continue
                bridge_id, secret = part.split(":", 1)
                bridge_id = bridge_id.strip()
                secret = secret.strip()
                if bridge_id and secret:
                    secrets[bridge_id] = secret

    if VIGWARE_BRIDGE_ID and VIGWARE_BRIDGE_SECRET:
        secrets[VIGWARE_BRIDGE_ID] = VIGWARE_BRIDGE_SECRET

    return secrets


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
