from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from backend.app import models
from backend.app.schemas.monitoring import ReceiverEventIn
from backend.app.services.occurrence_service import receive_event, make_card


FIELD_ALIASES = {
    "account_code": ["Conta", "conta", "account", "accountCode", "account_code", "codigoConta", "codigo_conta"],
    "event_code": ["Evento", "evento", "event", "eventCode", "event_code", "code", "codigoEvento", "codigo_evento"],
    "description": ["Descrição", "Descricao", "description", "descricao", "desc", "mensagem"],
    "info_1": ["Informação 1", "Informacao 1", "info1", "info_1", "information1", "informacao1"],
    "info_2": ["Informação 2", "Informacao 2", "info2", "info_2", "information2", "informacao2"],
    "date_time": ["Data e hora", "dataHora", "dateTime", "date_time", "datetime", "createdAt", "data"],
    "serial_number": ["Número de série", "Numero de serie", "serial", "serialNumber", "numeroSerie", "numero_serie"],
    "imei": ["IMEI", "imei"],
    "mac": ["MAC", "mac"],
}


@dataclass
class ActiveNetNormalizedEvent:
    account_code: str
    event_code: str
    description: str | None = None
    info_1: str | None = None
    info_2: str | None = None
    date_time: str | None = None
    serial_number: str | None = None
    imei: str | None = None
    mac: str | None = None
    partition: str | None = None
    zone: str | None = None
    raw: dict[str, Any] | None = None


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if text in {"", "---", "-", "null", "None"}:
        return None
    return re.sub(r"\s+", " ", text)


def _pick(row: dict[str, Any], key: str) -> str | None:
    for alias in FIELD_ALIASES[key]:
        if alias in row:
            value = _clean(row.get(alias))
            if value is not None:
                return value
    lowered = {str(k).lower(): v for k, v in row.items()}
    for alias in FIELD_ALIASES[key]:
        value = _clean(lowered.get(alias.lower()))
        if value is not None:
            return value
    return None


def _extract_partition(*texts: str | None) -> str | None:
    for text in texts:
        if not text:
            continue
        match = re.search(r"parti[cç][aã]o\s*0*(\d+)", text, flags=re.I)
        if match:
            return match.group(1).zfill(3)
    return None


def _extract_zone(*texts: str | None) -> str | None:
    for text in texts:
        if not text:
            continue
        match = re.search(r"zona\s*0*(\d+)", text, flags=re.I)
        if match:
            return match.group(1).zfill(3)
    return None


def normalize_activenet_event(item) -> ActiveNetNormalizedEvent:
    row = dict(getattr(item, "row", None) or {})

    # Campos normalizados têm prioridade sobre row.
    for attr in FIELD_ALIASES.keys():
        value = getattr(item, attr, None)
        if value is not None:
            row[attr] = value

    account_code = _clean(getattr(item, "account_code", None)) or _pick(row, "account_code")
    event_code = _clean(getattr(item, "event_code", None)) or _pick(row, "event_code")

    if not account_code:
        raise ValueError("Evento Active Net sem conta")
    if not event_code:
        raise ValueError(f"Evento Active Net da conta {account_code} sem código")

    description = _clean(getattr(item, "description", None)) or _pick(row, "description")
    info_1 = _clean(getattr(item, "info_1", None)) or _pick(row, "info_1")
    info_2 = _clean(getattr(item, "info_2", None)) or _pick(row, "info_2")
    date_time = _clean(getattr(item, "date_time", None)) or _pick(row, "date_time")
    serial_number = _clean(getattr(item, "serial_number", None)) or _pick(row, "serial_number")
    imei = _clean(getattr(item, "imei", None)) or _pick(row, "imei")
    mac = _clean(getattr(item, "mac", None)) or _pick(row, "mac")

    partition = _extract_partition(info_1, info_2, description)
    zone = _extract_zone(info_1, info_2, description)

    return ActiveNetNormalizedEvent(
        account_code=account_code.zfill(4) if account_code.isdigit() else account_code,
        event_code=event_code,
        description=description,
        info_1=info_1,
        info_2=info_2,
        date_time=date_time,
        serial_number=serial_number,
        imei=imei,
        mac=mac,
        partition=partition,
        zone=zone,
        raw=row,
    )


