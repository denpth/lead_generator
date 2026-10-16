import hmac
import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.config import Settings, get_settings
from app.db import get_db
from app.dependencies import get_lead_decision_engine
from app.models.lead import Lead, ResponsePriority, ReviewStatus
from app.schemas.lead import LeadDecisionRead
from app.services.decision import LeadDecisionEngine

router = APIRouter(prefix="/internal/leads", tags=["automation"])


def require_automation_key(
    x_automation_key: str = Header(default=""),
    settings: Settings = Depends(get_settings),
) -> None:
    expected = settings.automation_internal_key
    if not expected or not hmac.compare_digest(x_automation_key, expected):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid automation key")


@router.post(
    "/{lead_id}/decision",
    response_model=LeadDecisionRead,
    dependencies=[Depends(require_automation_key)],
)
def decide_lead_endpoint(
    lead_id: uuid.UUID,
    db: Session = Depends(get_db),
    engine: LeadDecisionEngine = Depends(get_lead_decision_engine),
) -> LeadDecisionRead:
    # Serialize automated decisions with human review to preserve human authority.
    lead = db.scalar(select(Lead).where(Lead.id == lead_id).with_for_update())
    if lead is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found")
    if lead.review_status in {ReviewStatus.ACCEPTED, ReviewStatus.DISCARDED} or lead.completed_at:
        raise HTTPException(409, "Human decisions and completed follow-ups cannot be overwritten")

    result = engine.decide(lead)
    now = datetime.now(UTC)
    due_at = now + timedelta(minutes=result.window_minutes)
    _store_decision(
        db,
        lead,
        result.summary,
        result.priority,
        result.window_minutes,
        due_at,
        result.confidence,
        result.model,
        result.warning,
        result.summary_fidelity,
        result.summary_fidelity_confidence,
        result.input_safety,
        result.input_safety_confidence,
        now,
    )
    return LeadDecisionRead(
        lead_id=lead.id,
        summary=result.summary,
        response_priority=result.priority,
        response_window_minutes=result.window_minutes,
        response_due_at=due_at,
        confidence=result.confidence,
        model=result.model,
        route=result.priority.value,
        warning=result.warning,
    )


def _store_decision(
    db: Session,
    lead: Lead,
    summary: str,
    priority: ResponsePriority,
    window_minutes: int,
    due_at: datetime,
    confidence: float | None,
    model: str | None,
    warning: str | None,
    summary_fidelity: str | None,
    summary_fidelity_confidence: float | None,
    input_safety: str | None,
    input_safety_confidence: float | None,
    decided_at: datetime,
) -> None:
    lead.summary = summary
    lead.response_priority = priority
    lead.review_status = ReviewStatus.PENDING if priority == ResponsePriority.REVIEW else None
    lead.response_window_minutes = window_minutes
    lead.response_due_at = due_at
    lead.decision_confidence = confidence
    lead.urgency_confidence = confidence
    lead.summary_fidelity = summary_fidelity
    lead.summary_fidelity_confidence = summary_fidelity_confidence
    lead.input_safety = input_safety
    lead.input_safety_confidence = input_safety_confidence
    lead.decision_model = model
    lead.decision_error = warning
    lead.decided_at = decided_at
    db.add(lead)
    db.commit()
