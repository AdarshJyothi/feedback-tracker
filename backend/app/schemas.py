"""Pydantic request/response schemas."""
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from . import models


# ---------- users ----------
class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    role: str


# ---------- comments ----------
class CommentCreate(BaseModel):
    author_id: int
    text: str = Field(min_length=1, max_length=2000)


class CommentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    text: str
    created_at: datetime
    author: UserOut


# ---------- actions ----------
class ActionCreate(BaseModel):
    title: str = Field(min_length=3, max_length=160)
    description: str | None = None
    action_type: str = "Corrective"
    owner_id: int
    due_date: date | None = None

    @field_validator("action_type")
    @classmethod
    def valid_type(cls, v: str) -> str:
        if v not in models.ACTION_TYPES:
            raise ValueError(f"action_type must be one of {models.ACTION_TYPES}")
        return v


class ActionUpdate(BaseModel):
    status: str | None = None
    title: str | None = None
    description: str | None = None
    due_date: date | None = None
    owner_id: int | None = None

    @field_validator("status")
    @classmethod
    def valid_status(cls, v: str | None) -> str | None:
        if v is not None and v not in models.ACTION_STATUSES:
            raise ValueError(f"status must be one of {models.ACTION_STATUSES}")
        return v


class ActionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    complaint_id: int
    title: str
    description: str | None
    action_type: str
    status: str
    due_date: date | None
    completed_date: date | None
    created_at: datetime
    owner: UserOut
    is_overdue: bool


# ---------- complaints ----------
class ComplaintCreate(BaseModel):
    policy_ref: str = Field(min_length=3, max_length=20)
    work_type: str
    category: str
    severity: str
    description: str = Field(min_length=10, max_length=5000)
    received_date: date | None = None  # defaults to today
    raised_by_id: int

    @field_validator("work_type")
    @classmethod
    def valid_work_type(cls, v: str) -> str:
        if v not in models.WORK_TYPES:
            raise ValueError("unknown work_type")
        return v

    @field_validator("category")
    @classmethod
    def valid_category(cls, v: str) -> str:
        if v not in models.CATEGORIES:
            raise ValueError("unknown category")
        return v

    @field_validator("severity")
    @classmethod
    def valid_severity(cls, v: str) -> str:
        if v not in models.SEVERITIES:
            raise ValueError(f"severity must be one of {models.SEVERITIES}")
        return v


class ComplaintUpdate(BaseModel):
    """Partial update — status transitions are validated in the router."""
    status: str | None = None
    severity: str | None = None
    category: str | None = None
    root_cause: str | None = None
    description: str | None = None

    @field_validator("root_cause")
    @classmethod
    def valid_root_cause(cls, v: str | None) -> str | None:
        if v is not None and v not in models.ROOT_CAUSES:
            raise ValueError(f"root_cause must be one of {models.ROOT_CAUSES}")
        return v


class ComplaintOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    ref: str
    policy_ref: str
    work_type: str
    category: str
    severity: str
    status: str
    root_cause: str | None
    received_date: date
    resolved_date: date | None
    resolution_days: int | None
    is_overdue: bool
    raised_by: UserOut


class ComplaintDetail(ComplaintOut):
    description: str
    created_at: datetime
    updated_at: datetime
    actions: list[ActionOut]
    comments: list[CommentOut]
    allowed_transitions: list[str] = []


class ComplaintList(BaseModel):
    total: int
    items: list[ComplaintOut]


# ---------- stats ----------
class StatsSummary(BaseModel):
    total: int
    open: int
    under_investigation: int
    resolved: int
    closed: int
    overdue_open: int
    avg_resolution_days: float | None
    sla_met_pct: float | None
    open_actions: int
    overdue_actions: int


class CountItem(BaseModel):
    label: str
    count: int


class TrendPoint(BaseModel):
    week_start: date
    received: int
    resolved: int