def activenet_signature(event: ActiveNetNormalizedEvent, protocol: str) -> str:
    # Quando o evento vem do PostgreSQL local do Active Net, o id original da linha
    # garante idempotência perfeita sem precisar escrever nada no banco do Active Net.
    source_event_id = ""
    if isinstance(event.raw, dict):
        source_event_id = str(event.raw.get("id") or event.raw.get("source_event_id") or "")

    parts = [
        protocol,
        source_event_id,
        event.account_code or "",
        event.event_code or "",
        event.date_time or "",
        event.serial_number or "",
        event.imei or "",
        event.mac or "",
        event.info_1 or "",
        event.info_2 or "",
    ]
    return "|".join(parts)


def ensure_activenet_event_code(db: Session, event: ActiveNetNormalizedEvent) -> None:
    exists = db.query(models.EventCode).filter_by(code=event.event_code).first()
    if exists:
        # Se o cadastro veio sem nome bom, melhora com a descrição real do Active Net.
        if event.description and exists.name.startswith("Evento Active Net"):
            exists.name = event.description
        return

    # Padrão seguro: eventos desconhecidos entram como histórico, sem abrir ocorrência.
    # Depois você decide quais códigos viram ocorrência crítica.
    db.add(
        models.EventCode(
            code=event.event_code,
            name=event.description or f"Evento Active Net {event.event_code}",
            event_type="activenet",
            priority="low",
            open_occurrence=False,
            sound=None,
        )
    )
    db.flush()


def import_activenet_event(db: Session, item, protocol: str = "ACTIVENET_STOMP"):
    event = normalize_activenet_event(item)
    signature = activenet_signature(event, protocol)

    duplicate = (
        db.query(models.RawEvent)
        .filter(models.RawEvent.company_id == 1)
        .filter(models.RawEvent.protocol.in_(["ACTIVENET", "ACTIVENET_TABLE", "ACTIVENET_STOMP", protocol]))
        .filter(models.RawEvent.raw_payload == signature)
        .first()
    )
    if duplicate:
        return {"skipped": True, "raw_event_id": duplicate.id, "occurrence": None}

    ensure_activenet_event_code(db, event)

    payload = ReceiverEventIn(
        account_code=event.account_code,
        event_code=event.event_code,
        partition=event.partition or "001",
        zone=event.zone,
        raw=signature,
        protocol=protocol,
    )

    raw_event, occurrence = receive_event(db, payload)

    # Complementa a timeline com a descrição original do Active Net.
    if occurrence and event.description:
        timeline = models.OccurrenceTimeline(
            occurrence_id=occurrence.id,
            type="ACTIVENET",
            title=f"Active Net: {event.description}",
            description=(
                f"Conta {event.account_code} | Evento {event.event_code}"
                f" | Info 1: {event.info_1 or '-'} | Info 2: {event.info_2 or '-'}"
                f" | Data/hora Active Net: {event.date_time or '-'}"
            ),
            event_code=event.event_code,
        )
        db.add(timeline)
        db.commit()
        db.refresh(occurrence)

    return {
        "skipped": False,
        "raw_event_id": raw_event.id,
        "occurrence": make_card(db, occurrence) if occurrence else None,
    }


def import_activenet_batch(db: Session, events: list, protocol: str = "ACTIVENET_STOMP") -> dict[str, Any]:
    imported = 0
    skipped = 0
    occurrences = []
    errors: list[str] = []

    for index, item in enumerate(events):
        try:
            result = import_activenet_event(db, item, protocol=protocol)
            if result.get("skipped"):
                skipped += 1
            else:
                imported += 1
            if result.get("occurrence"):
                occurrences.append(result["occurrence"])
        except Exception as exc:
            db.rollback()
            errors.append(f"Linha {index + 1}: {exc}")

    return {
        "ok": len(errors) == 0,
        "imported": imported,
        "skipped": skipped,
        "occurrences": occurrences,
        "occurrence_count": len(occurrences),
        "errors": errors,
    }
