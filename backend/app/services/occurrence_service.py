from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import desc
from backend.app import models

ACTIVE_STATUSES = ["NEW", "STARTED", "DISPLACEMENT", "IN_PLACE", "OBSERVATION"]
STATUS_LABELS = {
    "NEW": "Novos",
    "STARTED": "Iniciado",
    "DISPLACEMENT": "Deslocamento",
    "IN_PLACE": "No local",
    "OBSERVATION": "Observação",
    "FINISHED": "Finalizado",
    "CANCELED": "Cancelado",
}
MONITORING_COLUMNS = {
    "newers": "NEW",
    "started": "STARTED",
    "displacement": "DISPLACEMENT",
    "inPlace": "IN_PLACE",
    "observation": "OBSERVATION",
}


def event_description(db: Session, code: str):
    event = db.query(models.EventCode).filter_by(code=code).first()
    if event:
        return event.name, event.priority, event.open_occurrence, event.event_type
    return f"Evento {code}", "medium", True, "alarm"


def initial_status_for_event(event_code: str, event_type: str | None) -> str:
    code = (event_code or "").upper()
    typ = (event_type or "").lower()

    # Falhas técnicas/comunicação entram em Observação, igual fila operacional de central.
    if code in {"1250", "E301", "E302"}:
        return "OBSERVATION"
    if typ in {"communication_failure", "technical", "technical_failure"}:
        return "OBSERVATION"

    # Disparo/pânico/tamper entram em Novos.
    return "NEW"


RESTORE_EVENT_MAP = {
    "3250": ["1250"],
    "R301": ["E301"],
    "R302": ["E302"],
    "R130": ["E130"],
}


AUTO_CLOSE_RESTORE_CODES = {"3250"}


def register_restore_on_active_occurrence(db: Session, payload, description: str):
    """Vincula restaurações/normalizações à ocorrência ativa.

    Regra operacional estilo Segware:
    - 1250/Falha de keep alive abre ocorrência em Observação.
    - 3250/Restauração de keep alive normaliza TODAS as ocorrências 1250 ativas
      da mesma conta e tira os cards da tela automaticamente.
    - Isso não mexe em evento manual; é fechamento técnico por restauração real.
    """
    code = (payload.event_code or "").upper()
    targets = RESTORE_EVENT_MAP.get(code)
    if not targets:
        return None

    occurrences = (
        db.query(models.Occurrence)
        .filter(models.Occurrence.company_id == 1)
        .filter(models.Occurrence.account_code == payload.account_code)
        .filter(models.Occurrence.event_code.in_(targets))
        .filter(models.Occurrence.status.in_(ACTIVE_STATUSES))
        .order_by(desc(models.Occurrence.updated_at), desc(models.Occurrence.created_at))
        .all()
    )
    if not occurrences:
        return None

    first = occurrences[0]
    for occ in occurrences:
        occ.event_count += 1
        occ.updated_at = datetime.utcnow()

        if code in AUTO_CLOSE_RESTORE_CODES:
            occ.status = "FINISHED"
            occ.finished_at = datetime.utcnow()
            add_timeline(
                db,
                occ.id,
                title=f"Normalização recebida {payload.event_code}",
                description=f"{description}. Ocorrência finalizada automaticamente por restauração da comunicação.",
                type_="AUTO_FINISH",
                event_code=payload.event_code,
            )
        else:
            add_timeline(
                db,
                occ.id,
                title=f"Restauração recebida {payload.event_code}",
                description=f"{description}. Ocorrência mantida ativa até finalização do operador.",
                type_="RESTORE",
                event_code=payload.event_code,
            )

    return first


