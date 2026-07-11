from datetime import datetime
import re
from sqlalchemy.orm import Session
from sqlalchemy import desc, or_
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
    if code in {"1250", "E301", "E302", "E250"}:
        return "OBSERVATION"
    if typ in {"communication_failure", "technical", "technical_failure"}:
        return "OBSERVATION"

    # Falha de arme/sistema não armado vira ocorrência operacional.
    if typ in {"arm_state_problem", "schedule_failure"}:
        return "STARTED"

    # Disparo/pânico/tamper entram em Novos.
    return "NEW"


RESTORE_EVENT_MAP = {
    "3250": ["1250"],
    "R250": ["E250"],
    "R301": ["E301"],
    "R302": ["E302"],
    "R130": ["E130"],
}

# Falhas de comunicação que devem desaparecer automaticamente quando a
# comunicação realmente for restabelecida.
COMMUNICATION_FAILURE_CODES = {"1250", "E250"}
AUTO_CLOSE_RESTORE_CODES = {"3250", "R250"}

# Pares usados também na reconciliação do board, para corrigir ocorrências que
# ficaram abertas antes da restauração ser processada pela regra atual.
AUTO_CLOSE_RESTORE_PAIRS = {
    "1250": {"3250"},
    "E250": {"R250"},
}


def restore_targets_for_event(event_code: str | None, description: str | None = None) -> list[str]:
    """Retorna quais eventos uma restauração/normalização deve vincular.

    Active Net/Contact ID costuma usar 1xxx para evento novo e 3xxx para
    restauração/normalização. Exemplo real: 1130 = alarme, 3130 = zona em
    alarme normalizada.

    Alguns 3xxx são arme normal (3401/3404 etc.), então esses são excluídos.
    """
    code = (event_code or "").upper().strip()
    if not code:
        return []
    if code in RESTORE_EVENT_MAP:
        return RESTORE_EVENT_MAP[code]
    if code in ARM_EVENT_CODES:
        return []

    desc = normalize_text(description)
    looks_restore = (
        "normalizada" in desc
        or "normalizado" in desc
        or "restauracao" in desc
        or "restaurado" in desc
        or "restabelecida" in desc
        or "restabelecido" in desc
        or "restore" in desc
        or "retorno" in desc
    )
    communication_hint = any(
        hint in desc
        for hint in ("keep alive", "conexao", "comunicacao", "gprs", "ethernet", "modulo", "online")
    )

    # Algumas instalações do Active Net enviam E250/R250; outras trazem apenas
    # o código base acompanhado da descrição. A descrição de restauração de
    # comunicação deve localizar qualquer falha de comunicação ativa da conta.
    if looks_restore and communication_hint:
        return sorted(COMMUNICATION_FAILURE_CODES)

    # Padrão Ademco/receiver usado em parte dos cadastros: E301 -> R301 etc.
    if re.fullmatch(r"R[0-9A-Z]+", code):
        return ["E" + code[1:]]

    # Contact ID: 1xxx abre e 3xxx restaura. Os códigos de arme já foram
    # excluídos acima para não transformar um arme normal em restauração.
    if code.isdigit() and len(code) == 4 and code.startswith("3"):
        return ["1" + code[1:]]
    return []


def is_restore_event(event_code: str | None, description: str | None = None) -> bool:
    return bool(restore_targets_for_event(event_code, description))


def should_auto_close_restore(
    event_code: str | None,
    description: str | None,
    targets: list[str] | None = None,
) -> bool:
    """Define se a restauração deve retirar a ocorrência da fila.

    Somente restauração de comunicação fecha automaticamente. Restaurações de
    alarme, bateria ou energia continuam na timeline para decisão do operador.
    """
    code = (event_code or "").upper().strip()
    if code in AUTO_CLOSE_RESTORE_CODES:
        return True

    targets = targets or restore_targets_for_event(code, description)
    if not set(targets).intersection(COMMUNICATION_FAILURE_CODES):
        return False

    desc = normalize_text(description)
    looks_restore = any(
        hint in desc
        for hint in (
            "restauracao",
            "restaurado",
            "restabelecida",
            "restabelecido",
            "normalizada",
            "normalizado",
            "retorno",
            "online novamente",
        )
    )
    communication_hint = any(
        hint in desc
        for hint in ("keep alive", "conexao", "comunicacao", "gprs", "ethernet", "modulo", "online")
    )
    return looks_restore and communication_hint


