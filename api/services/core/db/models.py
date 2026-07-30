"""SQLAlchemy ORM models."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class SearchRun(Base):
    __tablename__ = "search_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    keywords: Mapped[str] = mapped_column(String(512), default="")
    config_snapshot: Mapped[dict] = mapped_column(JSONB, default=dict)
    status: Mapped[str] = mapped_column(String(32), default="running")
    resume_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    resume_skills: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    jobs_fetched: Mapped[int] = mapped_column(Integer, default=0)
    jobs_scored: Mapped[int] = mapped_column(Integer, default=0)
    report_path: Mapped[str | None] = mapped_column(String(512), nullable=True)

    scores: Mapped[list[JobScore]] = relationship(back_populates="search_run")
    raw_responses: Mapped[list[RawResponse]] = relationship(back_populates="search_run")


class RawResponse(Base):
    __tablename__ = "raw_responses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    search_run_id: Mapped[int | None] = mapped_column(
        ForeignKey("search_runs.id"), nullable=True
    )
    source: Mapped[str] = mapped_column(String(64), index=True)
    request_params: Mapped[dict] = mapped_column(JSONB, default=dict)
    response_body: Mapped[dict | list] = mapped_column(JSONB, default=dict)
    cache_key: Mapped[str | None] = mapped_column(String(128), index=True, nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    search_run: Mapped[SearchRun | None] = relationship(back_populates="raw_responses")


class JobRecord(Base):
    __tablename__ = "jobs"
    __table_args__ = (UniqueConstraint("source", "external_id", name="uq_jobs_source_ext"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source: Mapped[str] = mapped_column(String(64), index=True)
    external_id: Mapped[str] = mapped_column(String(255))
    title: Mapped[str] = mapped_column(String(512))
    company: Mapped[str] = mapped_column(String(255), default="")
    location: Mapped[str] = mapped_column(String(255), default="")
    url: Mapped[str] = mapped_column(String(1024), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_remote: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    raw_json: Mapped[dict] = mapped_column(JSONB, default=dict)
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    scores: Mapped[list[JobScore]] = relationship(back_populates="job")


class JobScore(Base):
    __tablename__ = "job_scores"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    search_run_id: Mapped[int] = mapped_column(ForeignKey("search_runs.id"), index=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"), index=True)
    score: Mapped[float] = mapped_column(Float, default=0.0)
    matched_keywords: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    missing_keywords: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    search_run: Mapped[SearchRun] = relationship(back_populates="scores")
    job: Mapped[JobRecord] = relationship(back_populates="scores")