def reconcile_restored_occurrences(db: Session):
    """Fecha cards antigos de falha de keep alive quando o último evento da conta já é restauração.

    Isso corrige casos em que a falha 1250 entrou antes da regra atual ou o card ficou
    aberto porque a normalização 3250 já tinha passado. A consulta usa somente os
    eventos já importados para o Vigware; não acessa nem altera o banco do Active Net.
    """
    active_keep_alive = (
        db.query(models.Occurrence)
        .filter(models.Occurrence.company_id == 1)
        .filter(models.Occurrence.event_code == "1250")
        .filter(models.Occurrence.status.in_(ACTIVE_STATUSES))
        .all()
    )

    closed = 0
    for occ in active_keep_alive:
        latest = (
            db.query(models.RawEvent)
            .filter(models.RawEvent.company_id == occ.company_id)
            .filter(models.RawEvent.account_code == occ.account_code)
            .filter(models.RawEvent.event_code.in_(["1250", "3250"]))
            .filter(models.RawEvent.received_at >= occ.created_at)
            .order_by(desc(models.RawEvent.received_at), desc(models.RawEvent.id))
            .first()
        )
        if not latest or (latest.event_code or "").upper() != "3250":
            continue

        # Evita duplicar timeline se o board for consultado várias vezes.
        already = (
            db.query(models.OccurrenceTimeline)
            .filter(models.OccurrenceTimeline.occurrence_id == occ.id)
            .filter(models.OccurrenceTimeline.type == "AUTO_FINISH")
            .filter(models.OccurrenceTimeline.event_code == "3250")
            .first()
        )

        occ.status = "FINISHED"
        occ.finished_at = datetime.utcnow()
        occ.updated_at = datetime.utcnow()
        if not already:
            add_timeline(
                db,
                occ.id,
                title="Normalização recebida 3250",
                description="Restauração de keep alive recebida. Ocorrência finalizada automaticamente.",
                type_="AUTO_FINISH",
                event_code="3250",
            )
        closed += 1

    if closed:
        db.commit()
    return closed


# Mantido como compatibilidade interna com versões anteriores.
def close_restored_occurrence(db: Session, payload, description: str):
    return register_restore_on_active_occurrence(db, payload, description)


def get_account(db: Session, account_code: str):
    return db.query(models.Account).filter_by(company_id=1, code=account_code).first()


def get_zone(db: Session, account_id: int | None, zone_number: str | None):
    if not account_id or not zone_number:
        return None
    return db.query(models.AccountZone).filter_by(account_id=account_id, zone_number=zone_number).first()


def get_open_occurrence(db: Session, account_code: str, event_code: str | None = None):
    query = (
        db.query(models.Occurrence)
        .filter(models.Occurrence.company_id == 1)
        .filter(models.Occurrence.account_code == account_code)
        .filter(models.Occurrence.status.in_(ACTIVE_STATUSES))
    )
    if event_code:
        query = query.filter(models.Occurrence.event_code == event_code)
    return query.order_by(desc(models.Occurrence.created_at)).first()


def add_timeline(db: Session, occurrence_id: int, title: str, description: str | None = None, type_: str = "EVENT", event_code: str | None = None, user_id: int | None = None):
    item = models.OccurrenceTimeline(
        occurrence_id=occurrence_id,
        type=type_,
        title=title,
        description=description,
        event_code=event_code,
        created_by_user_id=user_id,
    )
    db.add(item)
    db.flush()
    return item


def receive_event(db: Session, payload):
    description, priority, open_occ, event_type = event_description(db, payload.event_code)
    account = get_account(db, payload.account_code)
    zone = get_zone(db, account.id if account else None, payload.zone)

    raw_event = models.RawEvent(
        company_id=1,
        receiver_id=1,
        protocol=payload.protocol,
        account_code=payload.account_code,
        event_code=payload.event_code,
        partition_number=payload.partition,
        zone_number=payload.zone,
        raw_payload=payload.raw,
    )
    db.add(raw_event)
    db.flush()

    occurrence = None
    if open_occ:
        occurrence = get_open_occurrence(db, payload.account_code, payload.event_code)
        if occurrence:
            occurrence.event_count += 1
            occurrence.updated_at = datetime.utcnow()
            add_timeline(
                db,
                occurrence.id,
                title=f"Novo evento {payload.event_code}",
                description=f"{description} | Zona {payload.zone or '-'}",
                type_="EVENT",
                event_code=payload.event_code,
            )
        else:
            occurrence = models.Occurrence(
                company_id=1,
                client_id=account.client_id if account else None,
                account_id=account.id if account else None,
                account_code=payload.account_code,
                partition_number=payload.partition,
                zone_number=payload.zone,
                zone_name=zone.name if zone else None,
                event_code=payload.event_code,
                description=description,
                priority=priority,
                status=initial_status_for_event(payload.event_code, event_type),
            )
            db.add(occurrence)
            db.flush()
            add_timeline(
                db,
                occurrence.id,
                title=f"Evento recebido {payload.event_code}",
                description=f"{description} | Zona {payload.zone or '-'}",
                type_="EVENT",
                event_code=payload.event_code,
            )

        raw_event.occurrence_id = occurrence.id
    else:
        # Eventos de restauração/normalização não abrem novo card e não fecham
        # automaticamente. Eles entram na timeline da ocorrência ativa.
        occurrence = register_restore_on_active_occurrence(db, payload, description)
        if occurrence:
            raw_event.occurrence_id = occurrence.id

    raw_event.processed = True
    db.commit()
    if occurrence:
        db.refresh(occurrence)
    return raw_event, occurrence


