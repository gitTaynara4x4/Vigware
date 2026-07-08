from datetime import datetime
from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.app.core.database import Base


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    slug: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    email: Mapped[str] = mapped_column(String(180), nullable=False, unique=True)
    role: Mapped[str] = mapped_column(String(60), default="operator")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Client(Base):
    __tablename__ = "clients"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    trade_name: Mapped[str] = mapped_column(String(180), nullable=False)
    document: Mapped[str | None] = mapped_column(String(60), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(80), nullable=True)
    email: Mapped[str | None] = mapped_column(String(180), nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    accounts: Mapped[list["Account"]] = relationship(back_populates="client")


class Account(Base):
    __tablename__ = "accounts"
    __table_args__ = (
        UniqueConstraint("company_id", "code", name="uq_accounts_company_code"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False, index=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id"), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    partition_number: Mapped[str] = mapped_column(String(20), default="001")
    armed: Mapped[bool] = mapped_column(Boolean, default=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    protocol_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    client: Mapped[Client] = relationship(back_populates="accounts")
    zones: Mapped[list["AccountZone"]] = relationship(back_populates="account")
    contacts: Mapped[list["AccountContact"]] = relationship(back_populates="account")


class AccountZone(Base):
    __tablename__ = "account_zones"
    __table_args__ = (
        UniqueConstraint("account_id", "zone_number", name="uq_account_zones_account_zone"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), nullable=False, index=True)
    zone_number: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    area: Mapped[str | None] = mapped_column(String(160), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)

    account: Mapped[Account] = relationship(back_populates="zones")


class AccountContact(Base):
    __tablename__ = "account_contacts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    phone: Mapped[str] = mapped_column(String(80), nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=1)
    password_hint: Mapped[str | None] = mapped_column(String(180), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)

    account: Mapped[Account] = relationship(back_populates="contacts")


class Receiver(Base):
    __tablename__ = "receivers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    protocol: Mapped[str] = mapped_column(String(60), default="HTTP_SIMULATED")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class EventCode(Base):
    __tablename__ = "event_codes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    code: Mapped[str] = mapped_column(String(30), nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    event_type: Mapped[str] = mapped_column(String(60), default="alarm")
    priority: Mapped[str] = mapped_column(String(20), default="medium")
    open_occurrence: Mapped[bool] = mapped_column(Boolean, default=True)
    sound: Mapped[str | None] = mapped_column(String(80), nullable=True)


class RawEvent(Base):
    __tablename__ = "raw_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False, index=True)
    receiver_id: Mapped[int | None] = mapped_column(ForeignKey("receivers.id"), nullable=True)
    protocol: Mapped[str] = mapped_column(String(60), default="HTTP_SIMULATED")
    account_code: Mapped[str] = mapped_column(String(30), index=True)
    event_code: Mapped[str] = mapped_column(String(30), index=True)
    partition_number: Mapped[str | None] = mapped_column(String(20), nullable=True)
    zone_number: Mapped[str | None] = mapped_column(String(20), nullable=True)
    raw_payload: Mapped[str | None] = mapped_column(Text, nullable=True)
    processed: Mapped[bool] = mapped_column(Boolean, default=False)
    occurrence_id: Mapped[int | None] = mapped_column(ForeignKey("occurrences.id"), nullable=True)
    received_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class Occurrence(Base):
    __tablename__ = "occurrences"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False, index=True)
    client_id: Mapped[int | None] = mapped_column(ForeignKey("clients.id"), nullable=True, index=True)
    account_id: Mapped[int | None] = mapped_column(ForeignKey("accounts.id"), nullable=True, index=True)
    account_code: Mapped[str] = mapped_column(String(30), index=True)
    partition_number: Mapped[str | None] = mapped_column(String(20), nullable=True)
    zone_number: Mapped[str | None] = mapped_column(String(20), nullable=True)
    zone_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    event_code: Mapped[str] = mapped_column(String(30), index=True)
    description: Mapped[str] = mapped_column(String(220), nullable=False)
    priority: Mapped[str] = mapped_column(String(20), default="medium")
    status: Mapped[str] = mapped_column(String(30), default="NEW", index=True)
    event_count: Mapped[int] = mapped_column(Integer, default=1)
    assigned_operator_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class OccurrenceTimeline(Base):
    __tablename__ = "occurrence_timeline"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    occurrence_id: Mapped[int] = mapped_column(ForeignKey("occurrences.id"), nullable=False, index=True)
    type: Mapped[str] = mapped_column(String(60), default="EVENT")
    title: Mapped[str] = mapped_column(String(180), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    event_code: Mapped[str | None] = mapped_column(String(30), nullable=True)
    created_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class OccurrenceWatcher(Base):
    __tablename__ = "occurrence_watchers"
    __table_args__ = (
        UniqueConstraint("occurrence_id", "user_id", name="uq_occurrence_watchers_occ_user"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    occurrence_id: Mapped[int] = mapped_column(ForeignKey("occurrences.id"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class PatrolCar(Base):
    __tablename__ = "patrol_cars"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False, index=True)
    description: Mapped[str] = mapped_column(String(160), nullable=False)
    plates: Mapped[str | None] = mapped_column(String(40), nullable=True)
    online: Mapped[bool] = mapped_column(Boolean, default=True)
    available: Mapped[bool] = mapped_column(Boolean, default=True)
    latitude: Mapped[str | None] = mapped_column(String(40), nullable=True)
    longitude: Mapped[str | None] = mapped_column(String(40), nullable=True)
    last_keep_alive: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class ReceiverNonce(Base):
    __tablename__ = "receiver_nonces"
    __table_args__ = (
        UniqueConstraint("bridge_id", "nonce", name="uq_receiver_nonces_bridge_nonce"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    bridge_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    nonce: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    received_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
