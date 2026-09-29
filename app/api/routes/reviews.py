import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.db import get_db
from app.models.lead import Lead, ResponsePriority, ReviewStatus
from app.schemas.lead import LeadRead, ReviewDecision
from app.services.decision import WINDOWS

router = APIRouter(prefix="/leads", tags=["review"])


@router.post("/{lead_id}/review/{decision}", response_model=LeadRead)
def decide_review(
    lead_id: uuid.UUID,
    decision: ReviewStatus,
    payload: ReviewDecision,
    db: Session = Depends(get_db),
) -> LeadRead:
    if decision not in {ReviewStatus.ACCEPTED, ReviewStatus.DISCARDED}:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Review decision must be accepted or discarded",
        )
    if decision == ReviewStatus.ACCEPTED and payload.priority not in {
        ResponsePriority.IMMEDIATE, ResponsePriority.PRIORITY,
        ResponsePriority.STANDARD, ResponsePriority.LOW,
    }:
        raise HTTPException(422, "Choose a follow-up priority before accepting")
    lead = db.scalar(select(Lead).where(Lead.id == lead_id).with_for_update())
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
    lead.reviewer_name = payload.reviewer_name
    lead.review_note = payload.note
    lead.reviewed_at = datetime.now(UTC)
    if decision == ReviewStatus.ACCEPTED:
        lead.response_priority = payload.priority
        lead.response_window_minutes = WINDOWS[payload.priority]
        lead.response_due_at = lead.reviewed_at + timedelta(minutes=lead.response_window_minutes)
    db.add(lead)
    db.commit()
    db.refresh(lead)
    return LeadRead.model_validate(lead)


@router.post("/{lead_id}/complete", response_model=LeadRead)
def complete_follow_up(lead_id: uuid.UUID, db: Session = Depends(get_db)) -> LeadRead:
    lead = db.scalar(select(Lead).where(Lead.id == lead_id).with_for_update())
    if lead is None:
        raise HTTPException(404, "Lead not found")
    if lead.review_status in {ReviewStatus.PENDING, ReviewStatus.DISCARDED} or (
        lead.response_priority is None or lead.response_priority == ResponsePriority.REVIEW
    ):
        raise HTTPException(409, "Resolve review and select a priority before completing follow-up")
    if lead.completed_at is None:
        lead.completed_at = datetime.now(UTC)
        db.commit()
        db.refresh(lead)
    return LeadRead.model_validate(lead)
