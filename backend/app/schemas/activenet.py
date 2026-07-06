from pydantic import BaseModel, Field
from typing import Any


class ActiveNetEventIn(BaseModel):
    # Campos normalizados que o bridge pode enviar.
    account_code: str | None = None
    event_code: str | None = None
    description: str | None = None
    info_1: str | None = None
    info_2: str | None = None
    date_time: str | None = None
    serial_number: str | None = None
    imei: str | None = None
    mac: str | None = None

    # Linha original da tabela/Active Net. Aceita chaves em português.
    row: dict[str, Any] | None = None


class ActiveNetBatchIn(BaseModel):
    events: list[ActiveNetEventIn] = Field(default_factory=list)
    source: str = "ACTIVENET_STOMP"


class ActiveNetImportOut(BaseModel):
    ok: bool
    imported: int
    skipped: int
    occurrence_count: int
    errors: list[str]
