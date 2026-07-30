"""Arbeitnow public API fetcher."""

from __future__ import annotations

from typing import Any
import requests

from api.services.core.fetchers.base import BaseFetcher, parse_datetime, truncate
from api.services.core.models_dto import Job

ARBEITNOW_URL = "https://www.arbeitnow.com/api/job-board-api"


class ArbeitnowFetcher(BaseFetcher):
    name = "arbeitnow"

    def fetch(self) -> list[Job]:
        search_cfg = self.config.get("search", {})
        keywords = search_cfg.get("keywords") or []
        search = " ".join(str(k) for k in keywords).strip()
        max_results = int(search_cfg.get("max_results_per_source", 30))
        remote_only = bool(search_cfg.get("remote_only"))

        params: dict[str, Any] = {"page": 1}
        if search:
            # Arbeitnow uses query string search via full URL sometimes;
            # keep page param and filter client-side for reliability.
            params["search"] = search

        def _do_fetch():
            # Public endpoint returns latest jobs; filter locally by keywords.
            resp = requests.get(ARBEITNOW_URL, params={"page": 1}, timeout=45)
            resp.raise_for_status()
            return resp.json()

        # Cache key includes search/remote so different configs don't collide
        cache_params = {"page": 1, "search": search, "remote_only": remote_only}
        body = self._load_or_fetch_json(cache_params, _do_fetch)
        data = body.get("data", []) if isinstance(body, dict) else []

        tokens = [t.lower() for t in keywords if str(t).strip()]
        jobs: list[Job] = []
        for item in data:
            if remote_only and not item.get("remote"):
                continue
            blob = " ".join(
                [
                    str(item.get("title") or ""),
                    str(item.get("description") or ""),
                    " ".join(item.get("tags") or []),
                    " ".join(item.get("job_types") or []),
                ]
            ).lower()
            if tokens and not all(tok in blob for tok in tokens):
                # soft filter: require at least one keyword if all is too strict
                if not any(tok in blob for tok in tokens):
                    continue
            job = self._to_job(item)
            if job:
                jobs.append(job)
            if len(jobs) >= max_results:
                break
        return jobs

    def _to_job(self, item: dict[str, Any]) -> Job | None:
        slug = str(item.get("slug") or item.get("url") or "")
        title = (item.get("title") or "").strip()
        if not slug or not title:
            return None
        return Job(
            source=self.name,
            external_id=slug,
            title=title,
            company=(item.get("company_name") or "").strip(),
            location=(item.get("location") or "").strip(),
            url=(item.get("url") or "").strip(),
            description=truncate(item.get("description") or ""),
            posted_at=parse_datetime(item.get("created_at")),
            is_remote=bool(item.get("remote")) if item.get("remote") is not None else None,
            raw_json=item,
        )