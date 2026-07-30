"""Pydantic schemas for API requests and responses."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = "ok"
    app: str = "SkillMatch Jobs"


class SearchConfigInput(BaseModel):
    keywords: list[str] | None = None
    location: str | None = None
    remote_only: bool | None = None
    countries: list[str] | None = None
    max_results_per_source: int | None = None
    posted_within_days: int | None = None
    max_pages: int | None = None


class SourcesInput(BaseModel):
    jsearch: bool | None = None
    remotive: bool | None = None
    arbeitnow: bool | None = None


class ScoringInput(BaseModel):
    must_have_weight: float | None = None
    nice_to_have_weight: float | None = None
    title_weight: float | None = None
    min_score_to_save: float | None = None


class CreateRunRequest(BaseModel):
    search: SearchConfigInput | None = None
    sources: SourcesInput | None = None
    scoring: ScoringInput | None = None
    refresh: bool = False
    rescore_only: bool = False


class RunResponse(BaseModel):
    id: int
    started_at: datetime | None
    keywords: str
    status: str
    jobs_fetched: int
    jobs_scored: int
    report_path: str | None
    resume_skills: list[str] | None = None


class CreateRunResponse(BaseModel):
    run_id: int
    status: str
    message: str


class JobScoreResponse(BaseModel):
    job_id: int
    score: float
    matched_keywords: list[str]
    missing_keywords: list[str]
    title: str
    company: str
    location: str
    source: str
    url: str
    is_remote: bool | None
    posted_at: datetime | None


class JobDetailResponse(BaseModel):
    job_id: int
    run_id: int
    score: float
    matched_keywords: list[str]
    missing_keywords: list[str]
    title_match: float | None = None
    title: str
    company: str
    location: str
    source: str
    url: str
    description: str
    is_remote: bool | None
    posted_at: datetime | None


class ResumeResponse(BaseModel):
    source_path: str
    skills: list[str]
    text_preview: str


class GapItem(BaseModel):
    skill: str
    jobs_missing_count: int


class DashboardResponse(BaseModel):
    latest_run: RunResponse | None
    top_matches: list[JobScoreResponse]
    avg_score: float | None
    gaps: list[GapItem]


class SettingsResponse(BaseModel):
    search: dict[str, Any]
    sources: dict[str, Any]
    scoring: dict[str, Any]
    cache: dict[str, Any]