ARM_EVENT_CODES = {"3401", "3402", "3403", "3404", "3409", "E401"}
DISARM_EVENT_CODES = {"1401", "1402", "1403", "1404", "1409"}
ARM_PROBLEM_HINTS = ["não armado", "nao armado", "nao armou", "falha ao armar", "arme não", "arme nao", "sistema não armado", "sistema nao armado"]
ARM_NORMAL_HINTS = ["arme", "armado", "ativação", "ativacao", "desarme", "desarmado", "desativação", "desativacao"]


def normalize_text(value: str | None) -> str:
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


def contains_normalized_phrase(text: str | None, phrase: str | None) -> bool:
    """Procura palavra/frase inteira, sem confundir `arme` com `alarme`."""
    normalized_text = normalize_text(text)
    normalized_phrase = normalize_text(phrase).strip()
    if not normalized_phrase:
        return False
    pattern = rf"(?<![a-z0-9_]){re.escape(normalized_phrase)}(?![a-z0-9_])"
    return re.search(pattern, normalized_text) is not None


def is_arm_problem_event(event_code: str | None, description: str | None) -> bool:
    code = (event_code or "").upper()
    desc = normalize_text(description)
    if code in {"X002", "E402", "E403"}:
        return True
    return any(contains_normalized_phrase(desc, hint) for hint in ARM_PROBLEM_HINTS)


def is_normal_arm_disarm_event(event_code: str | None, description: str | None, event_type: str | None = None) -> bool:
    if is_arm_problem_event(event_code, description):
        return False
    code = (event_code or "").upper()
    typ = (event_type or "").lower()
    desc = normalize_text(description)
    if typ in {"alarm", "panic", "burglary", "tamper"}:
        return False
    if typ == "open_close" or code in ARM_EVENT_CODES or code in DISARM_EVENT_CODES:
        return True
    # Heurística para códigos Active Net novos: usa palavras inteiras para que
    # "alarme" não seja interpretado como o comando "arme".
    return any(contains_normalized_phrase(desc, hint) for hint in ARM_NORMAL_HINTS)


def infer_armed_state(event_code: str | None, description: str | None) -> bool | None:
    code = (event_code or "").upper()
    desc = normalize_text(description)
    if is_arm_problem_event(code, description):
        return False
    if code in DISARM_EVENT_CODES or any(
        contains_normalized_phrase(desc, phrase)
        for phrase in ("desarme", "desativacao", "desarmado")
    ):
        return False
    if code in ARM_EVENT_CODES or any(
        contains_normalized_phrase(desc, phrase)
        for phrase in ("ativacao", "armado", "arme")
    ):
        return True
    return None


def apply_account_arm_state(db: Session, account: models.Account | None, event_code: str | None, description: str | None) -> bool | None:
    if not account:
        return None
    state = infer_armed_state(event_code, description)
    if state is None:
        return None
    account.armed = state
    account.notes = account.notes or ""
    return state


def register_restore_on_active_occurrence(db: Session, payload, description: str):
    """Vincula restaurações/normalizações à ocorrência ativa.

    Regra operacional estilo Segware:
    - 1250/Falha de keep alive abre ocorrência em Observação.
    - 3250/Restauração de keep alive normaliza TODAS as ocorrências 1250 ativas
      da mesma conta e tira os cards da tela automaticamente.
    - Isso não mexe em evento manual; é fechamento técnico por restauração real.
    """
    code = (payload.event_code or "").upper()
    targets = restore_targets_for_event(code, description)
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

        if should_auto_close_restore(code, description, targets):
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
    """Fecha falhas de comunicação cuja restauração já foi importada.

    Corrige tanto o par Contact ID 1250/3250 quanto o par E250/R250. A rotina
    usa apenas eventos já copiados para o Vigware e nunca altera o Active Net.
    """
    active_failures = (
        db.query(models.Occurrence)
        .filter(models.Occurrence.company_id == 1)
        .filter(models.Occurrence.event_code.in_(list(AUTO_CLOSE_RESTORE_PAIRS.keys())))
        .filter(models.Occurrence.status.in_(ACTIVE_STATUSES))
        .all()
    )

    closed = 0
    for occ in active_failures:
        restore_codes = AUTO_CLOSE_RESTORE_PAIRS.get((occ.event_code or "").upper(), set())
        if not restore_codes:
            continue

        relevant_codes = [occ.event_code, *sorted(restore_codes)]
        latest = (
            db.query(models.RawEvent)
            .filter(models.RawEvent.company_id == occ.company_id)
            .filter(models.RawEvent.account_code == occ.account_code)
            .filter(models.RawEvent.event_code.in_(relevant_codes))
            .filter(models.RawEvent.received_at >= occ.created_at)
            .order_by(desc(models.RawEvent.received_at), desc(models.RawEvent.id))
            .first()
        )
        latest_code = (latest.event_code or "").upper() if latest else ""
        if latest_code not in restore_codes:
            continue

        already = (
            db.query(models.OccurrenceTimeline)
            .filter(models.OccurrenceTimeline.occurrence_id == occ.id)
            .filter(models.OccurrenceTimeline.type == "AUTO_FINISH")
            .filter(models.OccurrenceTimeline.event_code == latest_code)
            .first()
        )

        occ.status = "FINISHED"
        occ.finished_at = datetime.utcnow()
        occ.updated_at = datetime.utcnow()
        if not already:
            add_timeline(
                db,
                occ.id,
                title=f"Restauração recebida {latest_code}",
                description="Comunicação restabelecida. Ocorrência finalizada automaticamente.",
                type_="AUTO_FINISH",
                event_code=latest_code,
            )
        closed += 1

    if closed:
        db.commit()
    return closed




