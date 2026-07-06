"""SQLAlchemy models for the complaint feedback tracker."""
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base

# ---- domain vocabularies (validated in schemas, reused by seed + frontend meta) ----
SEVERITIES = ["Low", "Medium", "High", "Critical"]
COMPLAINT_STATUSES = ["Open", "Under Investigation", "Resolved", "Closed"]
ACTION_STATUSES = ["Open", "In Progress", "Done", "Verified"]
ACTION_TYPES = ["Corrective", "Preventive"]
CATEGORIES = [
    "Delay in Processing",
    "Incorrect Payment",
    "Poor Communication",
    "Documentation Error",
    "Process Not Followed",
    "System Error",
    "Data Quality Issue",
]
ROOT_CAUSES = [
    "Process Gap",
    "Training Gap",
    "Human Error",
    "System Limitation",
    "Third-Party Dependency",
    "Unclear Guidance",
]
WORK_TYPES = [
    "Direct Debit Mandate",
    "Policy Surrender",
    "Fund Switch",
    "Death Claim",
    "Address Change",
    "Annuity Payment",
    "Policy Valuation",
    "Beneficiary Update",
    "Premium Collection",
    "Withdrawal Request",
    "Transfer Out",
    "Retirement Claim",
    "Bonus Statement",
    "Chargeable Event Certificate",
    "Complaint Acknowledgement",
]

# Allowed status transitions (workflow rules enforced in the API)
COMPLAINT_TRANSITIONS = {
    "Open": ["Under Investigation"],
    "Under Investigation": ["Resolved", "Open"],
    "Resolved": ["Closed", "Under Investigation"],
    "Closed": [],
}

SLA_DAYS = 28  # target: complaint resolved within 28 calendar days


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    role: Mapped[str] = mapped_column(String(50), nullable=False, default="Analyst")

    complaints_raised: Mapped[list["Complaint"]] = relationship(back_populates="raised_by")


class Complaint(Base):
    __tablename__ = "complaints"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ref: Mapped[str] = mapped_column(String(12), unique=True, index=True)  # CMP-0001
    policy_ref: Mapped[str] = mapped_column(String(20), nullable=False)
    work_type: Mapped[str] = mapped_column(String(60), index=True)
    category: Mapped[str] = mapped_column(String(60), index=True)
    severity: Mapped[str] = mapped_column(String(20), index=True)
    status: Mapped[str] = mapped_column(String(30), index=True, default="Open")
    description: Mapped[str] = mapped_column(Text, nullable=False)
    root_cause: Mapped[str | None] = mapped_column(String(60), nullable=True)
    received_date: Mapped[date] = mapped_column(Date, nullable=False)
    resolved_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    raised_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    raised_by: Mapped["User"] = relationship(back_populates="complaints_raised")
    actions: Mapped[list["Action"]] = relationship(
        back_populates="complaint", cascade="all, delete-orphan"
    )
    comments: Mapped[list["Comment"]] = relationship(
        back_populates="complaint", cascade="all, delete-orphan"
    )

    @property
    def resolution_days(self) -> int | None:
        if self.resolved_date:
            return (self.resolved_date - self.received_date).days
        return None

    @property
    def is_overdue(self) -> bool:
        """Open past SLA, or resolved late."""
        if self.resolved_date:
            return (self.resolved_date - self.received_date).days > SLA_DAYS
        return (date.today() - self.received_date).days > SLA_DAYS


class Action(Base):
    __tablename__ = "actions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    complaint_id: Mapped[int] = mapped_column(ForeignKey("complaints.id"), index=True)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    action_type: Mapped[str] = mapped_column(String(20), default="Corrective")
    status: Mapped[str] = mapped_column(String(20), default="Open", index=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    completed_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    complaint: Mapped["Complaint"] = relationship(back_populates="actions")
    owner: Mapped["User"] = relationship()

    @property
    def is_overdue(self) -> bool:
        return (
            self.due_date is not None
            and self.status in ("Open", "In Progress")
            and self.due_date < date.today()
        )


class Comment(Base):
    __tablename__ = "comments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    complaint_id: Mapped[int] = mapped_column(ForeignKey("complaints.id"), index=True)
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    complaint: Mapped["Complaint"] = relationship(back_populates="comments")
    author: Mapped["User"] = relationship()
