import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.dependencies import get_n8n_dispatcher
from app.models.lead import LeadStatus
from app.schemas.lead import LeadCreate, LeadRead
from app.services.leads import create_lead, dispatch_lead, get_lead
from app.services.n8n import N8nDispatcher

router = APIRouter(prefix="/leads", tags=["leads"])


@router.post("", response_model=LeadRead, status_code=status.HTTP_201_CREATED)
def create_lead_endpoint(
    payload: LeadCreate,
    db: Session = Depends(get_db),
    dispatcher: N8nDispatcher = Depends(get_n8n_dispatcher),
) -> LeadRead:
    lead = create_lead(db, payload)
    return LeadRead.model_validate(dispatch_lead(db, lead, dispatcher))


@router.get("/{lead_id}", response_model=LeadRead)
def get_lead_endpoint(lead_id: uuid.UUID, db: Session = Depends(get_db)) -> LeadRead:
    lead = get_lead(db, lead_id)
    if lead is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found")
    return LeadRead.model_validate(lead)


@router.post("/{lead_id}/retry", response_model=LeadRead)
def retry_lead_endpoint(
    lead_id: uuid.UUID,
    db: Session = Depends(get_db),
    dispatcher: N8nDispatcher = Depends(get_n8n_dispatcher),
) -> LeadRead:
    lead = get_lead(db, lead_id)
    if lead is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found")
    if lead.status != LeadStatus.FAILED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only failed leads can be retried",
        )
    return LeadRead.model_validate(dispatch_lead(db, lead, dispatcher))
