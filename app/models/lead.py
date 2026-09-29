import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, Float, Integer, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class LeadStatus(str, enum.Enum):
    PENDING = "pending"
    DISPATCHED = "dispatched"
    FAILED = "failed"


class ResponsePriority(str, enum.Enum):
    IMMEDIATE = "immediate"
    PRIORITY = "priority"
    STANDARD = "standard"
    LOW = "low"
    REVIEW = "review"


class Lead(Base):
    __tablename__ = "leads"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    first_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    email: Mapped[str | None] = mapped_column(String(320), nullable=True, index=True)
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    company: Mapped[str | None] = mapped_column(String(200), nullable=True)
    source: Mapped[str] = mapped_column(String(100), nullable=False, default="api")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    status: Mapped[LeadStatus] = mapped_column(
        Enum(LeadStatus, name="lead_status", native_enum=False, length=32),
        nullable=False,
        default=LeadStatus.PENDING,
        index=True,
    )
    dispatch_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_webhook_status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)

    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    response_priority: Mapped[ResponsePriority | None] = mapped_column(
        Enum(ResponsePriority, name="response_priority", native_enum=False, length=32),
        nullable=True,
        index=True,
    )
    response_window_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    response_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    decision_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    urgency_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    summary_fidelity: Mapped[str | None] = mapped_column(String(32), nullable=True)
    summary_fidelity_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    input_safety: Mapped[str | None] = mapped_column(String(32), nullable=True)
    input_safety_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    decision_model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    decision_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