def reconcile_restore_duplicate_occurrences(db: Session):
    """Remove da fila cards antigos criados por restauração/normalização.

    Exemplo do problema: Active Net envia 1130 (alarme) e depois 3130
    (zona em alarme normalizada). O 3130 não é nova ocorrência; ele deve ser
    timeline da 1130. Se versões antigas abriram card 3130, este reconciliador
    tira o card duplicado da tela sem apagar histórico.
    """
    active = (
        db.query(models.Occurrence)
        .filter(models.Occurrence.company_id == 1)
        .filter(models.Occurrence.status.in_(ACTIVE_STATUSES))
        .all()
    )

    closed = 0
    for occ in active:
        targets = restore_targets_for_event(occ.event_code, occ.description)
        if not targets:
            continue

        target_occ = (
            db.query(models.Occurrence)
            .filter(models.Occurrence.company_id == occ.company_id)
            .filter(models.Occurrence.account_code == occ.account_code)
            .filter(models.Occurrence.event_code.in_(targets))
            .filter(models.Occurrence.status.in_(ACTIVE_STATUSES))
            .filter(models.Occurrence.id != occ.id)
            .order_by(desc(models.Occurrence.updated_at), desc(models.Occurrence.created_at))
            .first()
        )

        if target_occ:
            already = (
                db.query(models.OccurrenceTimeline)
                .filter(models.OccurrenceTimeline.occurrence_id == target_occ.id)
                .filter(models.OccurrenceTimeline.type == "RESTORE")
                .filter(models.OccurrenceTimeline.event_code == occ.event_code)
                .first()
            )
            if not already:
                add_timeline(
                    db,
                    target_occ.id,
                    title=f"Normalização recebida {occ.event_code}",
                    description=f"{occ.description}. Card duplicado removido e vinculado à ocorrência original.",
                    type_="RESTORE",
                    event_code=occ.event_code,
                )

        occ.status = "FINISHED"
        occ.finished_at = datetime.utcnow()
        occ.updated_at = datetime.utcnow()
        add_timeline(
            db,
            occ.id,
            title="Card de normalização removido",
            description="Evento de restauração/normalização não fica como ocorrência separada.",
            type_="AUTO_FINISH",
            event_code=occ.event_code,
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

    # Correção anti-duplicidade estilo Segware:
    # eventos de normalização/restauração, como 3130, não devem abrir card separado.
    # Eles entram na timeline da ocorrência original, como 1130, e só 3250 fecha automático.
    if is_restore_event(payload.event_code, description):
        open_occ = False
        event_type = "restore"
        priority = "low"

    account = get_account(db, payload.account_code)
    zone = get_zone(db, account.id if account else None, payload.zone)

    # Atualiza o status armado/desarmado da conta com eventos normais de arme/desarme.
    armed_state = apply_account_arm_state(db, account, payload.event_code, description)
    if is_normal_arm_disarm_event(payload.event_code, description, event_type):
        open_occ = False
        event_type = "open_close"

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
        # Eventos normais de arme/desarme não abrem card, mas entram no histórico da conta
        # e, se já houver ocorrência ativa daquele cliente, também entram na timeline dela.
        occurrence = register_restore_on_active_occurrence(db, payload, description)
        if not occurrence and is_normal_arm_disarm_event(payload.event_code, description, event_type):
            occurrence = get_open_occurrence(db, payload.account_code)
            if occurrence:
                state_label = "Armado" if armed_state is True else ("Desarmado" if armed_state is False else "Atualizado")
                add_timeline(
                    db,
                    occurrence.id,
                    title=f"Status da partição: {state_label}",
                    description=f"{payload.event_code} - {description}",
                    type_="ARM_STATE",
                    event_code=payload.event_code,
                )
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
    reconcile_restore_duplicate_occurrences(db)

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


BULK_CLOSE_MAX_SELECTION = 50
EVENT_TYPE_LABELS = {
    "alarm": "Alarme",
    "panic": "Pânico",
    "burglary": "Intrusão",
    "tamper": "Violação",
    "technical": "Técnico",
    "technical_failure": "Falha técnica",
    "communication_failure": "Falha de comunicação",
    "communication_restore": "Restauração de comunicação",
    "restore": "Restauração",
    "arm_state_problem": "Falha de arme",
    "schedule_failure": "Falha de horário",
    "open_close": "Arme/desarme",
    "test": "Teste",
}


def _event_type_label(value: str | None) -> str:
    key = (value or "other").strip().lower()
    return EVENT_TYPE_LABELS.get(key, key.replace("_", " ").title())


def bulk_close_options(db: Session):
    companies = (
        db.query(models.Company)
        .filter(models.Company.active.is_(True))
        .order_by(models.Company.name)
        .all()
    )
    event_types = [
        row[0]
        for row in (
            db.query(models.EventCode.event_type)
            .filter(models.EventCode.event_type.isnot(None))
            .distinct()
            .order_by(models.EventCode.event_type)
            .all()
        )
        if row[0]
    ]
    return {
        "companies": [{"id": company.id, "name": company.name} for company in companies],
        "event_types": [
            {"value": value, "label": _event_type_label(value)}
            for value in event_types
        ],
        "priorities": [
            {"value": "high", "label": "Alta"},
            {"value": "medium", "label": "Média"},
            {"value": "low", "label": "Baixa"},
        ],
        "countries": [{"value": "Brasil", "label": "Brasil"}],
        "max_selection": BULK_CLOSE_MAX_SELECTION,
    }


def search_bulk_close_occurrences(
    db: Session,
    *,
    query: str | None = None,
    event_type: str | None = None,
    priority: str | None = None,
    company_id: int | None = None,
    country: str | None = None,
    state: str | None = None,
    city: str | None = None,
    neighborhood: str | None = None,
    user_id: int = 1,
    limit: int = 500,
):
    stmt = (
        db.query(
            models.Occurrence,
            models.Client,
            models.Account,
            models.Company,
            models.EventCode,
        )
        .outerjoin(models.Client, models.Client.id == models.Occurrence.client_id)
        .outerjoin(models.Account, models.Account.id == models.Occurrence.account_id)
        .outerjoin(models.Company, models.Company.id == models.Occurrence.company_id)
        .outerjoin(models.EventCode, models.EventCode.code == models.Occurrence.event_code)
        .filter(models.Occurrence.status.in_(ACTIVE_STATUSES))
    )

    text = (query or "").strip()
    if text:
        pattern = f"%{text}%"
        stmt = stmt.filter(
            or_(
                models.Occurrence.event_code.ilike(pattern),
                models.Occurrence.description.ilike(pattern),
                models.Occurrence.account_code.ilike(pattern),
                models.Client.name.ilike(pattern),
                models.Client.trade_name.ilike(pattern),
                models.Account.name.ilike(pattern),
            )
        )

    event_type = (event_type or "").strip().lower()
    if event_type:
        stmt = stmt.filter(models.EventCode.event_type == event_type)

    priority = (priority or "").strip().lower()
    if priority:
        stmt = stmt.filter(models.Occurrence.priority == priority)

    if company_id:
        stmt = stmt.filter(models.Occurrence.company_id == company_id)

    # O cadastro atual armazena endereço em um único campo. Os filtros abaixo
    # continuam funcionais procurando cada termo no endereço completo.
    for location_value in (country, state, city, neighborhood):
        clean = (location_value or "").strip()
        if clean:
            stmt = stmt.filter(models.Client.address.ilike(f"%{clean}%"))

    rows = (
        stmt.order_by(desc(models.Occurrence.updated_at), desc(models.Occurrence.created_at))
        .limit(max(1, min(int(limit or 500), 1000)))
        .all()
    )

    occurrence_ids = [row[0].id for row in rows]
    watcher_map: dict[int, list[tuple[int, str]]] = {}
    if occurrence_ids:
        watchers = (
            db.query(models.OccurrenceWatcher, models.User)
            .join(models.User, models.User.id == models.OccurrenceWatcher.user_id)
            .filter(models.OccurrenceWatcher.occurrence_id.in_(occurrence_ids))
            .all()
        )
        for watcher, user in watchers:
            watcher_map.setdefault(watcher.occurrence_id, []).append((watcher.user_id, user.name))

    items = []
    for occurrence, client, account, company, event_code in rows:
        other_watchers = [
            name for watcher_user_id, name in watcher_map.get(occurrence.id, [])
            if watcher_user_id != user_id
        ]
        locked_by = other_watchers[0] if other_watchers else None
        items.append({
            "id": occurrence.id,
            "event_code": occurrence.event_code,
            "description": occurrence.description,
            "event_type": event_code.event_type if event_code else "other",
            "event_type_label": _event_type_label(event_code.event_type if event_code else "other"),
            "priority": occurrence.priority,
            "status": occurrence.status,
            "status_label": STATUS_LABELS.get(occurrence.status, occurrence.status),
            "company_id": occurrence.company_id,
            "company_name": company.name if company else "Empresa não cadastrada",
            "account_code": occurrence.account_code,
            "partition_number": occurrence.partition_number or (account.partition_number if account else "001"),
            "client_name": (
                client.trade_name if client and client.trade_name
                else client.name if client
                else account.name if account
                else "Conta não cadastrada"
            ),
            "address": client.address if client and client.address else "Endereço não cadastrado",
            "created_at": occurrence.created_at.isoformat(),
            "updated_at": occurrence.updated_at.isoformat() if occurrence.updated_at else occurrence.created_at.isoformat(),
            "selectable": locked_by is None,
            "locked_by": locked_by,
        })

    return {
        "items": items,
        "count": len(items),
        "max_selection": BULK_CLOSE_MAX_SELECTION,
    }


def close_occurrences_bulk(db: Session, occurrence_ids: list[int], log: str, user_id: int = 1):
    ids = list(dict.fromkeys(int(value) for value in occurrence_ids if int(value) > 0))
    clean_log = (log or "").strip()

    if not ids:
        raise ValueError("Selecione pelo menos uma ocorrência")
    if len(ids) > BULK_CLOSE_MAX_SELECTION:
        raise ValueError(f"Permitida a seleção máxima de {BULK_CLOSE_MAX_SELECTION} eventos")
    if not clean_log:
        raise ValueError("Digite o log que será registrado nos eventos selecionados")

    occurrences = (
        db.query(models.Occurrence)
        .filter(models.Occurrence.id.in_(ids))
        .filter(models.Occurrence.status.in_(ACTIVE_STATUSES))
        .all()
    )
    found_ids = {occurrence.id for occurrence in occurrences}
    missing_ids = [occurrence_id for occurrence_id in ids if occurrence_id not in found_ids]
    if missing_ids:
        raise ValueError("Uma ou mais ocorrências já foram fechadas ou não estão disponíveis")

    locked = (
        db.query(models.OccurrenceWatcher, models.User)
        .join(models.User, models.User.id == models.OccurrenceWatcher.user_id)
        .filter(models.OccurrenceWatcher.occurrence_id.in_(ids))
        .filter(models.OccurrenceWatcher.user_id != user_id)
        .all()
    )
    if locked:
        names = sorted({user.name for _, user in locked})
        raise ValueError(f"Existem ocorrências em atendimento por outro operador: {', '.join(names)}")

    now = datetime.utcnow()
    operator_name = _operator_name(db, user_id)
    for occurrence in occurrences:
        previous_status = occurrence.status
        add_timeline(
            db,
            occurrence.id,
            title=clean_log[:160],
            description=f"Log aplicado em fechamento múltiplo por {operator_name}",
            type_="LOG",
            user_id=user_id,
        )
        occurrence.status = "FINISHED"
        occurrence.finished_at = now
        occurrence.updated_at = now
        add_timeline(
            db,
            occurrence.id,
            title=f"Status alterado: {STATUS_LABELS.get(previous_status, previous_status)} → Finalizado",
            description="Fechamento múltiplo de eventos",
            type_="STATUS",
            user_id=user_id,
        )

    (
        db.query(models.OccurrenceWatcher)
        .filter(models.OccurrenceWatcher.occurrence_id.in_(ids))
        .delete(synchronize_session=False)
    )
    db.commit()

    return {
        "ok": True,
        "closed_count": len(occurrences),
        "closed_ids": sorted(found_ids),
    }


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
    timeline_user_ids = {item.created_by_user_id for item in timeline if item.created_by_user_id}
    timeline_users = {
        user.id: user.name
        for user in (
            db.query(models.User).filter(models.User.id.in_(timeline_user_ids)).all()
            if timeline_user_ids else []
        )
    }
    patrol = db.query(models.PatrolCar).filter_by(company_id=1).order_by(models.PatrolCar.id).all()
    last_raw = (
        db.query(models.RawEvent)
        .filter(models.RawEvent.company_id == 1)
        .filter(models.RawEvent.account_code == occ.account_code)
        .order_by(desc(models.RawEvent.received_at))
        .first()
    )
    last_arm_raw = (
        db.query(models.RawEvent)
        .filter(models.RawEvent.company_id == 1)
        .filter(models.RawEvent.account_code == occ.account_code)
        .filter(models.RawEvent.event_code.in_(list(ARM_EVENT_CODES | DISARM_EVENT_CODES | {"X002", "E402", "E403"})))
        .order_by(desc(models.RawEvent.received_at), desc(models.RawEvent.id))
        .first()
    )
    recent_raw_events = (
        db.query(models.RawEvent)
        .filter(models.RawEvent.company_id == 1)
        .filter(models.RawEvent.account_code == occ.account_code)
        .order_by(desc(models.RawEvent.received_at), desc(models.RawEvent.id))
        .limit(30)
        .all()
    )

    def raw_event_out(raw: models.RawEvent):
        ev = db.query(models.EventCode).filter_by(code=raw.event_code).first()
        return {
            "id": raw.id,
            "type": "ACCOUNT_EVENT",
            "title": f"{raw.event_code} - {(ev.name if ev else 'Evento da conta')}",
            "description": f"Partição {raw.partition_number or '-'} | Zona {raw.zone_number or '-'} | Protocolo {raw.protocol}",
            "event_code": raw.event_code,
            "partition_number": raw.partition_number,
            "zone_number": raw.zone_number,
            "receiver_name": "JFL - ACTIVE 20 v3",
            "created_at": raw.received_at.isoformat(),
        }

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
            {
                "id": t.id,
                "type": t.type,
                "title": t.title,
                "description": t.description,
                "event_code": t.event_code,
                "partition_number": occ.partition_number,
                "zone_number": occ.zone_number,
                "receiver_name": "JFL - ACTIVE 20 v3",
                "created_by_name": timeline_users.get(t.created_by_user_id),
                "created_at": t.created_at.isoformat(),
            }
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
                "armed": bool(account.armed) if account else None,
                "armed_label": "Armado" if account and account.armed else "Desarmado",
                "partition_number": occ.partition_number or (account.partition_number if account else "001"),
                "last_event_code": last_raw.event_code if last_raw else occ.event_code,
                "last_event_at": last_raw.received_at.isoformat() if last_raw else occ.updated_at.isoformat(),
                "last_arm_event_code": last_arm_raw.event_code if last_arm_raw else None,
                "last_arm_event_at": last_arm_raw.received_at.isoformat() if last_arm_raw else None,
                "protocol": last_raw.protocol if last_raw else "ACTIVENET_DB",
                "can_command": True,
            }
        ],
        "account_events": [raw_event_out(raw) for raw in recent_raw_events],
        "operator_hint": account.protocol_note if account and account.protocol_note else None,
        "location_hint": account.notes if account and account.notes else None,
    }



