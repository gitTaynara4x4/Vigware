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
    "notes": ["notes", "observacoes", "observacao", "informacoes_do_local", "informações_do_local"],
    "protocol_note": ["protocol_note", "protocolo", "regras_do_local", "como_atuar", "procedimento"],
    "source_owner_id": ["source_owner_id", "dono_cliente_id", "owner_id"],
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
    notes: str | None = None
    protocol_note: str | None = None
    contacts: list[dict[str, Any]] | None = None
    zones: list[dict[str, Any]] | None = None
    source_owner_id: str | None = None
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


def _norm_text(value: str | None) -> str:
    text = (value or "").lower()
    return (
        text.replace("ã", "a")
        .replace("á", "a")
        .replace("à", "a")
        .replace("â", "a")
        .replace("é", "e")
        .replace("ê", "e")
        .replace("í", "i")
        .replace("ó", "o")
        .replace("ô", "o")
        .replace("õ", "o")
        .replace("ú", "u")
        .replace("ç", "c")
    )


def classify_active_net_event(code: str | None, description: str | None) -> dict[str, Any]:
    c = (code or "").upper().strip()
    d = _norm_text(description)
    if c == "1250" or "falha de keep alive" in d:
        return {"event_type": "communication_failure", "priority": "medium", "open_occurrence": True}
    if c == "3250" or "restauracao de keep alive" in d:
        return {"event_type": "communication_restore", "priority": "low", "open_occurrence": False}
    if c in {"1602"} or "teste periodico" in d or "reporte periodico" in d:
        return {"event_type": "test", "priority": "low", "open_occurrence": False}
    if c in {"1401", "1402", "1403", "1404", "1409", "3401", "3402", "3403", "3404", "3409"}:
        return {"event_type": "open_close", "priority": "low", "open_occurrence": False}
    if "sistema nao armado" in d or "sistema não armado" in (description or "").lower() or "nao armou" in d or "falha ao armar" in d or "arme nao" in d or c in {"X002", "E402", "E403"}:
        return {"event_type": "arm_state_problem", "priority": "medium", "open_occurrence": True}
    if "desarme" in d or "desativacao" in d or "ativacao" in d or "armado" in d:
        return {"event_type": "open_close", "priority": "low", "open_occurrence": False}
    if "falha de conexao" in d or "gprs" in d or "comunicacao" in d:
        return {"event_type": "communication_failure", "priority": "medium", "open_occurrence": True}
    if "alarme" in d or "disparo" in d or "panico" in d or "furto" in d:
        return {"event_type": "alarm", "priority": "high", "open_occurrence": True}
    if "normalizada" in d or "restauracao" in d:
        return {"event_type": "restore", "priority": "low", "open_occurrence": False}
    return {"event_type": "activenet", "priority": "low", "open_occurrence": False}


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



def _as_list(value: Any) -> list:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            import json as _json
            parsed = _json.loads(value)
            return parsed if isinstance(parsed, list) else []
        except Exception:
            return []
    return []


def _normalize_contacts(value: Any) -> list[dict[str, Any]]:
    contacts = []
    for idx, item in enumerate(_as_list(value), start=1):
        if hasattr(item, "model_dump"):
            item = item.model_dump()
        elif not isinstance(item, dict):
            continue
        name = _clean(item.get("name") or item.get("nome"))
        phone = _clean(item.get("phone") or item.get("telefone"))
        function = _clean(item.get("function") or item.get("funcao"))
        if not name and not phone:
            continue
        contacts.append({
            "name": name or phone or f"Contato {idx}",
            "phone": phone or "",
            "function": function,
            "priority": int(item.get("priority") or idx),
            "row": item,
        })
    return contacts


