"""Browser-assisted form fill for known ATS boards.

IMPORTANT: Never clicks final Submit / Send Application.
Opens a headed browser, fills what it can, leaves the tab open for the human.
"""

from __future__ import annotations

import re
import threading
from typing import Any
from urllib.parse import urlparse

_assist_lock = threading.Lock()
_assist_jobs: dict[int, dict[str, Any]] = {}


class BrowserAssistError(RuntimeError):
    pass


def detect_ats(url: str) -> str:
    host = (urlparse(url).hostname or "").lower()
    path = (urlparse(url).path or "").lower()
    if "greenhouse.io" in host or "boards.greenhouse" in host:
        return "greenhouse"
    if "lever.co" in host:
        return "lever"
    if "ashbyhq.com" in host or "jobs.ashby" in host:
        return "ashby"
    if "myworkdayjobs.com" in host or "workday" in host:
        return "workday"
    if "greenhouse" in path:
        return "greenhouse"
    return "generic"


def parse_applicant_from_resume(resume_text: str) -> dict[str, str]:
    """Best-effort contact extraction from resume header."""
    text = resume_text or ""
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    full_name = lines[0] if lines else ""
    # Prefer all-caps or first line without too many separators
    email_m = re.search(r"[\w.+-]+@[\w.-]+\.\w+", text)
    phone_m = re.search(r"(?:\+?\d[\d\s\-()]{8,}\d)", text)
    linkedin_m = re.search(r"(?:https?://)?(?:www\.)?linkedin\.com/in/[\w\-/%]+", text, re.I)
    github_m = re.search(r"(?:https?://)?(?:www\.)?github\.com/[\w\-]+", text, re.I)

    first = last = ""
    if full_name:
        parts = re.split(r"\s+", full_name.replace("|", " ").strip())
        parts = [p for p in parts if p and "@" not in p and not p.isdigit()]
        if len(parts) >= 2:
            first, last = parts[0], " ".join(parts[1:])
        elif parts:
            first = parts[0]

    return {
        "full_name": full_name.title() if full_name.isupper() else full_name,
        "first_name": first.title() if first.isupper() else first,
        "last_name": last.title() if last.isupper() else last,
        "email": email_m.group(0) if email_m else "",
        "phone": re.sub(r"\s+", " ", phone_m.group(0)).strip() if phone_m else "",
        "linkedin": (
            linkedin_m.group(0)
            if linkedin_m and linkedin_m.group(0).startswith("http")
            else f"https://{linkedin_m.group(0)}"
            if linkedin_m
            else ""
        ),
        "github": (
            github_m.group(0)
            if github_m and github_m.group(0).startswith("http")
            else f"https://{github_m.group(0)}"
            if github_m
            else ""
        ),
        "location": "",
        "years_of_experience": "",
        "notice_period": "",
        "cover_letter": "",
        "resume_path": "",
    }


def merge_applicant_profile(
    config: dict[str, Any],
    *,
    resume_text: str = "",
    form_answers: dict[str, Any] | None = None,
    cover_letter: str = "",
) -> dict[str, str]:
    parsed = parse_applicant_from_resume(resume_text)
    cfg = (config.get("agent") or {}).get("applicant") or {}
    answers = form_answers or {}
    profile = {
        **parsed,
        **{k: str(v) for k, v in cfg.items() if v},
    }
    # Form answers overlay common keys
    if answers.get("current_location"):
        profile["location"] = str(answers["current_location"])
    if answers.get("years_of_experience"):
        profile["years_of_experience"] = str(answers["years_of_experience"])
    if answers.get("notice_period"):
        profile["notice_period"] = str(answers["notice_period"])
    if answers.get("willing_to_relocate"):
        profile["willing_to_relocate"] = str(answers["willing_to_relocate"])
    if answers.get("why_company"):
        profile["why_company"] = str(answers["why_company"])
    if answers.get("why_role"):
        profile["why_role"] = str(answers["why_role"])
    if cover_letter:
        profile["cover_letter"] = cover_letter
    resume_cfg = config.get("resume") or {}
    if not profile.get("resume_path"):
        profile["resume_path"] = str(resume_cfg.get("path") or "./data/resume.pdf")
    return {k: str(v or "") for k, v in profile.items()}


def get_assist_status(queue_id: int) -> dict[str, Any] | None:
    with _assist_lock:
        job = _assist_jobs.get(queue_id)
        return dict(job) if job else None


