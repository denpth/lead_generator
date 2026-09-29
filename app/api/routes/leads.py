import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.dependencies import get_n8n_dispatcher
from app.models.lead import Lead, LeadStatus, ResponsePriority
from app.schemas.lead import LeadCreate, LeadPage, LeadRead
from app.services.leads import create_lead, dispatch_lead, get_lead
from app.services.n8n import N8nDispatcher

router = APIRouter(prefix="/leads", tags=["leads"])


@router.get("", response_model=LeadPage)
def list_leads_endpoint(
    db: Session = Depends(get_db),
    q: str = Query(default="", max_length=200),
    status_filter: LeadStatus | None = Query(default=None, alias="status"),
    priority_filter: ResponsePriority | None = Query(default=None, alias="priority"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> LeadPage:
    conditions = []
    if status_filter is not None:
        conditions.append(Lead.status == status_filter)
    if priority_filter is not None:
        conditions.append(Lead.response_priority == priority_filter)
    if q.strip():
        # Treat SQL wildcard characters as literal search text.
        pattern = (
            "%" + q.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        )
        conditions.append(
            or_(
                *[
                    field.ilike(pattern, escape="\\")
                    for field in (
                        Lead.first_name,
                        Lead.last_name,
                        Lead.email,
                        Lead.phone,
                        Lead.company,
                    )
                ]
            )
        )
    total = db.scalar(select(func.count()).select_from(Lead).where(*conditions)) or 0
    ordering = (
        (Lead.response_due_at.asc().nulls_last(), Lead.created_at.asc())
        if priority_filter == ResponsePriority.REVIEW
        else (Lead.created_at.desc(), Lead.id.desc())
    )
    leads = db.scalars(
        select(Lead).where(*conditions).order_by(*ordering).offset(offset).limit(limit)
    ).all()
    counts = {state.value: 0 for state in LeadStatus}
    for state, count in db.execute(select(Lead.status, func.count()).group_by(Lead.status)):
        counts[state.value] = count
    priority_counts = {priority.value: 0 for priority in ResponsePriority}
    for priority, count in db.execute(
        select(Lead.response_priority, func.count())
        .where(Lead.response_priority.is_not(None))
        .group_by(Lead.response_priority)
    ):
        priority_counts[priority.value] = count
    return LeadPage(
        items=[LeadRead.model_validate(lead) for lead in leads],
        total=total,
        counts=counts,
        priority_counts=priority_counts,
    )


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
