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
    years_of_experience: float | None = None
    experience_min: float | None = None
    experience_max: float | None = None
    keep_unknown_experience: bool | None = None
    experience_tolerance: float | None = None
    keep_remote_worldwide: bool | None = None
    keep_unknown_location: bool | None = None
    strict_country_filter: bool | None = None


class SourcesInput(BaseModel):
    jsearch: bool | None = None
    remotive: bool | None = None
    arbeitnow: bool | None = None
    company_boards: bool | None = None


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


class SearchSettingsUpdate(BaseModel):
    """UI-editable search prefs persisted to config.yaml."""

    years_of_experience: float | None = None
    experience_min: float | None = None
    experience_max: float | None = None
    keep_unknown_experience: bool | None = None
    experience_tolerance: float | None = None
    remote_only: bool | None = None
    countries: list[str] | None = None
    max_pages: int | None = None
    posted_within_days: int | None = None
    max_results_per_source: int | None = None
    jsearch_max_query_variants: int | None = None
    cache_ttl_hours: int | None = None
    cache_enabled: bool | None = None
    clear_years_of_experience: bool = False
    clear_experience_min: bool = False
    clear_experience_max: bool = False


class AnalyzeJobRequest(BaseModel):
    force: bool = False


class BatchAnalyzeRequest(BaseModel):
    max_jobs: int | None = None
    min_score: float | None = None
    force: bool = False


class BatchAnalyzeStatusResponse(BaseModel):
    run_id: int
    status: str
    total: int = 0
    analyzed: int = 0
    skipped_existing: int = 0
    errors: list[str] = Field(default_factory=list)
    job_ids: list[int] = Field(default_factory=list)
    force: bool = False
    min_score: float | None = None
    max_jobs: int | None = None


class ApplicationDraftResponse(BaseModel):
    id: int
    search_run_id: int
    job_id: int
    fit_score: float
    decision: str
    reasons: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    red_flags: list[str] = Field(default_factory=list)
    tailored_bullets: list[str] = Field(default_factory=list)
    cover_letter: str = ""
    form_answers: dict[str, Any] = Field(default_factory=dict)
    provider: str = ""
    model: str = ""
    created_at: datetime | None = None
    updated_at: datetime | None = None
    queue_status: str | None = None
    queue_id: int | None = None
    user_notes: str | None = None
    # enriched for queue list
    title: str | None = None
    company: str | None = None
    location: str | None = None
    url: str | None = None
    source: str | None = None
    clipboard_pack: str | None = None


class QueueUpdateRequest(BaseModel):
    status: str
    user_notes: str | None = None


class AgentStatusResponse(BaseModel):
    enabled: bool
    provider: str
    model: str
    require_human_approval: bool = True
    max_jobs_per_run: int = 15
    min_keyword_score: float = 40
    browser_assist_enabled: bool = True
    schedule_enabled: bool = False
    schedule_daily_at: str | None = None


class BrowserAssistStatusResponse(BaseModel):
    queue_id: int
    status: str
    ats: str = "generic"
    url: str | None = None
    filled: list[str] = Field(default_factory=list)
    skipped: list[str] = Field(default_factory=list)
    message: str = ""
    error: str | None = None


class ScheduleStatusResponse(BaseModel):
    enabled: bool = False
    status: str = "idle"
    last_run_at: str | None = None
    last_search_run_id: int | None = None
    last_error: str | None = None
    next_run_at: str | None = None
    triggered_by: str | None = None