def request_account_command(db: Session, occurrence_id: int, command: str, partition: str | None = None, note: str | None = None, user_id: int = 1):
    """Registra solicitação de comando para a conta.

    Esta etapa cria o ponto operacional na tela. O envio real para Active Net/JFL
    deve passar pelo bridge local autorizado; por enquanto fica registrado na
    timeline para não simular sucesso falso.
    """
    occ = db.get(models.Occurrence, occurrence_id)
    if not occ:
        return None
    account = db.get(models.Account, occ.account_id) if occ.account_id else get_account(db, occ.account_code)
    command = (command or "").upper().strip()
    if command not in {"ARM", "DISARM"}:
        raise ValueError("Comando inválido")
    label = "Arme" if command == "ARM" else "Desarme"
    part = partition or occ.partition_number or (account.partition_number if account else "001") or "001"
    add_timeline(
        db,
        occ.id,
        title=f"Comando solicitado: {label}",
        description=(note or f"Solicitação de {label.lower()} da partição {part}. A execução real será feita pelo bridge/local autorizado."),
        type_="COMMAND_REQUEST",
        event_code=command,
        user_id=user_id,
    )
    # Marca visualmente como estado solicitado, sem afirmar que a central aceitou.
    if account:
        account.armed = True if command == "ARM" else False
    db.commit()
    db.refresh(occ)
    return {"ok": True, "status": "queued", "command": command, "label": label, "partition": part, "occurrence": make_card(db, occ)}


