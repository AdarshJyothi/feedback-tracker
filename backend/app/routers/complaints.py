"""Complaint CRUD, workflow transitions, comments, and nested actions."""
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from .. import models, schemas
from ..database import get_db

router = APIRouter(prefix="/api/v1/complaints", tags=["complaints"])


def _next_ref(db: Session) -> str:
    last = db.query(models.Complaint).order_by(models.Complaint.id.desc()).first()
    n = (last.id + 1) if last else 1
    return f"CMP-{n:04d}"


def _get_or_404(db: Session, complaint_id: int) -> models.Complaint:
    c = (
        db.query(models.Complaint)
        .options(
            joinedload(models.Complaint.raised_by),
            joinedload(models.Complaint.actions).joinedload(models.Action.owner),
            joinedload(models.Complaint.comments).joinedload(models.Comment.author),
        )
        .filter(models.Complaint.id == complaint_id)
        .first()
    )
    if not c:
        raise HTTPException(404, "Complaint not found")
    return c


def _detail(c: models.Complaint) -> schemas.ComplaintDetail:
    out = schemas.ComplaintDetail.model_validate(c)
    out.allowed_transitions = models.COMPLAINT_TRANSITIONS.get(c.status, [])
    return out


@router.get("", response_model=schemas.ComplaintList)
def list_complaints(
    status: str | None = None,
    category: str | None = None,
    severity: str | None = None,
    work_type: str | None = None,
    overdue: bool | None = None,
    search: str | None = None,
    limit: int = Query(50, le=200),
    offset: int = 0,
    db: Session = Depends(get_db),
):
    q = db.query(models.Complaint).options(joinedload(models.Complaint.raised_by))
    if status:
        q = q.filter(models.Complaint.status == status)
    if category:
        q = q.filter(models.Complaint.category == category)
    if severity:
        q = q.filter(models.Complaint.severity == severity)
    if work_type:
        q = q.filter(models.Complaint.work_type == work_type)
    if search:
        like = f"%{search}%"
        q = q.filter(
            or_(
                models.Complaint.ref.ilike(like),
                models.Complaint.policy_ref.ilike(like),
                models.Complaint.description.ilike(like),
            )
        )
    items = q.order_by(models.Complaint.received_date.desc(), models.Complaint.id.desc()).all()
    # overdue is a computed property → filter in Python (dataset is small)
    if overdue is not None:
        items = [c for c in items if c.is_overdue == overdue]
    total = len(items)
    return {"total": total, "items": items[offset : offset + limit]}


@router.post("", response_model=schemas.ComplaintDetail, status_code=201)
def create_complaint(payload: schemas.ComplaintCreate, db: Session = Depends(get_db)):
    if not db.get(models.User, payload.raised_by_id):
        raise HTTPException(400, "raised_by_id: unknown user")
    c = models.Complaint(
        ref=_next_ref(db),
        policy_ref=payload.policy_ref.upper(),
        work_type=payload.work_type,
        category=payload.category,
        severity=payload.severity,
        description=payload.description,
        received_date=payload.received_date or date.today(),
        raised_by_id=payload.raised_by_id,
        status="Open",
    )
    db.add(c)
    db.commit()
    return _detail(_get_or_404(db, c.id))


@router.get("/{complaint_id}", response_model=schemas.ComplaintDetail)
def get_complaint(complaint_id: int, db: Session = Depends(get_db)):
    return _detail(_get_or_404(db, complaint_id))


@router.patch("/{complaint_id}", response_model=schemas.ComplaintDetail)
def update_complaint(
    complaint_id: int, payload: schemas.ComplaintUpdate, db: Session = Depends(get_db)
):
    c = _get_or_404(db, complaint_id)
    data = payload.model_dump(exclude_unset=True)

    # ---- workflow rules ----
    new_status = data.get("status")
    if new_status and new_status != c.status:
        allowed = models.COMPLAINT_TRANSITIONS.get(c.status, [])
        if new_status not in allowed:
            raise HTTPException(
                422, f"Invalid transition {c.status} → {new_status}. Allowed: {allowed}"
            )
        root_cause = data.get("root_cause", c.root_cause)
        if new_status == "Resolved" and not root_cause:
            raise HTTPException(422, "A root cause must be recorded before resolving.")
        if new_status == "Resolved":
            c.resolved_date = date.today()
        if new_status in ("Open", "Under Investigation"):
            c.resolved_date = None  # reopened

    for field, value in data.items():
        setattr(c, field, value)
    db.commit()
    return _detail(_get_or_404(db, complaint_id))


# ---------- comments ----------
@router.post("/{complaint_id}/comments", response_model=schemas.CommentOut, status_code=201)
def add_comment(
    complaint_id: int, payload: schemas.CommentCreate, db: Session = Depends(get_db)
):
    _get_or_404(db, complaint_id)
    if not db.get(models.User, payload.author_id):
        raise HTTPException(400, "author_id: unknown user")
    comment = models.Comment(complaint_id=complaint_id, **payload.model_dump())
    db.add(comment)
    db.commit()
    db.refresh(comment)
    return comment


# ---------- actions (nested create) ----------
@router.post("/{complaint_id}/actions", response_model=schemas.ActionOut, status_code=201)
def add_action(
    complaint_id: int, payload: schemas.ActionCreate, db: Session = Depends(get_db)
):
    c = _get_or_404(db, complaint_id)
    if c.status == "Closed":
        raise HTTPException(422, "Cannot add actions to a closed complaint.")
    if not db.get(models.User, payload.owner_id):
        raise HTTPException(400, "owner_id: unknown user")
    action = models.Action(complaint_id=complaint_id, **payload.model_dump())
    db.add(action)
    db.commit()
    db.refresh(action)
    return action
