"""Analytics endpoints powering the dashboard (RCA-style views)."""
from collections import Counter
from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db

router = APIRouter(prefix="/api/v1/stats", tags=["stats"])


@router.get("/summary", response_model=schemas.StatsSummary)
def summary(db: Session = Depends(get_db)):
    complaints = db.query(models.Complaint).all()
    by_status = Counter(c.status for c in complaints)

    resolved = [c for c in complaints if c.resolution_days is not None]
    avg_res = (
        round(sum(c.resolution_days for c in resolved) / len(resolved), 1)
        if resolved
        else None
    )
    sla_met = (
        round(
            100 * sum(1 for c in resolved if c.resolution_days <= models.SLA_DAYS) / len(resolved),
            1,
        )
        if resolved
        else None
    )
    overdue_open = sum(
        1 for c in complaints if c.status in ("Open", "Under Investigation") and c.is_overdue
    )

    actions = db.query(models.Action).all()
    open_actions = sum(1 for a in actions if a.status in ("Open", "In Progress"))
    overdue_actions = sum(1 for a in actions if a.is_overdue)

    return schemas.StatsSummary(
        total=len(complaints),
        open=by_status.get("Open", 0),
        under_investigation=by_status.get("Under Investigation", 0),
        resolved=by_status.get("Resolved", 0),
        closed=by_status.get("Closed", 0),
        overdue_open=overdue_open,
        avg_resolution_days=avg_res,
        sla_met_pct=sla_met,
        open_actions=open_actions,
        overdue_actions=overdue_actions,
    )


def _grouped(db: Session, column) -> list[schemas.CountItem]:
    rows = (
        db.query(column, func.count(models.Complaint.id))
        .group_by(column)
        .order_by(func.count(models.Complaint.id).desc())
        .all()
    )
    return [schemas.CountItem(label=r[0], count=r[1]) for r in rows if r[0]]


@router.get("/by-category", response_model=list[schemas.CountItem])
def by_category(db: Session = Depends(get_db)):
    return _grouped(db, models.Complaint.category)


@router.get("/by-root-cause", response_model=list[schemas.CountItem])
def by_root_cause(db: Session = Depends(get_db)):
    """Pareto view — which root causes drive most complaints (investigated ones only)."""
    return _grouped(db, models.Complaint.root_cause)


@router.get("/by-severity", response_model=list[schemas.CountItem])
def by_severity(db: Session = Depends(get_db)):
    rows = _grouped(db, models.Complaint.severity)
    order = {s: i for i, s in enumerate(models.SEVERITIES)}
    return sorted(rows, key=lambda r: order.get(r.label, 99))


@router.get("/by-work-type", response_model=list[schemas.CountItem])
def by_work_type(db: Session = Depends(get_db)):
    return _grouped(db, models.Complaint.work_type)[:10]


@router.get("/trend", response_model=list[schemas.TrendPoint])
def trend(weeks: int = Query(12, ge=4, le=26), db: Session = Depends(get_db)):
    """Weekly received vs resolved counts for the last N weeks."""
    today = date.today()
    start_of_week = today - timedelta(days=today.weekday())
    buckets: list[schemas.TrendPoint] = []
    complaints = db.query(models.Complaint).all()

    for i in range(weeks - 1, -1, -1):
        ws = start_of_week - timedelta(weeks=i)
        we = ws + timedelta(days=7)
        received = sum(1 for c in complaints if ws <= c.received_date < we)
        resolved = sum(
            1 for c in complaints if c.resolved_date and ws <= c.resolved_date < we
        )
        buckets.append(schemas.TrendPoint(week_start=ws, received=received, resolved=resolved))
    return buckets