def _operator_name(db: Session, user_id: int | None = 1) -> str:
    if not user_id:
        return "Sistema"
    user = db.get(models.User, user_id)
    return user.name if user else "Operador"


def add_operator_log(db: Session, occurrence_id: int, text: str, user_id: int = 1):
    occ = db.get(models.Occurrence, occurrence_id)
    if not occ:
        return None
    clean = (text or "").strip()
    if not clean:
        raise ValueError("Log vazio")
    add_timeline(
        db,
        occ.id,
        title=clean[:160],
        description=f"por {_operator_name(db, user_id)}",
        type_="LOG",
        user_id=user_id,
    )
    occ.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(occ)
    return {"ok": True, "occurrence": make_card(db, occ)}


def add_temporary_note(db: Session, occurrence_id: int, note: str | None = None, providence: str | None = None, user_id: int = 1):
    occ = db.get(models.Occurrence, occurrence_id)
    if not occ:
        return None
    note = (note or "").strip()
    providence = (providence or "").strip()
    if not note and not providence:
        raise ValueError("Anotação vazia")
    title = note or "Anotação temporária"
    desc = providence if providence else None
    if note and providence:
        desc = f"Providência: {providence}"
    add_timeline(
        db,
        occ.id,
        title=title[:160],
        description=desc,
        type_="NOTE",
        user_id=user_id,
    )
    occ.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(occ)
    return {"ok": True, "occurrence": make_card(db, occ)}


