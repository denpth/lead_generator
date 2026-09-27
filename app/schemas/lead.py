import re
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from app.models.lead import LeadStatus

_PHONE_RE = re.compile(r"^[0-9+().\-\s]{7,32}$")


class LeadCreate(BaseModel):
    first_name: str | None = Field(default=None, max_length=100)
    last_name: str | None = Field(default=None, max_length=100)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=32)
    company: str | None = Field(default=None, max_length=200)
    source: str = Field(default="api", min_length=1, max_length=100)
    notes: str | None = Field(default=None, max_length=5000)

    model_config = ConfigDict(extra="forbid")

    @field_validator("first_name", "last_name", "phone", "company", "source", "notes", mode="before")
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
            raise ValueError("phone contains unsupported characters or has an invalid length")
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
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