def start_browser_assist(
    *,
    queue_id: int,
    url: str,
    profile: dict[str, str],
    config: dict[str, Any],
) -> dict[str, Any]:
    """Launch headed Playwright fill in a background thread. Never submits."""
    agent = config.get("agent") or {}
    assist_cfg = agent.get("browser_assist") or {}
    if not assist_cfg.get("enabled", True):
        raise BrowserAssistError("Browser assist is disabled in config (agent.browser_assist.enabled)")
    if not url:
        raise BrowserAssistError("Job has no apply URL")
    if not agent.get("require_human_approval", True):
        # Still never auto-submit; but warn via status
        pass

    with _assist_lock:
        existing = _assist_jobs.get(queue_id)
        if existing and existing.get("status") == "running":
            raise BrowserAssistError("Browser assist already running for this queue item")
        _assist_jobs[queue_id] = {
            "queue_id": queue_id,
            "status": "starting",
            "ats": detect_ats(url),
            "url": url,
            "filled": [],
            "skipped": [],
            "message": "Launching browser…",
            "error": None,
        }

    def _worker() -> None:
        try:
            result = _run_playwright_fill(
                url=url,
                profile=profile,
                config=config,
                on_filled=lambda payload: _set_status(queue_id, payload),
            )
            with _assist_lock:
                _assist_jobs[queue_id] = {
                    "queue_id": queue_id,
                    "status": "closed",
                    "ats": result["ats"],
                    "url": url,
                    "filled": result["filled"],
                    "skipped": result["skipped"],
                    "message": result["message"] + " Browser window closed.",
                    "error": None,
                }
        except Exception as exc:  # noqa: BLE001
            with _assist_lock:
                _assist_jobs[queue_id] = {
                    "queue_id": queue_id,
                    "status": "failed",
                    "ats": detect_ats(url),
                    "url": url,
                    "filled": [],
                    "skipped": [],
                    "message": str(exc),
                    "error": str(exc),
                }

    threading.Thread(target=_worker, daemon=True, name=f"browser-assist-{queue_id}").start()
    with _assist_lock:
        return dict(_assist_jobs[queue_id])


_SUBMIT_RE = re.compile(
    r"submit|send\s+application|apply\s+now|finish\s+application|complete\s+application",
    re.I,
)
_OPEN_APPLY_RE = re.compile(r"^(apply|apply\s+for\s+this\s+job|apply\s+now)$", re.I)


def _set_status(queue_id: int, payload: dict[str, Any]) -> None:
    with _assist_lock:
        cur = _assist_jobs.get(queue_id) or {"queue_id": queue_id}
        cur.update(payload)
        _assist_jobs[queue_id] = cur


def _run_playwright_fill(
    *,
    url: str,
    profile: dict[str, str],
    config: dict[str, Any],
    on_filled=None,
) -> dict[str, Any]:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise BrowserAssistError(
            "Playwright is not installed. Run: pip install playwright && playwright install chromium"
        ) from exc

    assist_cfg = (config.get("agent") or {}).get("browser_assist") or {}
    timeout_ms = int(assist_cfg.get("keep_open_minutes", 45)) * 60 * 1000
    ats = detect_ats(url)
    filled: list[str] = []
    skipped: list[str] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=int(assist_cfg.get("slow_mo_ms", 50)))
        context = browser.new_context()
        page = context.new_page()
        page.set_default_timeout(15000)
        page.goto(url, wait_until="domcontentloaded")

        _try_open_application_form(page)

        # Prefer application iframe (Greenhouse)
        frames = [page] + list(page.frames)
        target = page
        for fr in frames:
            try:
                if fr.locator("input, textarea, select").count() >= 2:
                    target = fr
                    break
            except Exception:  # noqa: BLE001
                continue

        field_plan = _field_plan(profile, ats=ats)
        for label, value in field_plan:
            if not value:
                skipped.append(f"{label} (empty)")
                continue
            ok = _fill_by_label(target, label, value)
            if ok:
                filled.append(label)
            else:
                skipped.append(label)

        # Resume upload
        resume_path = profile.get("resume_path") or ""
        if resume_path:
            uploaded = _try_upload_resume(target, resume_path)
            if uploaded:
                filled.append("resume_file")
            else:
                skipped.append("resume_file")

        # Soft banner for the human
        try:
            page.evaluate(
                """() => {
                  const el = document.createElement('div');
                  el.textContent = 'SkillMatch: fields prefilled — review and click Submit yourself. Agent will NOT submit.';
                  Object.assign(el.style, {
                    position: 'fixed', top: '0', left: '0', right: '0', zIndex: '2147483647',
                    background: '#0f766e', color: 'white', padding: '10px 16px',
                    font: '14px/1.4 system-ui,sans-serif', textAlign: 'center'
                  });
                  document.body.prepend(el);
                }"""
            )
        except Exception:  # noqa: BLE001
            pass

        message = (
            f"Filled {len(filled)} field(s) on {ats}. "
            "Browser stays open — review answers and click Submit yourself. "
            "This agent never clicks Submit."
        )
        if on_filled:
            on_filled(
                {
                    "status": "awaiting_human_submit",
                    "ats": ats,
                    "url": url,
                    "filled": list(filled),
                    "skipped": list(skipped),
                    "message": message,
                    "error": None,
                }
            )

        # Keep browser open until user closes the page or timeout
        try:
            page.wait_for_event("close", timeout=timeout_ms)
        except Exception:  # noqa: BLE001
            pass
        try:
            browser.close()
        except Exception:  # noqa: BLE001
            pass

    return {
        "ats": ats,
        "filled": filled,
        "skipped": skipped,
        "message": message,
    }


