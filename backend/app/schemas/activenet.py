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
    source: str = "ACTIVENET_DB"


class ActiveNetAccountIn(BaseModel):
    account_code: str | None = None
    client_name: str | None = None
    account_name: str | None = None
    partition_number: str | None = None
    phone: str | None = None
    email: str | None = None
    document: str | None = None
    address: str | None = None
    source_client_id: str | int | None = None
    source_account_id: str | int | None = None
    row: dict[str, Any] | None = None


class ActiveNetAccountsBatchIn(BaseModel):
    accounts: list[ActiveNetAccountIn] = Field(default_factory=list)
    source: str = "ACTIVENET_DB"


class ActiveNetImportOut(BaseModel):
    ok: bool
    imported: int
    skipped: int
    occurrence_count: int
    errors: list[str]
