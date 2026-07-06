"""Reference data for the frontend (dropdowns, demo user picker)."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db

router = APIRouter(prefix="/api/v1/meta", tags=["meta"])


@router.get("/users", response_model=list[schemas.UserOut])
def list_users(db: Session = Depends(get_db)):
    return db.query(models.User).order_by(models.User.name).all()


@router.get("/options")
def options():
    return {
        "work_types": models.WORK_TYPES,
        "categories": models.CATEGORIES,
        "severities": models.SEVERITIES,
        "root_causes": models.ROOT_CAUSES,
        "complaint_statuses": models.COMPLAINT_STATUSES,
        "action_statuses": models.ACTION_STATUSES,
        "action_types": models.ACTION_TYPES,
        "sla_days": models.SLA_DAYS,
    }
