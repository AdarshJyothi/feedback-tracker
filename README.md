# Feedback Tracker

A complaint feedback and RCA (root cause analysis) action tracker for operations teams — FastAPI backend, vanilla JS frontend.

Built from hands-on experience with complaint handling and root-cause analysis in financial-services operations: the workflows, the discipline the tooling needs to enforce, and the analytics teams actually use.

---

## What it does

- **Log complaints** against policies, tagged by work type (surrenders, fund switches, death claims…), category, and severity
- **Enforced RCA workflow**: `Open → Under Investigation → Resolved → Closed`, with rules the API actually enforces — you cannot resolve a complaint without recording a root cause, invalid transitions are rejected, and closed complaints are read-only
- **Corrective & preventive actions** per complaint, with owners, due dates, and overdue tracking
- **Comment threads** on every complaint for the investigation trail
- **Analytics dashboard**: received-vs-resolved weekly trend, complaints by category, root-cause Pareto, severity mix, top work types, SLA compliance (28-day target), average resolution time
- **Filter & search** across refs, policy numbers, and descriptions

Demo mode: pick which seeded user you're acting as — no login. (JWT auth is on the roadmap; my [Arth](https://github.com/AdarshJyothi/Arth) project implements it fully.)

## Tech stack

| Layer | Choice |
|---|---|
| API | Python, FastAPI, Pydantic v2 |
| Database | SQLite via SQLAlchemy 2.0 (swap to PostgreSQL = change one URL) |
| Frontend | HTML, CSS, vanilla JavaScript, Chart.js (CDN, no build step) |
| Data | Self-seeding — 78 realistic complaints generated on first startup |

## Run it

Backend (from `backend/`):

```bash
pip install -r requirements.txt
cd backend
python -m uvicorn app.main:app --reload --port 8000
```

Frontend (from `frontend/`):

```bash
python -m http.server 8001
```

Open <http://localhost:8001>. Interactive API docs at <http://localhost:8000/docs>.

## API overview

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/v1/complaints` | List with filters (`status`, `category`, `severity`, `work_type`, `overdue`, `search`) |
| POST | `/api/v1/complaints` | Log a complaint |
| GET | `/api/v1/complaints/{id}` | Detail incl. actions, comments, allowed transitions |
| PATCH | `/api/v1/complaints/{id}` | Update / transition status (workflow-validated) |
| POST | `/api/v1/complaints/{id}/actions` | Add an RCA action |
| POST | `/api/v1/complaints/{id}/comments` | Add a comment |
| PATCH | `/api/v1/actions/{id}` | Update action status/owner/due date |
| GET | `/api/v1/stats/summary` | KPI card data (open, overdue, SLA %, avg resolution) |
| GET | `/api/v1/stats/by-category` · `by-root-cause` · `by-severity` · `by-work-type` · `trend` | Dashboard charts |

## Design notes

- **Workflow rules live in the API, not the UI** — the frontend renders whatever transitions `allowed_transitions` returns, so the rules cannot be bypassed
- **Root cause is mandatory before resolution** — the RCA discipline the original VBA tool was built to encourage
- **Computed properties** (`is_overdue`, `resolution_days`) are derived server-side so every client sees the same logic
- Seed data is deterministic (fixed RNG seed) so the demo dashboard looks the same on every fresh clone

## Roadmap

- JWT authentication (register/login, roles)
- CSV export of complaints and actions
- Email notifications for overdue actions
- PostgreSQL + Alembic migrations
