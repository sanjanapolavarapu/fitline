"""Estimate how many characters fit on one resume bullet line from LaTeX source."""

from __future__ import annotations

import re
import statistics

# US letter width in inches
LETTER_WIDTH_IN = 8.5
A4_WIDTH_IN = 8.27

# Default \\textwidth for article class (inches) before template tweaks
DEFAULT_TEXTWIDTH_IN = {
    "letterpaper": 451.68793 / 72.0,
    "a4paper": 418.25368 / 72.0,
}

# compile_tex PREVIEW_PREAMBLE uses this — preview PDF is wider than 1in-margin docs
PREVIEW_GEOMETRY_MARGIN_IN = 0.5

# LaTeX font-size command → nominal point size on an 11pt document
LATEX_SIZE_PT = {
    "tiny": 6.0,
    "scriptsize": 8.0,
    "footnotesize": 9.0,
    "small": 10.0,
    "normalsize": 11.0,
    "large": 12.0,
    "Large": 14.0,
    "LARGE": 17.0,
    "huge": 20.0,
    "Huge": 25.0,
}


def _to_inches(val: float, unit: str | None) -> float:
    u = (unit or "in").lower()
    if u == "cm":
        return val / 2.54
    if u == "mm":
        return val / 25.4
    if u == "pt":
        return val / 72.0
    return val


def _page_width(tex: str) -> float:
    return A4_WIDTH_IN if "a4paper" in tex.lower() else LETTER_WIDTH_IN


def _paper_key(tex: str) -> str:
    return "a4paper" if "a4paper" in tex.lower() else "letterpaper"


def _parse_geometry_margin(tex: str) -> float | None:
    """Return symmetric margin in inches from \\usepackage[...]{geometry}."""
    for m in re.finditer(r"\\usepackage(\[[^\]]*\])?\{geometry\}", tex, re.I):
        opts = m.group(1) or ""
        mm = re.search(r"margin\s*=\s*([\d.]+)\s*(in|cm|mm)?", opts, re.I)
        if mm:
            return _to_inches(float(mm.group(1)), mm.group(2))
        left = right = None
        lm = re.search(r"left\s*=\s*([\d.]+)\s*(in|cm|mm)?", opts, re.I)
        rm = re.search(r"right\s*=\s*([\d.]+)\s*(in|cm|mm)?", opts, re.I)
        if lm:
            left = _to_inches(float(lm.group(1)), lm.group(2))
        if rm:
            right = _to_inches(float(rm.group(1)), rm.group(2))
        if left is not None and right is not None:
            return (left + right) / 2.0
    return None


def _parse_addtolength_textwidth(tex: str) -> float:
    delta = 0.0
    for m in re.finditer(
        r"\\addtolength\{\\textwidth\}\{([+-]?[\d.]+)\s*(in|cm|mm|pt)?\}",
        tex,
        re.I,
    ):
        val = float(m.group(1))
        delta += _to_inches(val, m.group(2))
    return delta


def _text_width_inches(tex: str) -> float:
    """Best-effort text block width for the compiled document."""
    page_w = _page_width(tex)
    paper = _paper_key(tex)

    geom_margin = _parse_geometry_margin(tex)
    if geom_margin is not None:
        return page_w - 2 * geom_margin

    # fullpage-style resumes widen \\textwidth directly
    if re.search(r"\\usepackage(\[[^\]]*\])?\{fullpage\}", tex, re.I) or re.search(
        r"\\addtolength\{\\textwidth\}", tex, re.I
    ):
        text_w = DEFAULT_TEXTWIDTH_IN[paper] + _parse_addtolength_textwidth(tex)
        return max(text_w, page_w * 0.72)

    margin_in = 1.0
    for m in re.finditer(r"margin\s*=\s*([\d.]+)\s*(in|cm|mm)?", tex, re.I):
        val = float(m.group(1))
        unit = (m.group(2) or "in").lower()
        if unit == "cm":
            val /= 2.54
        elif unit == "mm":
            val /= 25.4
        margin_in = val
        break

    left = right = None
    lm = re.search(r"left\s*=\s*([\d.]+)\s*(in|cm|mm)?", tex, re.I)
    rm = re.search(r"right\s*=\s*([\d.]+)\s*(in|cm|mm)?", tex, re.I)
    if lm:
        left = _to_inches(float(lm.group(1)), lm.group(2))
    if rm:
        right = _to_inches(float(rm.group(1)), rm.group(2))
    if left is not None and right is not None:
        return page_w - left - right

    text_w = page_w - 2 * margin_in + _parse_addtolength_textwidth(tex)
    return text_w


