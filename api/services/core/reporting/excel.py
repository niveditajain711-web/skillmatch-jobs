"""Excel report generation."""

from __future__ import annotations

from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from api.services.core.models_dto import ScoredJob


def write_excel_report(
    scored_jobs: list[ScoredJob],
    *,
    output_dir: str | Path,
    filename_prefix: str,
    keywords: str,
    resume_skills: list[str],
    meta: dict[str, Any] | None = None,
) -> Path:
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    path = out_dir / f"{filename_prefix}_{stamp}.xlsx"

    matches_rows = []
    gap_counter: Counter[str] = Counter()
    for item in scored_jobs:
        job = item.job
        matches_rows.append(
            {
                "score": item.score,
                "title": job.title,
                "company": job.company,
                "location": job.location,
                "source": job.source,
                "remote": job.is_remote,
                "posted_at": job.posted_at.isoformat() if job.posted_at else "",
                "url": job.url,
                "matched_keywords": ", ".join(item.matched_keywords),
                "missing_keywords": ", ".join(item.missing_keywords),
                "title_match": item.title_match,
            }
        )
        for skill in item.missing_keywords:
            gap_counter[skill] += 1

    meta = meta or {}
    scores = [s.score for s in scored_jobs]
    summary_rows = [
        {"metric": "generated_at", "value": datetime.now().isoformat(timespec="seconds")},
        {"metric": "keywords", "value": keywords},
        {"metric": "jobs_scored", "value": len(scored_jobs)},
        {"metric": "avg_score", "value": round(sum(scores) / len(scores), 2) if scores else 0},
        {"metric": "max_score", "value": max(scores) if scores else 0},
        {"metric": "min_score", "value": min(scores) if scores else 0},
        {"metric": "resume_skills", "value": ", ".join(resume_skills)},
        {"metric": "jobs_fetched", "value": meta.get("jobs_fetched", "")},
        {"metric": "sources_used", "value": meta.get("sources_used", "")},
        {"metric": "mode", "value": meta.get("mode", "normal")},
    ]

    gaps_rows = [
        {
            "skill": skill,
            "jobs_missing_count": count,
            "in_resume": skill in set(resume_skills),
        }
        for skill, count in gap_counter.most_common()
    ]

    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        pd.DataFrame(summary_rows).to_excel(writer, sheet_name="Summary", index=False)
        pd.DataFrame(matches_rows).to_excel(writer, sheet_name="Matches", index=False)
        pd.DataFrame(gaps_rows).to_excel(writer, sheet_name="Gaps", index=False)

    return path