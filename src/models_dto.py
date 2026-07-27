"""Shared data transfer objects used across layers."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class Job:
    source: str
    external_id: str
    title: str
    company: str
    location: str
    url: str
    description: str
    posted_at: datetime | None = None
    is_remote: bool | None = None
    raw_json: dict[str, Any] = field(default_factory=dict)


@dataclass
class ScoredJob:
    job: Job
    score: float
    matched_keywords: list[str] = field(default_factory=list)
    missing_keywords: list[str] = field(default_factory=list)
    title_match: float = 0.0


@dataclass
class ResumeData:
    text: str
    skills: list[str]
    source_path: str