def _bullet_indent_in(tex: str) -> float:
    indent_in = 0.12
    if re.search(r"leftmargin=\*", tex):
        indent_in = 0.14
    for m in re.finditer(r"leftmargin\s*=\s*([\d.]+)\s*(in|cm|mm|pt)?", tex):
        indent_in = _to_inches(float(m.group(1)), m.group(2) or "pt")
    return indent_in


def _font_size_pt(tex: str) -> float:
    pt = 11.0
    dc = re.search(r"\\documentclass(\[[^\]]*\])?", tex)
    if dc and dc.group(1):
        pm = re.search(r"(\d+(?:\.\d+)?)\s*pt", dc.group(1))
        if pm:
            pt = float(pm.group(1))
    return pt


def _bullet_font_size_pt(tex: str, doc_pt: float) -> float:
    """Detect bullet font size from resumeItem/item definitions and list markup."""
    size_pt = doc_pt
    snippets: list[str] = []

    for m in re.finditer(
        r"\\newcommand\{\\resumeItem\}\[1\]\{([^}]*(?:\{[^}]*\}[^}]*)*)\}",
        tex,
        re.I | re.S,
    ):
        snippets.append(m.group(1))

    if re.search(r"\\item\\small|\\item\s+\\small|\\small\{", tex, re.I):
        snippets.append(r"\small")

    for snippet in snippets:
        for name, nominal in LATEX_SIZE_PT.items():
            if re.search(rf"\\{name}\b", snippet):
                return nominal

    return size_pt


def _char_width_in(tex: str, pt: float) -> float:
    char_w_in = 0.073 * (pt / 11.0)
    if re.search(r"\\usepackage.*\{times\}|mathptmx|newtx", tex, re.I):
        char_w_in *= 0.92
    elif "helvet" in tex.lower() or "sans" in tex.lower():
        char_w_in *= 1.08
    if re.search(r"\\usepackage.*\{lmodern\}", tex, re.I):
        char_w_in *= 0.94

    bullet_pt = _bullet_font_size_pt(tex, pt)
    if bullet_pt != pt:
        char_w_in *= bullet_pt / pt
    return char_w_in


def estimate_line_chars(tex: str) -> int:
    """
    Estimate characters per bullet line from document class, margins, font, and list indent.
    Fallback when PDF calibration is unavailable.
    """
    text_w = _text_width_inches(tex)
    indent_in = _bullet_indent_in(tex)
    pt = _font_size_pt(tex)
    char_w_in = _char_width_in(tex, pt)

    bullet_w = max(text_w - indent_in, text_w * 0.92)
    chars = int(bullet_w / char_w_in)
    return max(80, min(150, chars))


def _is_complete_document(tex: str) -> bool:
    return bool(re.search(r"\\documentclass\b", tex) and re.search(r"\\begin\{document\}", tex))


def _norm_match(text: str) -> str:
    t = text.lower()
    t = re.sub(r"[\u2013\u2014\u2212]", "-", t)
    t = re.sub(r"[^\w\s\-.,/%+&()]", "", t)
    return re.sub(r"\s+", " ", t).strip()


def _collect_pdf_lines(page) -> list[dict]:
    """Return rendered text lines with bounding boxes (PDF points)."""
    lines: list[dict] = []
    payload = page.get_text("dict")
    for block in payload.get("blocks", []):
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            parts: list[str] = []
            x0 = y0 = float("inf")
            x1 = y1 = float("-inf")
            for span in line.get("spans", []):
                text = span.get("text", "")
                if not text:
                    continue
                parts.append(text)
                sx0, sy0, sx1, sy1 = span["bbox"]
                x0 = min(x0, sx0)
                y0 = min(y0, sy0)
                x1 = max(x1, sx1)
                y1 = max(y1, sy1)
            merged = "".join(parts).strip()
            if merged and x0 < float("inf"):
                lines.append({"text": merged, "x0": x0, "x1": x1, "y0": y0, "y1": y1})
    return lines


def _content_right_margin(lines: list[dict], *, exclude: list[dict] | None = None) -> float | None:
    """
    Right edge of the text block — from headings/dates, not bullet bodies.
    Using bullet x1 as the margin falsely marks partial lines as full.
    """
    if not lines:
        return None
    skip = {id(line) for line in (exclude or [])}
    refs = [
        line["x1"]
        for line in lines
        if id(line) not in skip and len(line["text"]) >= 4
    ]
    if not refs:
        refs = [line["x1"] for line in lines]
    return max(refs) if refs else None