def _try_open_application_form(page) -> None:
    """Click the job-page Apply control to reveal the form (not final submit)."""
    candidates = [
        "text=Apply for this job",
        "text=Apply for this Job",
        "role=button[name=/^Apply$/i]",
        "role=link[name=/^Apply$/i]",
        "text=Apply",
    ]
    for sel in candidates:
        try:
            loc = page.locator(sel).first
            if loc.count() == 0:
                continue
            text = (loc.inner_text() or "").strip()
            # Avoid final-submit style buttons
            if _SUBMIT_RE.search(text) and not _OPEN_APPLY_RE.match(text):
                continue
            loc.click(timeout=3000)
            page.wait_for_timeout(800)
            return
        except Exception:  # noqa: BLE001
            continue


def _field_plan(profile: dict[str, str], *, ats: str) -> list[tuple[str, str]]:
    """Ordered (label_hint, value) pairs to attempt."""
    plan = [
        ("First Name", profile.get("first_name", "")),
        ("Last Name", profile.get("last_name", "")),
        ("Full Name", profile.get("full_name", "")),
        ("Name", profile.get("full_name", "")),
        ("Email", profile.get("email", "")),
        ("Phone", profile.get("phone", "")),
        ("Mobile", profile.get("phone", "")),
        ("LinkedIn", profile.get("linkedin", "")),
        ("LinkedIn Profile", profile.get("linkedin", "")),
        ("GitHub", profile.get("github", "")),
        ("Website", profile.get("github", "")),
        ("Location", profile.get("location", "")),
        ("City", profile.get("location", "")),
        ("Current location", profile.get("location", "")),
        ("Years of experience", profile.get("years_of_experience", "")),
        ("How many years", profile.get("years_of_experience", "")),
        ("Notice period", profile.get("notice_period", "")),
        ("Notice Period", profile.get("notice_period", "")),
        ("Willing to relocate", profile.get("willing_to_relocate", "")),
        ("Cover Letter", profile.get("cover_letter", "")),
        ("Cover letter", profile.get("cover_letter", "")),
        ("Additional information", profile.get("cover_letter", "")),
        ("Why do you want", profile.get("why_company") or profile.get("why_role") or ""),
        ("Why are you interested", profile.get("why_role") or profile.get("why_company") or ""),
    ]
    if ats == "lever":
        # Lever often uses Full name single field
        plan = [p for p in plan if p[0] not in {"First Name", "Last Name"}] + plan
    return plan


def _fill_by_label(root, label: str, value: str) -> bool:
    """Try several strategies to set an input without touching submit."""
    strategies = [
        lambda: root.get_by_label(re.compile(re.escape(label), re.I), exact=False).first.fill(value),
        lambda: root.get_by_placeholder(re.compile(re.escape(label), re.I)).first.fill(value),
        lambda: root.locator(
            f'input[name*="{_slug(label)}" i], textarea[name*="{_slug(label)}" i]'
        ).first.fill(value),
        lambda: root.locator(
            f'input[aria-label*="{label}" i], textarea[aria-label*="{label}" i]'
        ).first.fill(value),
    ]
    for strat in strategies:
        try:
            strat()
            return True
        except Exception:  # noqa: BLE001
            continue
    # Label text → following input
    try:
        lab = root.locator(f"label:has-text('{label}')").first
        if lab.count():
            for_id = lab.get_attribute("for")
            if for_id:
                root.locator(f"#{for_id}").fill(value)
                return True
            lab.locator("xpath=following::input[1] | following::textarea[1]").first.fill(value)
            return True
    except Exception:  # noqa: BLE001
        pass
    return False


def _slug(label: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", label.lower()).strip("_")


def _try_upload_resume(root, path: str) -> bool:
    from pathlib import Path

    p = Path(path)
    if not p.is_file():
        # try .txt sibling
        return False
    try:
        file_inputs = root.locator('input[type="file"]')
        n = file_inputs.count()
        for i in range(min(n, 3)):
            try:
                file_inputs.nth(i).set_input_files(str(p.resolve()))
                return True
            except Exception:  # noqa: BLE001
                continue
    except Exception:  # noqa: BLE001
        return False
    return False


__all__ = [
    "BrowserAssistError",
    "detect_ats",
    "get_assist_status",
    "merge_applicant_profile",
    "parse_applicant_from_resume",
    "start_browser_assist",
]
