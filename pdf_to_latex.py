"""Convert uploaded PDF resume text to FitLine LaTeX."""

from __future__ import annotations

import io
import re

from pathlib import Path

from ai_rewriter import _call_gemini_raw, resolve_api_key

JAKES_PREAMBLE = Path(__file__).parent / "templates" / "jakes_resume_preamble.tex"

CONVERT_PROMPT = """You convert plain-text resume content (extracted from a PDF/Word export) into
a complete, compilable LaTeX file using FitLine template macros.

Use EXACTLY these macros for structure:
- \\section{Experience}, \\section{Education}, \\section{Skills}, etc.
- \\resumeSubheading{Job Title}{Dates}{Company}{Location}
- \\resumeItemListStart ... \\resumeItem{bullet text} ... \\resumeItemListEnd
- Name/contact in a \\begin{center} block at the top

Rules:
1. Preserve ALL facts, numbers, metrics, company names, dates, and degrees exactly.
2. Do NOT invent experience or metrics not in the source text.
3. Escape LaTeX specials: \\$, \\%, \\&, \\#, \\_, \\{, \\}
4. Return ONLY the full .tex file from \\documentclass through \\end{document}
5. Do NOT include \\usepackage{fitline} — omit it entirely (not for Overleaf export).
6. CRITICAL — PDF text is often broken across visual line wraps. Merge continuation lines
   into ONE \\resumeItem per bullet. Each bullet must be a single uninterrupted line of text.
7. Each experience bullet should be a FULL line (~90–110 characters) — combine related
   phrases from the source; do NOT split one accomplishment into multiple short bullets.
8. ATS header format: job title and dates bold on row 1; company and location italic on row 2.

Resume text from PDF:
---
<<<RESUME_TEXT>>>
---
"""

BULLET_MARKER_RE = re.compile(
    r"^[\s]*(?:"
    r"[•●◦▪▸►·]|"
    r"[-–—]\s+|"
    r"\*\s+|"
    r"o\s+|"
    r"\d+[.)]\s+"
    r")",
    re.I,
)

SECTION_HEADER_RE = re.compile(
    r"^[A-Z][A-Z0-9\s/&\-–—]{2,}$",
)


def normalize_pdf_text(text: str) -> str:
    """
    Rejoin PDF line wraps into logical bullets/paragraphs.
    PDF extractors break wrapped lines — this merges them back before AI conversion.
    """
    lines = [ln.rstrip() for ln in text.splitlines()]
    blocks: list[str] = []
    current = ""

    def flush() -> None:
        nonlocal current
        if current.strip():
            blocks.append(current.strip())
        current = ""

    for raw in lines:
        stripped = raw.strip()
        if not stripped:
            flush()
            continue

        if SECTION_HEADER_RE.match(stripped) and len(stripped.split()) <= 6:
            flush()
            blocks.append(stripped)
            continue

        if BULLET_MARKER_RE.match(raw):
            flush()
            current = BULLET_MARKER_RE.sub("", stripped).strip()
            continue

        if not current:
            current = stripped
        elif current.endswith("-") and not current.endswith("--"):
            current = current[:-1] + stripped
        else:
            current = f"{current} {stripped}"

    flush()
    return "\n\n".join(blocks)


def _build_convert_prompt(resume_text: str) -> str:
    """Insert PDF text without str.format — LaTeX braces in the template break .format()."""
    return CONVERT_PROMPT.replace("<<<RESUME_TEXT>>>", resume_text[:12000])


def extract_pdf_text(pdf_bytes: bytes) -> str:
    """Extract text from PDF bytes."""
    try:
        import fitz  # pymupdf

        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        parts = [page.get_text() for page in doc]
        doc.close()
        text = "\n".join(parts).strip()
        if text:
            return normalize_pdf_text(text)
    except ImportError:
        pass
    except Exception:
        pass

    try:
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(pdf_bytes))
        text = "\n".join((p.extract_text() or "") for p in reader.pages).strip()
        if text:
            return normalize_pdf_text(text)
    except ImportError:
        pass
    except Exception:
        pass

    raise RuntimeError(
        "Could not read PDF text. Install pymupdf: pip install pymupdf"
    )


def _strip_code_fence(raw: str) -> str:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:latex|tex)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw.strip())
    return raw.strip()


def flatten_resume_bullets(tex: str) -> str:
    """
    Collapse multi-line \\resumeItem{...} bodies to one line and normalize whitespace.
    PDF conversion often emits hard line breaks inside bullet macros.
    """
    marker = r"\resumeItem{"
    out: list[str] = []
    i = 0
    while i < len(tex):
        pos = tex.find(marker, i)
        if pos == -1:
            out.append(tex[i:])
            break
        out.append(tex[i:pos])
        j = pos + len(marker)
        depth = 1
        body_start = j
        while j < len(tex) and depth:
            ch = tex[j]
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
            j += 1
        body = tex[body_start : j - 1]
        body = re.sub(r"\s+", " ", body).strip()
        out.append(f"{marker}{body}}}")
        i = j
    return "".join(out)


def strip_fitline_package(tex: str) -> str:
    """Remove fitline package and legacy rolefit macros from Overleaf-ready export."""
    tex = re.sub(
        r"^% >>> fitline \(auto-injected\)\s*\n\\usepackage\{fitline\}\s*\n",
        "",
        tex,
        flags=re.MULTILINE,
    )
    tex = re.sub(r"^\\usepackage(\[[^\]]*\])?\{fitline\}\s*\n?", "", tex, flags=re.MULTILINE)
    tex = re.sub(
        r"\\rolefit\{([^}]*)\}\{([^}]*)\}\{([^}]*)\}\{([^}]*)\}",
        r"\\role{\1}{\2}{\3}{\4}",
        tex,
    )
    return tex


def _ensure_document(tex: str) -> str:
    tex = _strip_code_fence(tex)
    tex = flatten_resume_bullets(tex)
    if r"\documentclass" not in tex:
        preamble = JAKES_PREAMBLE.read_text(encoding="utf-8")
        body = tex
        if not body.startswith("\n"):
            body = "\n" + body
        tex = preamble + r"\begin{document}" + body + "\n" + r"\end{document}"
    return strip_fitline_package(tex)


def pdf_to_jakes_latex(
    pdf_bytes: bytes,
    *,
    api_key: str | None = None,
    provider: str = "gemini",
) -> tuple[str, str | None]:
    """
    Convert PDF resume to FitLine LaTeX.
    Returns (latex_string, error_message).
    """
    if provider != "gemini":
        return "", "PDF conversion currently supports Gemini only."

    key = resolve_api_key(provider, api_key)  # type: ignore[arg-type]
    if not key:
        return "", "Add a Gemini API key to convert PDF → LaTeX."

    try:
        text = extract_pdf_text(pdf_bytes)
    except RuntimeError as e:
        return "", str(e)

    if len(text.strip()) < 40:
        return "", "PDF had too little text — try exporting from Word as PDF (not a scan)."

    prompt = _build_convert_prompt(text)

    try:
        raw = _call_gemini_raw(prompt, key)
    except Exception as e:
        return "", f"Gemini conversion failed: {e}"

    latex = _ensure_document(raw)
    if r"\begin{document}" not in latex:
        return "", "AI did not return valid LaTeX. Try again or paste manually."

    return latex, None
