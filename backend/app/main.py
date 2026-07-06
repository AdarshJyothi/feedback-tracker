"""Feedback Tracker API.

A complaint feedback & RCA action tracker for operations teams.
Originally built as an Excel VBA tool; rebuilt in Python with FastAPI.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import models  # noqa: F401 — ensure models are registered
from .database import Base, SessionLocal, engine
from .routers import actions, complaints, meta, stats
from .seed import seed

app = FastAPI(
    title="Feedback Tracker API",
    version="1.0.0",
    description="Complaint feedback tracking with RCA workflow and analytics.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # demo app — restrict in production
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup() -> None:
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        seed(db)


app.include_router(meta.router)
app.include_router(complaints.router)
app.include_router(actions.router)
app.include_router(stats.router)


@app.get("/api/v1/health", tags=["meta"])
def health():
    return {"status": "ok"}
