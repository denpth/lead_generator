import uuid

from sqlalchemy.orm import Session

from app.models.lead import Lead, LeadStatus
from app.schemas.lead import LeadCreate
from app.services.n8n import N8nDispatcher


def create_lead(db: Session, payload: LeadCreate) -> Lead:
    lead = Lead(**payload.model_dump(mode="python"), status=LeadStatus.PENDING)
    db.add(lead)
    db.commit()
    db.refresh(lead)
    return lead


def get_lead(db: Session, lead_id: uuid.UUID) -> Lead | None:
    return db.get(Lead, lead_id)


def dispatch_lead(db: Session, lead: Lead, dispatcher: N8nDispatcher) -> Lead:
    result = dispatcher.dispatch(lead)
    lead.dispatch_attempts += result.attempts
    lead.last_webhook_status_code = result.status_code
    lead.last_error = result.error
    lead.status = LeadStatus.DISPATCHED if result.success else LeadStatus.FAILED
    db.add(lead)
    db.commit()
    db.refresh(lead)
    return lead
