"""JD fit analysis + application draft generation."""

from __future__ import annotations

from typing import Any

from api.services.agent.llm import LLMClient, LLMError, get_llm_client

SYSTEM_PROMPT = """You are an expert job-application coach helping a candidate apply honestly.
Rules:
- Use ONLY facts from the resume. Do not invent employers, metrics, degrees, or skills.
- Prefer honest gaps over fabrication.
- Match seniority to the candidate's stated experience.
- Return STRICT JSON only (no markdown outside JSON).
JSON schema:
{
  "fit_score": number 0-100,
  "decision": "apply" | "maybe" | "skip",
  "reasons": string[],
  "gaps": string[],
  "red_flags": string[],
  "tailored_bullets": string[],
  "cover_letter": string,
  "form_answers": {
    "years_of_experience": string,
    "current_location": string,
    "willing_to_relocate": string,
    "notice_period": string,
    "why_company": string,
    "why_role": string
  }
}
cover_letter: 3 short paragraphs, professional, specific to this role/company.
tailored_bullets: 3-5 bullets mapping resume evidence to JD needs.
"""


def _truncate(text: str, limit: int) -> str:
    text = text or ""
    return text if len(text) <= limit else text[:limit] + "\n…[truncated]"


def analyze_job_fit(
    *,
    resume_text: str,
    resume_skills: list[str],
    job_title: str,
    company: str,
    location: str,
    description: str,
    preferences: dict[str, Any] | None = None,
    client: LLMClient | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run LLM analysis and normalize the response."""
    if client is None:
        if config is None:
            raise LLMError("config or client required")
        client = get_llm_client(config)

    prefs = preferences or {}
    search = (config or {}).get("search") or {}
    yoe = prefs.get("years_of_experience", search.get("years_of_experience"))
    exp_max = prefs.get("experience_max", search.get("experience_max"))

    user = f"""Candidate years of experience: {yoe}
Max experience preference (skip higher seniority if set): {exp_max}
Candidate skills: {", ".join(resume_skills) or "(none listed)"}

RESUME:
{_truncate(resume_text, 6000)}

JOB:
Title: {job_title}
Company: {company}
Location: {location}

JOB DESCRIPTION:
{_truncate(description, 4500)}
"""
    raw = client.complete_json(SYSTEM_PROMPT, user)
    return normalize_analysis(raw, provider=client.provider, model=client.model)


def normalize_analysis(
    raw: dict[str, Any], *, provider: str, model: str
) -> dict[str, Any]:
    decision = str(raw.get("decision") or "maybe").lower().strip()
    if decision not in {"apply", "maybe", "skip"}:
        decision = "maybe"
    try:
        fit = float(raw.get("fit_score", 0))
    except (TypeError, ValueError):
        fit = 0.0
    fit = max(0.0, min(100.0, fit))

    def _str_list(key: str) -> list[str]:
        val = raw.get(key) or []
        if isinstance(val, str):
            return [val] if val.strip() else []
        return [str(x).strip() for x in val if str(x).strip()]

    form = raw.get("form_answers") if isinstance(raw.get("form_answers"), dict) else {}
    form_answers = {
        "years_of_experience": str(form.get("years_of_experience") or ""),
        "current_location": str(form.get("current_location") or ""),
        "willing_to_relocate": str(form.get("willing_to_relocate") or ""),
        "notice_period": str(form.get("notice_period") or ""),
        "why_company": str(form.get("why_company") or ""),
        "why_role": str(form.get("why_role") or ""),
    }

    return {
        "fit_score": fit,
        "decision": decision,
        "reasons": _str_list("reasons"),
        "gaps": _str_list("gaps"),
        "red_flags": _str_list("red_flags"),
        "tailored_bullets": _str_list("tailored_bullets"),
        "cover_letter": str(raw.get("cover_letter") or "").strip(),
        "form_answers": form_answers,
        "provider": provider,
        "model": model,
    }
