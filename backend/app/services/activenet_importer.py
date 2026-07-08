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


ACCOUNT_FIELD_ALIASES = {
    "account_code": ["account_code", "conta", "Conta", "codigo", "codigo_conta", "numero_conta"],
    "client_name": ["client_name", "nome_cliente", "nomeCliente", "cliente", "nome", "nome_fantasia", "fantasia", "razao_social", "razao"],
    "account_name": ["account_name", "local", "nome_local", "descricao", "description", "nome_conta", "nome"],
    "partition_number": ["partition_number", "particao", "particao_pgm", "partition", "area"],
    "phone": ["phone", "telefone", "celular", "fone", "contato"],
    "email": ["email", "e_mail"],
    "document": ["document", "documento", "cpf", "cnpj"],
    "address": ["address", "endereco", "endereço", "logradouro", "rua", "localizacao", "location", "informacoes_do_local"],
    "source_client_id": ["source_client_id", "cliente_id", "clientes_id", "id_cliente"],
    "source_account_id": ["source_account_id", "conta_id", "contas_id", "id_conta", "id"],
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


@dataclass
class ActiveNetNormalizedAccount:
    account_code: str
    client_name: str
    account_name: str
    partition_number: str = "001"
    phone: str | None = None
    email: str | None = None
    document: str | None = None
    address: str | None = None
    source_client_id: str | None = None
    source_account_id: str | None = None
    raw: dict[str, Any] | None = None


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if text in {"", "---", "-", "null", "None"}:
        return None
    return re.sub(r"\s+", " ", text)


def _zfill_account(value: str | None) -> str | None:
    value = _clean(value)
    if not value:
        return None
    return value.zfill(4) if value.isdigit() else value


def _pick(row: dict[str, Any], key: str, aliases: dict[str, list[str]] = FIELD_ALIASES) -> str | None:
    for alias in aliases[key]:
        if alias in row:
            value = _clean(row.get(alias))
            if value is not None:
                return value
    lowered = {str(k).lower(): v for k, v in row.items()}
    for alias in aliases[key]:
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
        if text.isdigit() and len(text) <= 3:
            return text.zfill(3)
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

    account_code = _zfill_account(getattr(item, "account_code", None)) or _zfill_account(_pick(row, "account_code"))
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

    partition = _extract_partition(info_1, info_2, _clean(row.get("particao_pgm")), description)
    zone = _extract_zone(info_1, info_2, _clean(row.get("zona_usuario")), description)

    return ActiveNetNormalizedEvent(
        account_code=account_code,
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


def normalize_activenet_account(item) -> ActiveNetNormalizedAccount:
    row = dict(getattr(item, "row", None) or {})
    for attr in ACCOUNT_FIELD_ALIASES.keys():
        value = getattr(item, attr, None)
        if value is not None:
            row[attr] = value

    account_code = _zfill_account(getattr(item, "account_code", None)) or _zfill_account(_pick(row, "account_code", ACCOUNT_FIELD_ALIASES))
    if not account_code:
        raise ValueError("Conta Active Net sem código")

    client_name = (
        _clean(getattr(item, "client_name", None))
        or _pick(row, "client_name", ACCOUNT_FIELD_ALIASES)
        or _clean(row.get("nome_cliente"))
        or f"Conta {account_code}"
    )
    account_name = (
        _clean(getattr(item, "account_name", None))
        or _pick(row, "account_name", ACCOUNT_FIELD_ALIASES)
        or client_name
    )
    partition = _extract_partition(_clean(getattr(item, "partition_number", None)), _pick(row, "partition_number", ACCOUNT_FIELD_ALIASES)) or "001"

    return ActiveNetNormalizedAccount(
        account_code=account_code,
        client_name=client_name,
        account_name=account_name,
        partition_number=partition,
        phone=_clean(getattr(item, "phone", None)) or _pick(row, "phone", ACCOUNT_FIELD_ALIASES),
        email=_clean(getattr(item, "email", None)) or _pick(row, "email", ACCOUNT_FIELD_ALIASES),
        document=_clean(getattr(item, "document", None)) or _pick(row, "document", ACCOUNT_FIELD_ALIASES),
        address=_clean(getattr(item, "address", None)) or _pick(row, "address", ACCOUNT_FIELD_ALIASES),
        source_client_id=_clean(getattr(item, "source_client_id", None)) or _pick(row, "source_client_id", ACCOUNT_FIELD_ALIASES),
        source_account_id=_clean(getattr(item, "source_account_id", None)) or _pick(row, "source_account_id", ACCOUNT_FIELD_ALIASES),
        raw=row,
    )


def _find_client(db: Session, account: ActiveNetNormalizedAccount) -> models.Client | None:
    if account.source_client_id:
        marker = f"active_net_client_id={account.source_client_id}"
        found = db.query(models.Client).filter(models.Client.company_id == 1, models.Client.address.ilike(f"%{marker}%")).first()
        if found:
            return found

    return (
        db.query(models.Client)
        .filter(models.Client.company_id == 1)
        .filter((models.Client.trade_name == account.client_name) | (models.Client.name == account.client_name))
        .first()
    )


def upsert_activenet_account(db: Session, item) -> dict[str, Any]:
    account = normalize_activenet_account(item)
    existing_account = db.query(models.Account).filter_by(company_id=1, code=account.account_code).first()

    client = _find_client(db, account)
    if not client:
        address = account.address
        if account.source_client_id:
            address = f"{address or ''}\nactive_net_client_id={account.source_client_id}".strip()
        client = models.Client(
            company_id=1,
            name=account.client_name,
            trade_name=account.client_name,
            document=account.document,
            phone=account.phone,
            email=account.email,
            address=address,
            active=True,
        )
        db.add(client)
        db.flush()
    else:
        changed = False
        if account.client_name and client.trade_name in {"", "Conta não cadastrada", client.name}:
            client.trade_name = account.client_name
            client.name = account.client_name
            changed = True
        if account.phone and not client.phone:
            client.phone = account.phone
            changed = True
        if account.email and not client.email:
            client.email = account.email
            changed = True
        if account.document and not client.document:
            client.document = account.document
            changed = True
        if account.address and not client.address:
            client.address = account.address
            changed = True
        if changed:
            db.flush()

    if not existing_account:
        existing_account = models.Account(
            company_id=1,
            client_id=client.id,
            code=account.account_code,
            name=account.account_name or account.client_name,
            partition_number=account.partition_number or "001",
            armed=True,
            active=True,
            notes="Importado do Active Net em modo somente leitura.",
        )
        db.add(existing_account)
        db.flush()
        created = True
    else:
        existing_account.client_id = client.id
        existing_account.name = account.account_name or existing_account.name or account.client_name
        existing_account.partition_number = account.partition_number or existing_account.partition_number or "001"
        existing_account.active = True
        created = False
        db.flush()

    return {
        "created": created,
        "account_id": existing_account.id,
        "client_id": client.id,
        "account_code": existing_account.code,
        "client_name": client.trade_name,
    }


def import_activenet_accounts_batch(db: Session, accounts: list) -> dict[str, Any]:
    imported = 0
    updated = 0
    errors: list[str] = []

    for index, item in enumerate(accounts):
        try:
            result = upsert_activenet_account(db, item)
            if result.get("created"):
                imported += 1
            else:
                updated += 1
        except Exception as exc:
            db.rollback()
            errors.append(f"Conta {index + 1}: {exc}")

    db.commit()
    return {"ok": len(errors) == 0, "imported": imported, "updated": updated, "errors": errors}


def _event_client_name(event: ActiveNetNormalizedEvent) -> str | None:
    raw = event.raw or {}
    return (
        _clean(raw.get("nome_cliente"))
        or _clean(raw.get("nomeCliente"))
        or _clean(raw.get("cliente"))
        or _clean(raw.get("name"))
    )


def ensure_account_from_event(db: Session, event: ActiveNetNormalizedEvent):
    account = db.query(models.Account).filter_by(company_id=1, code=event.account_code).first()
    if account:
        # Aproveita evento real para cadastrar zona automaticamente, se vier zona/nome.
        ensure_zone_from_event(db, account, event)
        return account

    client_name = _event_client_name(event) or f"Conta {event.account_code}"
    row = event.raw or {}
    payload = type("TmpAccount", (), {})()
    payload.account_code = event.account_code
    payload.client_name = client_name
    payload.account_name = client_name
    payload.partition_number = event.partition or "001"
    payload.phone = None
    payload.email = None
    payload.document = None
    payload.address = _clean(row.get("location")) or _clean(row.get("local_de_acesso"))
    payload.source_client_id = None
    payload.source_account_id = None
    payload.row = {"source": "created_from_event", **row}
    result = upsert_activenet_account(db, payload)
    account = db.get(models.Account, result["account_id"])
    if account:
        ensure_zone_from_event(db, account, event)
    return account


def ensure_zone_from_event(db: Session, account: models.Account, event: ActiveNetNormalizedEvent):
    if not event.zone:
        return None
    exists = db.query(models.AccountZone).filter_by(account_id=account.id, zone_number=event.zone).first()
    if exists:
        return exists
    raw = event.raw or {}
    zone_name = _clean(raw.get("nome_zona_usuario")) or f"Zona {event.zone}"
    zone = models.AccountZone(account_id=account.id, zone_number=event.zone, name=zone_name, area=None, active=True)
    db.add(zone)
    db.flush()
    return zone


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
        if event.description and (exists.name.startswith("Evento Active Net") or exists.name == f"Evento {event.event_code}"):
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


def import_activenet_event(db: Session, item, protocol: str = "ACTIVENET_DB"):
    event = normalize_activenet_event(item)
    signature = activenet_signature(event, protocol)

    duplicate = (
        db.query(models.RawEvent)
        .filter(models.RawEvent.company_id == 1)
        .filter(models.RawEvent.protocol.in_(["ACTIVENET", "ACTIVENET_TABLE", "ACTIVENET_STOMP", "ACTIVENET_DB", protocol]))
        .filter(models.RawEvent.raw_payload == signature)
        .first()
    )
    if duplicate:
        return {"skipped": True, "raw_event_id": duplicate.id, "occurrence": None}

    ensure_account_from_event(db, event)
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


def import_activenet_batch(db: Session, events: list, protocol: str = "ACTIVENET_DB") -> dict[str, Any]:
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
