"""Seed the database with realistic demo data (idempotent — only runs when empty)."""
import random
from datetime import date, timedelta

from sqlalchemy.orm import Session

from . import models

DESCRIPTIONS = {
    "Delay in Processing": [
        "Customer chased three times for a {wt} request submitted over four weeks ago; still showing as pending in BaNCS.",
        "{wt} not actioned within the published service standard; customer states nobody called back as promised.",
        "IFA escalated on behalf of client — {wt} outstanding beyond SLA with no holding letter issued.",
    ],
    "Incorrect Payment": [
        "Payment issued for the wrong amount on a {wt}; customer received £312.40 less than quoted.",
        "Duplicate payment released on {wt}; recovery process now required, customer unhappy about contact.",
        "Tax deducted at the wrong rate on {wt} payout; customer requesting corrected certificate and shortfall.",
    ],
    "Poor Communication": [
        "Customer states letters about their {wt} contradicted each other and the helpline gave a third version.",
        "No acknowledgement sent for {wt} request; customer only learned status after calling twice.",
        "Bereaved family member told different requirements by two agents during a {wt}; formal complaint raised.",
    ],
    "Documentation Error": [
        "Statement issued for {wt} shows the wrong policyholder name; customer concerned about data accuracy.",
        "Discharge form for {wt} referenced an outdated address despite an address change confirmed last month.",
        "{wt} pack sent with a page missing; customer had to request a reissue, delaying completion.",
    ],
    "Process Not Followed": [
        "Verification step skipped on {wt}; case had to be reworked and customer asked to resubmit documents.",
        "{wt} processed without the required second check, resulting in a rework and a delayed completion.",
        "Complaint handler did not follow the vulnerable-customer procedure while handling a {wt} query.",
    ],
    "System Error": [
        "BaNCS workflow stuck in 'awaiting index' for {wt}; item invisible to the processing queue for 9 days.",
        "System generated a duplicate case for {wt}, causing conflicting letters to be issued.",
        "Online portal showed failed submission for {wt} although the request was received; customer resubmitted twice.",
    ],
    "Data Quality Issue": [
        "Fund values on the {wt} confirmation did not match the projection sent two weeks earlier.",
        "Date of birth recorded incorrectly, blocking the {wt} and triggering additional ID requirements.",
        "National Insurance number mismatch flagged during {wt}; source of the discrepancy unclear to customer.",
    ],
}

ACTION_TEMPLATES = [
    ("Update procedure document", "Revise the {wt} procedure to close the identified gap.", "Preventive"),
    ("Deliver targeted refresher training", "Short refresher for the team covering the failure point seen in this case.", "Preventive"),
    ("Raise system fix request", "Log a change request with the platform team and track to resolution.", "Corrective"),
    ("Issue corrected documentation", "Send corrected letter/statement to the customer with an apology.", "Corrective"),
    ("Add checkpoint to QC sample", "Include this scenario in the weekly QC sampling for one month.", "Preventive"),
    ("Recover / reissue payment", "Arrange recovery of the incorrect amount and reissue at the correct value.", "Corrective"),
]

COMMENTS = [
    "Called the customer to acknowledge and set expectations — holding letter issued.",
    "Pulled the BaNCS audit trail; timeline attached to the case file.",
    "Discussed at the daily huddle; similar case spotted last week, monitoring for a pattern.",
    "Root cause confirmed with the SME — updating the case record.",
    "Customer accepted the resolution and apology. Awaiting closure checks.",
    "Escalated to team lead due to potential vulnerable-customer flag.",
]

USERS = [
    ("Priya Nair", "Senior Analyst"),
    ("James Wallace", "Analyst"),
    ("Aoife Kennedy", "Team Lead"),
    ("Ravi Menon", "Analyst"),
    ("Fiona Stewart", "Quality Checker"),
    ("Tom Brady", "Analyst"),
]

CATEGORY_WEIGHTS = [28, 16, 18, 12, 10, 9, 7]  # matches models.CATEGORIES order
SEVERITY_WEIGHTS = [30, 40, 22, 8]
ROOT_CAUSE_WEIGHTS = [30, 20, 22, 12, 8, 8]


def seed(db: Session) -> None:
    if db.query(models.User).first():
        return  # already seeded

    rng = random.Random(42)

    users = [models.User(name=n, role=r) for n, r in USERS]
    db.add_all(users)
    db.flush()

    today = date.today()
    n_complaints = 78
    for i in range(1, n_complaints + 1):
        age_days = int(rng.triangular(0, 180, 40))
        received = today - timedelta(days=age_days)
        category = rng.choices(models.CATEGORIES, weights=CATEGORY_WEIGHTS)[0]
        severity = rng.choices(models.SEVERITIES, weights=SEVERITY_WEIGHTS)[0]
        work_type = rng.choice(models.WORK_TYPES)
        desc = rng.choice(DESCRIPTIONS[category]).format(wt=work_type.lower())

        c = models.Complaint(
            ref=f"CMP-{i:04d}",
            policy_ref=f"SW{rng.randint(10_000_000, 99_999_999)}",
            work_type=work_type,
            category=category,
            severity=severity,
            description=desc,
            received_date=received,
            raised_by_id=rng.choice(users).id,
            status="Open",
        )

        # Older complaints are progressively more likely to be worked/resolved
        p_progress = min(0.95, age_days / 60 + 0.15)
        if rng.random() < p_progress:
            c.status = "Under Investigation"
            c.root_cause = rng.choices(models.ROOT_CAUSES, weights=ROOT_CAUSE_WEIGHTS)[0]
            if rng.random() < min(0.9, age_days / 75):
                res_days = int(rng.triangular(3, 45, 18))
                resolved = received + timedelta(days=res_days)
                if resolved <= today:
                    c.status = "Resolved"
                    c.resolved_date = resolved
                    if rng.random() < 0.7 and (today - resolved).days > 7:
                        c.status = "Closed"
        db.add(c)
        db.flush()

        # comments
        for _ in range(rng.randint(0, 3)):
            db.add(
                models.Comment(
                    complaint_id=c.id,
                    author_id=rng.choice(users).id,
                    text=rng.choice(COMMENTS),
                )
            )

        # actions for investigated/resolved complaints
        if c.status != "Open":
            for _ in range(rng.randint(0, 2)):
                title, adesc, atype = rng.choice(ACTION_TEMPLATES)
                due = received + timedelta(days=rng.randint(10, 40))
                a = models.Action(
                    complaint_id=c.id,
                    title=title,
                    description=adesc.format(wt=c.work_type.lower()),
                    action_type=atype,
                    owner_id=rng.choice(users).id,
                    due_date=due,
                    status="Open",
                )
                if c.status in ("Resolved", "Closed") and rng.random() < 0.75:
                    a.status = rng.choice(["Done", "Verified"])
                    a.completed_date = min(due + timedelta(days=rng.randint(-5, 10)), today)
                elif rng.random() < 0.5:
                    a.status = "In Progress"
                db.add(a)

    db.commit()