def make_card(db: Session, occurrence: models.Occurrence):
    account = db.get(models.Account, occurrence.account_id) if occurrence.account_id else None
    if not account:
        account = get_account(db, occurrence.account_code)
    client = db.get(models.Client, occurrence.client_id) if occurrence.client_id else None
    if not client and account:
        client = db.get(models.Client, account.client_id)
    return {
        "id": occurrence.id,
        "account_code": occurrence.account_code,
        "client_name": client.trade_name if client else "Conta não cadastrada",
        "account_name": account.name if account else "Conta não cadastrada",
        "partition_number": occurrence.partition_number,
        "zone_number": occurrence.zone_number,
        "zone_name": occurrence.zone_name,
        "event_code": occurrence.event_code,
        "description": occurrence.description,
        "priority": occurrence.priority,
        "status": occurrence.status,
        "status_label": STATUS_LABELS.get(occurrence.status, occurrence.status),
        "event_count": occurrence.event_count,
        "created_at": occurrence.created_at.isoformat(),
        "updated_at": occurrence.updated_at.isoformat() if occurrence.updated_at else occurrence.created_at.isoformat(),
    }


def monitoring_board(db: Session):
    # Limpeza automática estilo Segware: se a última situação da conta foi 3250,
    # a falha 1250 não deve continuar presa na fila de Observação.
    reconcile_restored_occurrences(db)

    result = {key: [] for key in MONITORING_COLUMNS.keys()}
    occurrences = (
        db.query(models.Occurrence)
        .filter(models.Occurrence.company_id == 1)
        .filter(models.Occurrence.status.in_(ACTIVE_STATUSES))
        .order_by(desc(models.Occurrence.updated_at), desc(models.Occurrence.created_at))
        .all()
    )
    for occ in occurrences:
        for key, status in MONITORING_COLUMNS.items():
            if occ.status == status:
                result[key].append(make_card(db, occ))
                break
    return result


