"""Remotive public API fetcher."""

from __future__ import annotations

from typing import Any

import requests

from api.services.core.fetchers.base import BaseFetcher, parse_datetime, truncate
from api.services.core.models_dto import Job

REMOTIVE_URL = "https://remotive.com/api/remote-jobs"


class RemotiveFetcher(BaseFetcher):
    name = "remotive"

    def fetch(self) -> list[Job]:
        search_cfg = self.config.get("search", {})
        keywords = search_cfg.get("keywords") or []
        # Remotive search is fragile with long keyword strings — use top skills only.
        primary = [str(k).strip() for k in keywords[:2] if str(k).strip()]
        search = " ".join(primary).strip()
        max_results = int(search_cfg.get("max_results_per_source", 50))

        params: dict[str, Any] = {}
        if search:
            params["search"] = search
        params["limit"] = max(max_results, 50)

        def _do_fetch():
            resp = requests.get(REMOTIVE_URL, params=params, timeout=45)
            resp.raise_for_status()
            return resp.json()

        body = self._load_or_fetch_json(params, _do_fetch)
        jobs_data = body.get("jobs", []) if isinstance(body, dict) else []

        tokens = [str(k).lower().strip() for k in keywords if str(k).strip()]
        jobs: list[Job] = []
        for item in jobs_data:
            job = self._to_job(item)
            if not job:
                continue
            if tokens:
                blob = f"{job.title}\n{job.description}".lower()
                if not any(tok in blob for tok in tokens):
                    continue
            jobs.append(job)
            if len(jobs) >= max_results:
                break
        return jobs

    def _to_job(self, item: dict[str, Any]) -> Job | None:
        job_id = str(item.get("id") or "")
        title = (item.get("title") or "").strip()
        if not job_id or not title:
            return None
        return Job(
            source=self.name,
            external_id=job_id,
            title=title,
            company=(item.get("company_name") or "").strip(),
            location=(item.get("candidate_required_location") or "").strip(),
            url=(item.get("url") or "").strip(),
            description=truncate(item.get("description") or ""),
            posted_at=parse_datetime(item.get("publication_date")),
            is_remote=True,
            raw_json=item,
        )