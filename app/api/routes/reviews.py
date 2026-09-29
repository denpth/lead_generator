import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.lead import ResponsePriority, ReviewStatus
from app.schemas.lead import LeadRead
from app.services.leads import get_lead

router = APIRouter(prefix="/leads", tags=["review"])


@router.post("/{lead_id}/review/{decision}", response_model=LeadRead)
def decide_review(
    lead_id: uuid.UUID,
    decision: ReviewStatus,
    db: Session = Depends(get_db),
) -> LeadRead:
    if decision not in {ReviewStatus.ACCEPTED, ReviewStatus.DISCARDED}:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Review decision must be accepted or discarded",
        )
    lead = get_lead(db, lead_id)
    if lead is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found")
    if lead.response_priority != ResponsePriority.REVIEW:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only review leads can receive a review decision",
        )
    if lead.review_status != ReviewStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This review already has a decision",
        )
    lead.review_status = decision
    db.add(lead)
    db.commit()
    db.refresh(lead)
    return LeadRead.model_validate(lead)
