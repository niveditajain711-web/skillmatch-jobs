# Job Search + Resume Matcher

Personal Python CLI that:

1. Fetches jobs from free sources (JSearch/RapidAPI, Remotive, Arbeitnow)
2. Scores your resume against each job (keyword match + gaps)
3. Saves results to **PostgreSQL**
4. Writes an **Excel** report (`Summary`, `Matches`, `Gaps`)

## Setup

```bash
python -m venv .venv

# Windows PowerShell
.\.venv\Scripts\Activate.ps1

pip install -r requirements.txt
copy .env.example .env
```

### PostgreSQL (use your existing local instance)

This project does **not** start a Postgres container. Point `.env` at your local database:

```env
DATABASE_URL=postgresql://postgres:admin@localhost:5432/jobsearch
```

Create the database once if needed:

```sql
CREATE DATABASE jobsearch;
```

Tables are created automatically on first run.

Optional: `RAPIDAPI_KEY` in `.env` when `sources.jsearch.enabled: true` in `config.yaml`.

Put your resume at `data/resume.pdf` (preferred) or edit `data/resume.txt` (fallback).

Tune search settings in `config.yaml`.

## Run

From the project root:

```bash
python -m src.main
python -m src.main --refresh          # ignore cache, hit APIs
python -m src.main --rescore-only     # no API calls; rescore DB jobs
```

## Outputs

- Postgres tables: `search_runs`, `jobs`, `job_scores`, `raw_responses`
- Excel: `reports/job_matches_YYYYMMDD_HHMM.xlsx`
- File cache: `cache/*.json` (protects free API quotas)

## Notes

- Tables are created automatically via SQLAlchemy `create_all` on first run.
- JSearch is skipped gracefully if `RAPIDAPI_KEY` is missing.
- Remotive and Arbeitnow work without keys.
