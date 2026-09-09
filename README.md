# SkillMatch Jobs

Resume-aware job search with explainable match scores and skill-gap reports.

Fetches jobs from configurable APIs, scores them against your resume, stores history in **PostgreSQL**, and exports **Excel** reports. Includes a **CLI** and a **web UI** (FastAPI + React).

## Stack

| Layer | Tech |
|-------|------|
| Core | Python — fetchers, parsing, scoring, orchestrator |
| CLI | Click (`python -m api.services.core.main`) |
| API | FastAPI + Uvicorn |
| UI | React + Vite + TypeScript + Tailwind + TanStack Query |
| DB | PostgreSQL |
| Job sources | JSearch, Remotive, Arbeitnow, curated company ATS boards |

## Setup

```bash
python -m venv .venv
.\.venv\Scripts\Activate.ps1   # Windows
pip install -r requirements.txt
copy .env.example .env
```

Point `.env` at your Postgres:

```env
DATABASE_URL=postgresql://postgres:admin@localhost:5432/jobsearch
```

Create DB if needed: `CREATE DATABASE jobsearch;`

Put resume at `data/resume.pdf` or `data/resume.txt`. Tune `config.yaml`.

### Frontend

```bash
cd frontend
npm install
```

## Run

### Web UI (recommended)

Terminal 1 — API:

```bash
python -m uvicorn api.main:app --reload --port 8000
```

On Windows, if `uvicorn` is blocked by Application Control, use `python -m uvicorn` (not `uvicorn` directly).

Terminal 2 — UI:

```bash
cd frontend
npm run dev
```

Open http://localhost:5173

### CLI

```bash
python -m api.services.core.main
python -m api.services.core.main --refresh
python -m api.services.core.main --rescore-only
python -m api.services.core.main --validate-jsearch   # dry-run JSearch config
```

## UI screens

- **Dashboard** — latest run stats, top matches, skill gaps
- **New Search** — keywords, sources, run search
- **Results** — ranked jobs for a run
- **Job detail** — score breakdown, matched/missing skills, apply link
- **Apply Queue** — AI drafts to approve / skip / open apply
- **Resume** — upload PDF/txt, view detected skills
- **History** — past search runs
- **Settings** — scoring weights + agent status

## API docs

With API running: http://localhost:8000/docs

## AI apply agent

Human-in-the-loop: fit analysis, drafts, batch shortlist, clipboard pack, optional browser prefills. Nothing is auto-submitted.

1. Install [Ollama](https://ollama.com) and pull a model:
   ```bash
   ollama pull llama3.1:8b
   ```
2. Ensure `agent` is enabled in `config.yaml` (`provider: ollama`).
3. From **Results** → **Analyze top N with AI** (or open a job → **Analyze with AI**).
4. In **Apply Queue**: review → **Copy apply pack** / **Open apply + copy** → paste on the official site → **Mark applied**.
5. Optional browser assist (Greenhouse / Lever / Ashby heuristics):
   ```bash
   pip install playwright
   playwright install chromium
   ```
   Then use **Browser fill (you submit)** — a Chromium window opens, fields are prefilled, **you** click Submit.
6. Optional daily shortlist: set `agent.schedule.enabled: true` and `daily_at`, or use Settings → **Run shortlist now**.

Cloud alternatives (set in `config.yaml` + `.env`):

```yaml
agent:
  provider: groq   # or gemini
  model: llama-3.1-8b-instant
```

```env
GROQ_API_KEY=...
# or GEMINI_API_KEY=...
```

## Company career boards

Official ATS links (not Shine/BeBee) come from a curated list in `config.yaml` under `sources.company_boards.companies`:

```yaml
- name: Stripe
  board: greenhouse   # greenhouse | lever | ashby | workday
  token: stripe
```

JSearch also excludes low-quality publishers and prefers ATS/careers apply URLs when multiple options exist.

## Outputs

- Postgres: `search_runs`, `jobs`, `job_scores`, `raw_responses`
- Excel: `reports/job_matches_YYYYMMDD_HHMM.xlsx`
- Cache: `cache/*.json`

## Roadmap

- [ ] Authentication (JWT / user accounts)
- [ ] Saved jobs & alerts