def get_detail(db: Session, occurrence_id: int):
    occ = db.get(models.Occurrence, occurrence_id)
    if not occ:
        return None
    account = db.get(models.Account, occ.account_id) if occ.account_id else None
    if not account:
        account = get_account(db, occ.account_code)
    client = db.get(models.Client, occ.client_id) if occ.client_id else None
    if not client and account:
        client = db.get(models.Client, account.client_id)
    contacts = db.query(models.AccountContact).filter_by(account_id=account.id).order_by(models.AccountContact.priority).all() if account else []
    zones = db.query(models.AccountZone).filter_by(account_id=account.id).order_by(models.AccountZone.zone_number).all() if account else []
    timeline = db.query(models.OccurrenceTimeline).filter_by(occurrence_id=occ.id).order_by(desc(models.OccurrenceTimeline.created_at)).all()
    patrol = db.query(models.PatrolCar).filter_by(company_id=1).order_by(models.PatrolCar.id).all()
    last_raw = (
        db.query(models.RawEvent)
        .filter(models.RawEvent.company_id == 1)
        .filter(models.RawEvent.account_code == occ.account_code)
        .order_by(desc(models.RawEvent.received_at))
        .first()
    )
    return {
        "occurrence": make_card(db, occ),
        "account": {
            "id": account.id,
            "code": account.code,
            "name": account.name,
            "armed": account.armed,
            "notes": account.notes,
            "protocol_note": account.protocol_note,
            "partition_number": account.partition_number,
        } if account else None,
        "client": {
            "id": client.id,
            "name": client.name,
            "trade_name": client.trade_name,
            "phone": client.phone,
            "email": client.email,
            "address": client.address,
        } if client else None,
        "contacts": [
            {"id": c.id, "name": c.name, "phone": c.phone, "priority": c.priority, "password_hint": c.password_hint}
            for c in contacts
        ],
        "zones": [
            {"id": z.id, "zone_number": z.zone_number, "name": z.name, "area": z.area}
            for z in zones
        ],
        "timeline": [
            {"id": t.id, "type": t.type, "title": t.title, "description": t.description, "event_code": t.event_code, "created_at": t.created_at.isoformat()}
            for t in timeline
        ],
        "patrol_cars": [
            {"id": p.id, "description": p.description, "plates": p.plates, "online": p.online, "available": p.available, "latitude": p.latitude, "longitude": p.longitude}
            for p in patrol
        ],
        "connections": [
            {
                "name": "JFL / Active Net",
                "status": "Vivo",
                "last_event_code": last_raw.event_code if last_raw else occ.event_code,
                "last_event_at": last_raw.received_at.isoformat() if last_raw else occ.updated_at.isoformat(),
                "protocol": last_raw.protocol if last_raw else "ACTIVENET_DB",
            }
        ],
        "operator_hint": account.protocol_note if account and account.protocol_note else None,
        "location_hint": account.notes if account and account.notes else None,
    }


def update_status(db: Session, occurrence_id: int, status: str, note: str | None = None, user_id: int = 1):
    status = status.upper()
    if status not in [*ACTIVE_STATUSES, "FINISHED", "CANCELED"]:
        raise ValueError("Status inválido")
    occ = db.get(models.Occurrence, occurrence_id)
    if not occ:
        return None
    old = occ.status
    occ.status = status
    occ.updated_at = datetime.utcnow()
    if status == "STARTED" and not occ.started_at:
        occ.started_at = datetime.utcnow()
        occ.assigned_operator_id = user_id
    if status in ["FINISHED", "CANCELED"]:
        occ.finished_at = datetime.utcnow()
    add_timeline(
        db,
        occ.id,
        title=f"Status alterado: {STATUS_LABELS.get(old, old)} → {STATUS_LABELS.get(status, status)}",
        description=note,
        type_="STATUS",
        user_id=user_id,
    )
    db.commit()
    db.refresh(occ)
    return occ


def watch_occurrence(db: Session, occurrence_id: int, user_id: int = 1):
    occ = db.get(models.Occurrence, occurrence_id)
    if not occ:
        return None
    exists = db.query(models.OccurrenceWatcher).filter_by(occurrence_id=occurrence_id, user_id=user_id).first()
    if not exists:
        db.add(models.OccurrenceWatcher(occurrence_id=occurrence_id, user_id=user_id))
        add_timeline(db, occurrence_id, title="Operador abriu a ocorrência", type_="WATCH", user_id=user_id)
    db.commit()
    return occ


def unwatch_occurrence(db: Session, occurrence_id: int, user_id: int = 1):
    watcher = db.query(models.OccurrenceWatcher).filter_by(occurrence_id=occurrence_id, user_id=user_id).first()
    if watcher:
        db.delete(watcher)
        add_timeline(db, occurrence_id, title="Operador saiu da ocorrência", type_="UNWATCH", user_id=user_id)
        db.commit()
    return True


def reset_demo(db: Session):
    # Apaga somente dados operacionais demo, preserva cadastros.
    db.query(models.OccurrenceWatcher).delete()
    db.query(models.OccurrenceTimeline).delete()
    db.query(models.RawEvent).delete()
    db.query(models.Occurrence).delete()
    db.commit()
    return True
