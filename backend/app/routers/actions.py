"""Standalone action updates (status, ownership, due dates)."""
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from .. import models, schemas
from ..database import get_db

router = APIRouter(prefix="/api/v1/actions", tags=["actions"])


@router.get("", response_model=list[schemas.ActionOut])
def list_actions(
    status: str | None = None,
    overdue_only: bool = False,
    db: Session = Depends(get_db),
):
    q = db.query(models.Action).options(joinedload(models.Action.owner))
    if status:
        q = q.filter(models.Action.status == status)
    items = q.order_by(models.Action.due_date.is_(None), models.Action.due_date).all()
    if overdue_only:
        items = [a for a in items if a.is_overdue]
    return items


@router.patch("/{action_id}", response_model=schemas.ActionOut)
def update_action(action_id: int, payload: schemas.ActionUpdate, db: Session = Depends(get_db)):
    action = (
        db.query(models.Action)
        .options(joinedload(models.Action.owner))
        .filter(models.Action.id == action_id)
        .first()
    )
    if not action:
        raise HTTPException(404, "Action not found")

    data = payload.model_dump(exclude_unset=True)
    if "owner_id" in data and not db.get(models.User, data["owner_id"]):
        raise HTTPException(400, "owner_id: unknown user")

    new_status = data.get("status")
    if new_status and new_status != action.status:
        if new_status in ("Done", "Verified") and not action.completed_date:
            action.completed_date = date.today()
        if new_status in ("Open", "In Progress"):
            action.completed_date = None

    for field, value in data.items():
        setattr(action, field, value)
    db.commit()
    db.refresh(action)
    return action