def add_manual_event(db: Session, occurrence_id: int, event_code: str, note: str | None = None, user_id: int = 1):
    occ = db.get(models.Occurrence, occurrence_id)
    if not occ:
        return None
    code = (event_code or "").upper().strip()
    if code not in {"X8", "X12"}:
        raise ValueError("Evento manual inválido")
    add_timeline(
        db,
        occ.id,
        title=f"Evento manual {code}",
        description=(note or f"Gerado manualmente por {_operator_name(db, user_id)}"),
        type_="MANUAL_EVENT",
        event_code=code,
        user_id=user_id,
    )
    occ.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(occ)
    return {"ok": True, "event_code": code, "occurrence": make_card(db, occ)}


def add_media_note(db: Session, occurrence_id: int, filenames: str, user_id: int = 1):
    occ = db.get(models.Occurrence, occurrence_id)
    if not occ:
        return None
    names = (filenames or "").strip()
    if not names:
        raise ValueError("Nenhuma mídia informada")
    add_timeline(
        db,
        occ.id,
        title="Mídia anexada",
        description=names[:500],
        type_="MEDIA",
        user_id=user_id,
    )
    occ.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(occ)
    return {"ok": True, "occurrence": make_card(db, occ)}

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
    """Marca a ocorrência como aberta pelo operador sem poluir a timeline."""
    occ = db.get(models.Occurrence, occurrence_id)
    if not occ:
        return None
    exists = db.query(models.OccurrenceWatcher).filter_by(occurrence_id=occurrence_id, user_id=user_id).first()
    if not exists:
        db.add(models.OccurrenceWatcher(occurrence_id=occurrence_id, user_id=user_id))
        db.commit()
    return occ


def unwatch_occurrence(db: Session, occurrence_id: int, user_id: int = 1):
    """Libera o bloqueio do operador sem criar registro operacional visível."""
    watcher = db.query(models.OccurrenceWatcher).filter_by(occurrence_id=occurrence_id, user_id=user_id).first()
    if watcher:
        db.delete(watcher)
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
