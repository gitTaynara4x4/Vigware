from pydantic import BaseModel
from typing import Any


class ReceiverEventIn(BaseModel):
    account_code: str = "0594"
    event_code: str = "E130"
    partition: str | None = "001"
    zone: str | None = "005"
    raw: str | None = None
    protocol: str = "HTTP_SIMULATED"


class StatusIn(BaseModel):
    status: str
    note: str | None = None


class CommandIn(BaseModel):
    command: str
    partition: str | None = None
    note: str | None = None


class LogIn(BaseModel):
    text: str


class TemporaryNoteIn(BaseModel):
    note: str | None = None
    providence: str | None = None


class ManualEventIn(BaseModel):
    event_code: str
    note: str | None = None


class MediaNoteIn(BaseModel):
    filenames: str


class BulkCloseIn(BaseModel):
    occurrence_ids: list[int]
    log: str


class TimelineItemOut(BaseModel):
    id: int
    type: str
    title: str
    description: str | None
    event_code: str | None
    created_at: str


class OccurrenceCardOut(BaseModel):
    id: int
    account_code: str
    client_name: str
    account_name: str
    partition_number: str | None
    zone_number: str | None
    zone_name: str | None
    event_code: str
    description: str
    priority: str
    status: str
    status_label: str
    event_count: int
    created_at: str
    updated_at: str


class OccurrenceDetailOut(BaseModel):
    occurrence: dict[str, Any]
    account: dict[str, Any] | None
    client: dict[str, Any] | None
    contacts: list[dict[str, Any]]
    zones: list[dict[str, Any]]
    timeline: list[dict[str, Any]]
    patrol_cars: list[dict[str, Any]]