def _match_pdf_line(bullet: str, lines: list[dict]) -> dict | None:
    norm_b = _norm_match(bullet)
    if len(norm_b) < 12:
        return None
    prefix = norm_b[: min(32, len(norm_b))]
    best: dict | None = None
    best_score = 0.0
    for line in lines:
        norm_l = _norm_match(line["text"])
        if not norm_l:
            continue
        if prefix in norm_l or norm_l in norm_b:
            score = min(len(norm_l), len(norm_b)) / max(len(norm_b), 1)
            if score > best_score:
                best_score = score
                best = line
        elif norm_l[:20] == prefix[:20]:
            if 0.65 > best_score:
                best_score = 0.65
                best = line
    return best if best_score >= 0.55 else None


def _all_bullet_texts(tex: str) -> list[str]:
    from fit_resume import list_section_bullet_texts
    from sections import list_itemize_blocks, parse_experiences

    bullets: list[str] = []
    blocks = parse_experiences(tex)
    if not blocks:
        blocks = list_itemize_blocks(tex)
    for block in blocks:
        bullets.extend(list_section_bullet_texts(tex[block.start : block.end]))
    return [b for b in bullets if b.strip()]


def calibrate_line_chars_from_pdf(tex: str, pdf_bytes: bytes) -> int | None:
    """
    Measure how many characters fit on one bullet line using the compiled PDF.
    Works for any template/font/margin — not tied to a specific resume section.
    """
    if not pdf_bytes or not pdf_bytes.startswith(b"%PDF"):
        return None

    bullets = _all_bullet_texts(tex)
    if not bullets:
        return None

    try:
        import fitz
    except ImportError:
        return None

    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        if doc.page_count == 0:
            doc.close()
            return None
        page = doc.load_page(0)
        lines = _collect_pdf_lines(page)
        matched_lines: list[dict] = []
        for bullet in bullets:
            line = _match_pdf_line(bullet, lines)
            if line:
                matched_lines.append(line)

        right = _content_right_margin(lines, exclude=matched_lines)
        if not right:
            doc.close()
            return None

        implied: list[float] = []
        for bullet in bullets:
            line = _match_pdf_line(bullet, lines)
            if not line:
                continue
            available = right - line["x0"]
            used = line["x1"] - line["x0"]
            if available <= 8 or used <= 4:
                continue
            fill = used / available
            if fill < 0.35:
                continue
            char_len = len(re.sub(r"\s+", " ", bullet.strip()))
            if char_len < 20:
                continue
            line_len = len(re.sub(r"\s+", " ", line["text"].strip()))
            if line_len < char_len * 0.55 and not _norm_match(bullet).startswith(
                _norm_match(line["text"])[:18]
            ):
                continue
            implied.append(char_len / min(fill, 0.995))

        doc.close()
    except Exception:
        return None

    if len(implied) < 1:
        return None

    calibrated = int(statistics.median(implied))
    return max(80, min(180, calibrated))


def effective_line_chars(tex: str, pdf_bytes: bytes | None = None) -> int:
    """
    Line width target aligned with the compiled PDF preview when available.
    Falls back to LaTeX-structure estimate for fragments or failed compiles.
    """
    if pdf_bytes:
        calibrated = calibrate_line_chars_from_pdf(tex, pdf_bytes)
        if calibrated:
            return calibrated

    if not tex or not _is_complete_document(tex):
        preview_tex = (
            rf"\documentclass[11pt,letterpaper]{{article}}"
            rf"\usepackage[margin={PREVIEW_GEOMETRY_MARGIN_IN}in]{{geometry}}"
            rf"\begin{{itemize}}[leftmargin=0.15in, label={{}}]"
            rf"\item x"
            rf"\end{{itemize}}"
        )
        n = estimate_line_chars(preview_tex)
    else:
        n = estimate_line_chars(tex)
    return max(80, min(150, n))


def line_width_hint(tex: str, pdf_bytes: bytes | None = None) -> str:
    """Human-readable hint for UI."""
    n = effective_line_chars(tex, pdf_bytes)
    if pdf_bytes and calibrate_line_chars_from_pdf(tex, pdf_bytes):
        return f"Measured from your PDF preview (~{n} chars edge-to-edge)"
    return f"Auto-detected line width (~{n} chars edge-to-edge for your template)"
