from datetime import datetime
from sqlalchemy.orm import Session
from backend.app import models


EVENTS = [
    {"code": "E130", "name": "Disparo de alarme", "event_type": "alarm", "priority": "high", "open_occurrence": True, "sound": "alarm"},
    {"code": "R130", "name": "Restauração de alarme", "event_type": "restore", "priority": "low", "open_occurrence": False, "sound": None},
    {"code": "E301", "name": "Falha de energia AC", "event_type": "technical", "priority": "medium", "open_occurrence": True, "sound": "beep"},
    {"code": "R301", "name": "Restauração de energia AC", "event_type": "technical_restore", "priority": "low", "open_occurrence": False, "sound": None},
    {"code": "E302", "name": "Bateria baixa", "event_type": "technical", "priority": "medium", "open_occurrence": True, "sound": "beep"},
    {"code": "E401", "name": "Arme/desarme", "event_type": "open_close", "priority": "low", "open_occurrence": False, "sound": None},
    {"code": "E602", "name": "Teste periódico", "event_type": "test", "priority": "low", "open_occurrence": False, "sound": None},
    {"code": "1250", "name": "Falha de keep alive", "event_type": "communication_failure", "priority": "medium", "open_occurrence": True, "sound": "beep"},
    {"code": "3250", "name": "Restauração de keep alive", "event_type": "communication_restore", "priority": "low", "open_occurrence": False, "sound": None},
    {"code": "1602", "name": "Teste periódico", "event_type": "test", "priority": "low", "open_occurrence": False, "sound": None},
    {"code": "1401", "name": "Desarme por usuário", "event_type": "open_close", "priority": "low", "open_occurrence": False, "sound": None},
    {"code": "1409", "name": "Desarme via controle remoto", "event_type": "open_close", "priority": "low", "open_occurrence": False, "sound": None},
]


def ensure_seed(db: Session):
    company = db.get(models.Company, 1)
    if not company:
        company = models.Company(id=1, name="Vigware Demo", slug="default")
        db.add(company)
        db.flush()

    user = db.get(models.User, 1)
    if not user:
        db.add(models.User(id=1, company_id=1, name="Operador Demo", email="operador@vigware.local", role="operator"))
        db.flush()

    client = db.get(models.Client, 1)
    if not client:
        client = models.Client(
            id=1,
            company_id=1,
            name="KW Engenharia LTDA",
            trade_name="KW Engenharia",
            phone="(12) 99999-0000",
            email="contato@kw.local",
            address="Av. Exemplo, 1000 - Centro",
        )
        db.add(client)
        db.flush()

    account = db.get(models.Account, 1)
    if not account:
        account = models.Account(
            id=1,
            company_id=1,
            client_id=1,
            code="0594",
            name="KW Engenharia - Matriz",
            partition_number="001",
            notes="Cliente demo para testes do Vigware.",
            protocol_note="Confirmar senha/contrassenha. Se não atender, acionar responsável 2 e deslocamento.",
        )
        db.add(account)
        db.flush()

    if db.query(models.AccountZone).filter_by(account_id=1).count() == 0:
        db.add_all([
            models.AccountZone(account_id=1, zone_number="001", name="Recepção", area="Frente"),
            models.AccountZone(account_id=1, zone_number="002", name="Escritório", area="Administrativo"),
            models.AccountZone(account_id=1, zone_number="005", name="Porta dos fundos", area="Fundos"),
        ])

    if db.query(models.AccountContact).filter_by(account_id=1).count() == 0:
        db.add_all([
            models.AccountContact(account_id=1, name="João Responsável", phone="(12) 98888-0001", priority=1, password_hint="Senha verbal cadastrada"),
            models.AccountContact(account_id=1, name="Maria Responsável", phone="(12) 98888-0002", priority=2, password_hint="Contrassenha cadastrada"),
        ])

    if db.query(models.Receiver).filter_by(id=1).count() == 0:
        db.add(models.Receiver(id=1, company_id=1, name="Receiver HTTP Simulado", protocol="HTTP_SIMULATED"))

    if db.query(models.Receiver).filter_by(id=2).count() == 0:
        db.add(models.Receiver(id=2, company_id=1, name="Active Net Bridge", protocol="ACTIVENET_TABLE"))

    for item in EVENTS:
        exists = db.query(models.EventCode).filter_by(code=item["code"]).first()
        if not exists:
            db.add(models.EventCode(**item))

    if db.query(models.PatrolCar).filter_by(company_id=1).count() == 0:
        db.add_all([
            models.PatrolCar(company_id=1, description="VTR 01", plates="ABC1D23", online=True, available=True, latitude="-23.026", longitude="-45.555", last_keep_alive=datetime.utcnow()),
            models.PatrolCar(company_id=1, description="VTR 02", plates="XYZ9A88", online=True, available=False, latitude="-23.021", longitude="-45.548", last_keep_alive=datetime.utcnow()),
        ])

    db.commit()
