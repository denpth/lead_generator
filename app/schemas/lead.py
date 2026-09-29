import re
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from app.models.lead import LeadStatus, ResponsePriority, ReviewStatus

_PHONE_RE = re.compile(r"^[0-9+().\-\s]{1,32}$")


class LeadCreate(BaseModel):
    first_name: str | None = Field(default=None, max_length=100)
    last_name: str | None = Field(default=None, max_length=100)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=32)
    company: str | None = Field(default=None, max_length=200)
    source: str = Field(default="api", min_length=1, max_length=100)
    notes: str | None = Field(default=None, max_length=5000)

    model_config = ConfigDict(extra="forbid")

    @field_validator(
        "first_name", "last_name", "phone", "company", "source", "notes", mode="before"
    )
    @classmethod
    def strip_strings(cls, value: object) -> object:
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        return value

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value: str | None) -> str | None:
        if value is not None and not _PHONE_RE.fullmatch(value):
            raise ValueError(
                "phone may contain only digits, spaces, +, parentheses, periods, and hyphens"
            )
        if value is not None and len(re.sub(r"\D", "", value)) < 7:
            raise ValueError(
                "phone must contain at least 7 digits; otherwise leave it blank and provide an email"
            )
        return value

    @model_validator(mode="after")
    def require_contact_method(self) -> "LeadCreate":
        if self.email is None and self.phone is None:
            raise ValueError("at least one of email or phone is required")
        return self


class LeadRead(BaseModel):
    id: uuid.UUID
    first_name: str | None
    last_name: str | None
    email: EmailStr | None
    phone: str | None
    company: str | None
    source: str
    notes: str | None
    status: LeadStatus
    dispatch_attempts: int
    last_error: str | None
    last_webhook_status_code: int | None
    summary: str | None
    response_priority: ResponsePriority | None
    review_status: ReviewStatus | None
    reviewer_name: str | None
    review_note: str | None
    reviewed_at: datetime | None
    completed_at: datetime | None
    response_window_minutes: int | None
    response_due_at: datetime | None
    decision_confidence: float | None
    urgency_confidence: float | None
    summary_fidelity: str | None
    summary_fidelity_confidence: float | None
    input_safety: str | None
    input_safety_confidence: float | None
    decision_model: str | None
    decision_error: str | None
    decided_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class LeadPage(BaseModel):
    items: list[LeadRead]
    total: int
    counts: dict[str, int]
    priority_counts: dict[str, int]
    action_counts: dict[str, int] = Field(default_factory=dict)


class ReviewDecision(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    reviewer_name: str = Field(min_length=1, max_length=100)
    note: str = Field(min_length=1, max_length=2000)
    priority: ResponsePriority | None = None


class LeadDecisionRead(BaseModel):
    lead_id: uuid.UUID
    summary: str
    response_priority: ResponsePriority
    response_window_minutes: int
    response_due_at: datetime
    confidence: float | None
    model: str | None
    route: str
    warning: str | None = None
