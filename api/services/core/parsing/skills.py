"""Skill taxonomy and keyword helpers."""

from __future__ import annotations

import re

# Canonical skill -> aliases (lowercase)
SKILL_ALIASES: dict[str, list[str]] = {
    "python": ["python", "python3", "py"],
    "java": ["java"],
    "javascript": ["javascript", "js", "ecmascript"],
    "typescript": ["typescript", "ts"],
    "golang": ["golang", "go lang"],
    "rust": ["rust"],
    "c++": ["c++", "cpp"],
    "c#": ["c#", "csharp", "c sharp"],
    "ruby": ["ruby"],
    "php": ["php"],
    "scala": ["scala"],
    "kotlin": ["kotlin"],
    "swift": ["swift"],
    "sql": ["sql"],
    "postgresql": ["postgresql", "postgres", "psql"],
    "mysql": ["mysql"],
    "mongodb": ["mongodb", "mongo"],
    "redis": ["redis"],
    "elasticsearch": ["elasticsearch", "elastic search", "opensearch"],
    "django": ["django"],
    "flask": ["flask"],
    "fastapi": ["fastapi", "fast api"],
    "spring": ["spring boot", "spring framework", "spring"],
    "nodejs": ["nodejs", "node.js", "node js"],
    "express": ["express.js", "expressjs", "express"],
    "react": ["react.js", "reactjs", "react"],
    "angular": ["angular"],
    "vue": ["vue.js", "vuejs", "vue"],
    "nextjs": ["next.js", "nextjs"],
    "aws": ["aws", "amazon web services"],
    "azure": ["azure", "microsoft azure"],
    "gcp": ["gcp", "google cloud", "google cloud platform"],
    "docker": ["docker"],
    "kubernetes": ["kubernetes", "k8s"],
    "terraform": ["terraform"],
    "ansible": ["ansible"],
    "ci/cd": ["ci/cd", "cicd", "continuous integration", "continuous delivery"],
    "jenkins": ["jenkins"],
    "github actions": ["github actions", "github-actions"],
    "gitlab ci": ["gitlab ci", "gitlab-ci"],
    "linux": ["linux", "unix"],
    "git": ["git"],
    "rest": ["rest api", "restful", "rest apis"],
    "graphql": ["graphql"],
    "grpc": ["grpc"],
    "kafka": ["kafka", "apache kafka"],
    "rabbitmq": ["rabbitmq"],
    "microservices": ["microservices", "micro-services", "microservice"],
    "agile": ["agile", "scrum"],
    "machine learning": ["machine learning", "ml"],
    "deep learning": ["deep learning"],
    "pytorch": ["pytorch", "py torch"],
    "tensorflow": ["tensorflow"],
    "pandas": ["pandas"],
    "numpy": ["numpy"],
    "spark": ["apache spark", "pyspark", "spark"],
    "airflow": ["airflow", "apache airflow"],
    "dbt": ["dbt"],
    "snowflake": ["snowflake"],
    "databricks": ["databricks"],
    "html": ["html", "html5"],
    "css": ["css", "css3"],
    "tailwind": ["tailwind", "tailwindcss"],
    "selenium": ["selenium"],
    "pytest": ["pytest"],
    "junit": ["junit"],
    "oauth": ["oauth", "oauth2"],
    "jwt": ["jwt", "json web token"],
    "celery": ["celery"],
    "nginx": ["nginx"],
    "helm": ["helm"],
    "prometheus": ["prometheus"],
    "grafana": ["grafana"],
    "langchain": ["langchain"],
    "openai": ["openai", "chatgpt"],
    "llm": ["llm", "large language model", "large language models"],
    "rag": ["rag", "retrieval augmented"],
}

MUST_HAVE_MARKERS = (
    "requirements",
    "required",
    "must have",
    "must-have",
    "qualifications",
    "what you'll need",
    "minimum qualifications",
)
NICE_TO_HAVE_MARKERS = (
    "nice to have",
    "nice-to-have",
    "preferred",
    "bonus",
    "good to have",
    "desired",
)


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").lower())


def _strip_html(text: str) -> str:
    """Remove HTML tags so skills are not matched inside attributes or markup."""
    without_tags = re.sub(r"<[^>]+>", " ", text or "")
    return re.sub(r"\s+", " ", without_tags).strip()


def _alias_in_text(token: str, haystack: str) -> bool:
    """Match skill aliases on word boundaries to avoid false positives (rest in restaurants)."""
    token = token.lower().strip()
    if not token:
        return False
    if " " in token:
        pattern = rf"(?<![a-z0-9]){re.escape(token)}(?![a-z0-9])"
    else:
        pattern = rf"(?<![a-z0-9]){re.escape(token)}(?![a-z0-9])"
    return re.search(pattern, haystack) is not None


def extract_skills_from_text(text: str) -> list[str]:
    """Return sorted canonical skills found in text."""
    cleaned = _strip_html(text)
    haystack = f" {_normalize_text(cleaned)} "
    found: set[str] = set()
    for canonical, aliases in SKILL_ALIASES.items():
        for alias in aliases:
            if _alias_in_text(alias, haystack):
                found.add(canonical)
                break
    return sorted(found)


def split_job_skill_buckets(description: str) -> tuple[list[str], list[str]]:
    """Heuristic split of skills into must-have vs nice-to-have."""
    text = description or ""
    lower = text.lower()
    must_idx = -1
    nice_idx = -1
    for marker in MUST_HAVE_MARKERS:
        i = lower.find(marker)
        if i != -1 and (must_idx == -1 or i < must_idx):
            must_idx = i
    for marker in NICE_TO_HAVE_MARKERS:
        i = lower.find(marker)
        if i != -1 and (nice_idx == -1 or i < nice_idx):
            nice_idx = i

    if must_idx == -1 and nice_idx == -1:
        return extract_skills_from_text(text), []

    if must_idx != -1 and nice_idx != -1:
        if must_idx < nice_idx:
            must_text = text[must_idx:nice_idx]
            nice_text = text[nice_idx:]
        else:
            nice_text = text[nice_idx:must_idx]
            must_text = text[must_idx:]
        must = extract_skills_from_text(must_text)
        nice = [s for s in extract_skills_from_text(nice_text) if s not in must]
        if not must and not nice:
            return extract_skills_from_text(text), []
        return must, nice

    if must_idx != -1:
        must = extract_skills_from_text(text[must_idx:])
        rest = extract_skills_from_text(text[:must_idx])
        nice = [s for s in rest if s not in must]
        return must or extract_skills_from_text(text), nice

    nice = extract_skills_from_text(text[nice_idx:])
    must = [s for s in extract_skills_from_text(text[:nice_idx]) if s not in nice]
    if not must:
        must = extract_skills_from_text(text)
        nice = [s for s in nice if s not in must]
    return must, nice


def title_skill_overlap(title: str, resume_skills: list[str]) -> float:
    title_skills = extract_skills_from_text(title)
    if not title_skills:
        title_l = title.lower()
        hits = sum(1 for s in resume_skills if s in title_l)
        return min(1.0, hits / 3.0) if resume_skills else 0.0
    resume_set = set(resume_skills)
    matched = sum(1 for s in title_skills if s in resume_set)
    return matched / len(title_skills)