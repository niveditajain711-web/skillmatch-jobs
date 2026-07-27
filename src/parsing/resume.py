"""Resume loading: PDF primary, plain-text fallback."""

from __future__ import annotations

from pathlib import Path

from src.models_dto import ResumeData
from src.parsing.skills import extract_skills_from_text


def _read_pdf(path: Path) -> str:
    import pdfplumber

    chunks: list[str] = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            if text.strip():
                chunks.append(text)
    return "\n".join(chunks).strip()


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore").strip()


def load_resume(
    pdf_path: str | Path,
    text_fallback_path: str | Path | None = None,
) -> ResumeData:
    pdf = Path(pdf_path)
    fallback = Path(text_fallback_path) if text_fallback_path else None

    text = ""
    source = ""

    if pdf.exists() and pdf.suffix.lower() == ".pdf":
        try:
            text = _read_pdf(pdf)
            source = str(pdf)
        except Exception as exc:  # noqa: BLE001
            print(f"Warning: failed to parse PDF ({exc}); trying text fallback.")

    if not text and fallback and fallback.exists():
        text = _read_text(fallback)
        source = str(fallback)

    if not text and pdf.exists() and pdf.suffix.lower() in {".txt", ".md"}:
        text = _read_text(pdf)
        source = str(pdf)

    if not text:
        raise FileNotFoundError(
            "Could not load resume. Provide a readable PDF at "
            f"{pdf} or text at {fallback}."
        )

    skills = extract_skills_from_text(text)
    return ResumeData(text=text, skills=skills, source_path=source)