def _normalize_zones(value: Any) -> list[dict[str, Any]]:
    zones = []
    for idx, item in enumerate(_as_list(value), start=1):
        if hasattr(item, "model_dump"):
            item = item.model_dump()
        elif not isinstance(item, dict):
            continue
        number = _clean(item.get("zone_number") or item.get("zona") or item.get("id") or idx)
        name = _clean(item.get("name") or item.get("nome") or item.get("area"))
        area = _clean(item.get("area") or item.get("nome"))
        if not number and not name:
            continue
        if number and number.isdigit():
            number = number.zfill(2) if len(number) < 3 else number
        zones.append({
            "zone_number": number or str(idx).zfill(2),
            "name": name or f"Área {idx}",
            "area": area,
            "row": item,
        })
    return zones

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
        notes=_clean(getattr(item, "notes", None)) or _pick(row, "notes", ACCOUNT_FIELD_ALIASES),
        protocol_note=_clean(getattr(item, "protocol_note", None)) or _pick(row, "protocol_note", ACCOUNT_FIELD_ALIASES),
        contacts=_normalize_contacts(getattr(item, "contacts", None) or row.get("contacts")),
        zones=_normalize_zones(getattr(item, "zones", None) or row.get("zones")),
        source_owner_id=_clean(getattr(item, "source_owner_id", None)) or _pick(row, "source_owner_id", ACCOUNT_FIELD_ALIASES),
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



def _sync_contacts(db: Session, account: models.Account, contacts: list[dict[str, Any]]) -> None:
    for idx, data in enumerate(contacts, start=1):
        phone = _clean(data.get("phone")) or ""
        name = _clean(data.get("name")) or phone or f"Contato {idx}"
        function = _clean(data.get("function"))
        priority = int(data.get("priority") or idx)
        existing = None
        if phone:
            existing = db.query(models.AccountContact).filter_by(account_id=account.id, phone=phone).first()
        if not existing:
            existing = db.query(models.AccountContact).filter_by(account_id=account.id, name=name).first()
        if not existing:
            db.add(models.AccountContact(
                account_id=account.id,
                name=name,
                phone=phone or "-",
                priority=priority,
                password_hint=function,
                active=True,
            ))
        else:
            existing.name = name or existing.name
            existing.phone = phone or existing.phone
            existing.priority = priority
            if function:
                existing.password_hint = function
            existing.active = True


def _sync_zones(db: Session, account: models.Account, zones: list[dict[str, Any]]) -> None:
    for idx, data in enumerate(zones, start=1):
        number = _clean(data.get("zone_number")) or str(idx).zfill(2)
        name = _clean(data.get("name")) or f"Área {number}"
        area = _clean(data.get("area"))
        existing = db.query(models.AccountZone).filter_by(account_id=account.id, zone_number=number).first()
        if not existing:
            db.add(models.AccountZone(account_id=account.id, zone_number=number, name=name, area=area, active=True))
        else:
            existing.name = name or existing.name
            existing.area = area or existing.area
            existing.active = True

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

    if account.notes and not existing_account.notes:
        existing_account.notes = account.notes
    if account.protocol_note and not existing_account.protocol_note:
        existing_account.protocol_note = account.protocol_note
    if account.contacts:
        _sync_contacts(db, existing_account, account.contacts)
    if account.zones:
        _sync_zones(db, existing_account, account.zones)
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
    classification = classify_active_net_event(event.event_code, event.description)
    exists = db.query(models.EventCode).filter_by(code=event.event_code).first()
    if exists:
        # Se o cadastro veio sem nome bom, melhora com a descrição real do Active Net.
        if event.description and (exists.name.startswith("Evento Active Net") or exists.name == f"Evento {event.event_code}"):
            exists.name = event.description
        # Eventos criados automaticamente como activenet/histórico podem ganhar regra mais precisa
        # depois que descobrimos o significado real pelo Active Net.
        if exists.event_type in {"activenet", "open_close", "test", "communication_failure", "communication_restore", "arm_state_problem"}:
            exists.event_type = classification["event_type"]
            exists.priority = classification["priority"]
            exists.open_occurrence = classification["open_occurrence"]
        return

    db.add(
        models.EventCode(
            code=event.event_code,
            name=event.description or f"Evento Active Net {event.event_code}",
            event_type=classification["event_type"],
            priority=classification["priority"],
            open_occurrence=classification["open_occurrence"],
            sound="alarm" if classification["priority"] == "high" else None,
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
