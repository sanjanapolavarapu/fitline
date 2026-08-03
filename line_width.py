"""Estimate how many characters fit on one resume bullet line from LaTeX source."""

from __future__ import annotations

import re

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

    # Jake's / fullpage-style resumes widen \\textwidth directly
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
    lm2 = re.search(r"leftmargin\s*=\s*([\d.]+)\s*(in|cm|mm|pt)?", tex)
    if lm2:
        indent_in = _to_inches(float(lm2.group(1)), lm2.group(2) or "pt")
    return indent_in


def _font_size_pt(tex: str) -> float:
    pt = 11.0
    dc = re.search(r"\\documentclass(\[[^\]]*\])?", tex)
    if dc and dc.group(1):
        pm = re.search(r"(\d+(?:\.\d+)?)\s*pt", dc.group(1))
        if pm:
            pt = float(pm.group(1))
    return pt


def _char_width_in(tex: str, pt: float) -> float:
    char_w_in = 0.073 * (pt / 11.0)
    if re.search(r"\\usepackage.*\{times\}|mathptmx|newtx", tex, re.I):
        char_w_in *= 0.92
    elif "helvet" in tex.lower() or "sans" in tex.lower():
        char_w_in *= 1.08
    if re.search(r"\\usepackage.*\{lmodern\}", tex, re.I):
        # Latin Modern renders narrower than our default cm estimate in pdflatex preview
        char_w_in *= 0.94
    if re.search(r"\\resumeItem.*\\small|\\item\\small|\\small\{", tex, re.I) or re.search(
        r"\\newcommand\{\\resumeItem\}", tex, re.I
    ):
        # Jake's resumeItem renders bullets in \\small (~10pt)
        char_w_in *= 10.0 / 11.0
    return char_w_in


def estimate_line_chars(tex: str) -> int:
    """
    Estimate characters per bullet line from document class, margins, font, and list indent.
    Used internally — the AI is told to fill the line edge-to-edge, not to count chars.
    """
    text_w = _text_width_inches(tex)
    indent_in = _bullet_indent_in(tex)
    pt = _font_size_pt(tex)
    char_w_in = _char_width_in(tex, pt)

    bullet_w = max(text_w - indent_in, text_w * 0.92)
    chars = int(bullet_w / char_w_in)
    return max(80, min(115, chars))


def _is_complete_document(tex: str) -> bool:
    return bool(re.search(r"\\documentclass\b", tex) and re.search(r"\\begin\{document\}", tex))


def effective_line_chars(tex: str) -> int:
    """
    Line width target that matches what the in-app PDF preview actually renders.
    Fragment sources are wrapped with compile_tex's 0.5in preview geometry.
    """
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
    return max(80, min(115, n))


def line_width_hint(tex: str) -> str:
    """Human-readable hint for UI."""
    n = effective_line_chars(tex)
    return f"Auto-detected line width (~{n} chars edge-to-edge for your template)"
