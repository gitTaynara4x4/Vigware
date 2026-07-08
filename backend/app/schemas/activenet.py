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


class ActiveNetContactIn(BaseModel):
    name: str | None = None
    phone: str | None = None
    function: str | None = None
    priority: int | None = None
    row: dict[str, Any] | None = None


class ActiveNetZoneIn(BaseModel):
    zone_number: str | None = None
    name: str | None = None
    area: str | None = None
    row: dict[str, Any] | None = None


class ActiveNetAccountIn(BaseModel):
    account_code: str | None = None
    client_name: str | None = None
    account_name: str | None = None
    partition_number: str | None = None
    phone: str | None = None
    email: str | None = None
    document: str | None = None
    address: str | None = None
    notes: str | None = None
    protocol_note: str | None = None
    source_owner_id: str | int | None = None
    contacts: list[ActiveNetContactIn] = Field(default_factory=list)
    zones: list[ActiveNetZoneIn] = Field(default_factory=list)
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
