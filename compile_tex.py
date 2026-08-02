"""Compile LaTeX resume source to PDF for live preview."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

ROLE_USAGE_RE = re.compile(
    r"(^[\s]*\\role(?![a-zA-Z])\{[^}]+\}\{[^}]+\}\{[^}]+\}\{[^}]+\}\s*$)",
    re.MULTILINE,
)

PREVIEW_PREAMBLE = r"""\documentclass[11pt,letterpaper]{article}
\usepackage[utf8]{inputenc}
\usepackage[T1]{fontenc}
\usepackage{lmodern}
\usepackage[margin=0.5in]{geometry}
\usepackage{titlesec}
\usepackage{enumitem}
\usepackage{hyperref}
\usepackage{xcolor}
\pagenumbering{gobble}
\newcommand{\resumeitem}[1]{\item #1}
\newcommand{\rolefit}[4]{%
  \begin{center}%
  \textbf{#1}\hfill\textbf{#2}\\[-0.1em]
  \textit{#3}\hfill\textbf{#4}%
  \end{center}%
}
\newcommand{\role}[4]{%
  \begin{center}%
  \textbf{#1} \hfill \textbf{#2} \\
  \textit{#3} \hfill \textbf{#4}%
  \end{center}%
}
\newcommand{\resumeItem}[1]{\item #1}
\newcommand{\resumeSubheading}[4]{%
  \vspace{-2pt}\item
  \begin{tabular*}{\textwidth}[t]{l@{\extracolsep{\fill}}r}
    \textbf{#1} & #2 \\
    \textit{\small#3} & \textit{\small #4} \\
  \end{tabular*}\vspace{-4pt}%
}
\begin{document}
"""

PREVIEW_POSTAMBLE = "\n\\end{document}\n"

FITLINE_INJECT_RE = re.compile(
    r"^% >>> fitline \(auto-injected\)\s*\n\\usepackage\{fitline\}\s*\n",
    re.MULTILINE,
)

PREVIEW_MACROS = r"""
\newcommand{\resumeitem}[1]{\item #1}
\newcommand{\rolefit}[4]{%
  \begin{center}%
  \textbf{#1}\hfill\textbf{#2}\\[-0.1em]
  \textit{#3}\hfill\textbf{#4}%
  \end{center}%
}
"""

# Splice corruption from older fit_resume versions
_CORRUPT_ENDCENTER = re.compile(r"\\end\{center\\rolefit")
_CORRUPT_ENDCENTER2 = re.compile(r"\\end\{center\\role(?![a-zA-Z])")


def _normalize_document_start(tex: str) -> str:
    """
    Remove stray characters/lines before \\documentclass.
    Fixes pastes like ``e%---`` where a typo sits before the first comment.
    """
    m = re.search(r"\\documentclass\b", tex)
    if not m:
        return tex
    before = tex[: m.start()]
    after = tex[m.start() :]
    cleaned: list[str] = []
    for line in before.splitlines(keepends=True):
        stripped = line.lstrip()
        if not stripped.strip():
            cleaned.append(line)
            continue
        pct = stripped.find("%")
        if pct >= 0 and (pct == 0 or stripped[pct - 1] != "\\"):
            newline = "\n" if line.endswith("\n") else ""
            cleaned.append(stripped[pct:] + newline)
            continue
        # Drop non-comment garbage (e.g. a lone "e" before "% Resume in Latex")
    return "".join(cleaned) + after


def _sanitize_corrupted_tex(tex: str) -> str:
    """Repair known LaTeX corruption patterns from bad section splices."""
    tex = _normalize_document_start(tex)
    if _CORRUPT_ENDCENTER.search(tex) or _CORRUPT_ENDCENTER2.search(tex):
        tex = _CORRUPT_ENDCENTER.sub(r"\\rolefit", tex)
        tex = _CORRUPT_ENDCENTER2.sub(r"\\role", tex)
    # Drop duplicate \end{center} immediately after \role (over-patched sources)
    tex = re.sub(
        r"(\\role(?![a-zA-Z])\{[^}]+\}\{[^}]+\}\{[^}]+\}\{[^}]+\}\s*\n\\end\{center\}\s*\n)\\end\{center\}\s*\n",
        r"\1",
        tex,
    )
    return tex


def _fix_chicago_role_usages(tex: str) -> str:
    """Legacy Chicago \\role macro opens center but never closes it."""
    if r"\newcommand{\role}" not in tex:
        return tex
    role_def = tex.split(r"\newcommand{\role}", 1)[1][:400]
    if r"\end{center}" in role_def:
        return tex

    lines = tex.splitlines(keepends=True)
    out: list[str] = []
    for i, line in enumerate(lines):
        out.append(line)
        stripped = line.rstrip("\n\r")
        if not ROLE_USAGE_RE.match(stripped):
            continue
        if stripped.endswith(r"\end{center}"):
            continue
        nxt = lines[i + 1].strip() if i + 1 < len(lines) else ""
        if nxt == r"\end{center}":
            continue
        nl = "\n" if line.endswith("\n") else ""
        out.append("\\end{center}" + nl)
    return "".join(out)


def _strip_latex_comments(tex: str) -> str:
    """Remove full-line and inline % comments (ignore escaped \\%)."""
    out: list[str] = []
    for line in tex.splitlines(keepends=True):
        cleaned: list[str] = []
        i = 0
        while i < len(line):
            ch = line[i]
            if ch == "%" and (i == 0 or line[i - 1] != "\\"):
                break
            cleaned.append(ch)
            i += 1
        out.append("".join(cleaned))
    return "".join(out)


def _has_documentclass(tex: str) -> bool:
    return bool(re.search(r"\\documentclass\b", _strip_latex_comments(tex)))


def _has_active_begin_document(tex: str) -> bool:
    return bool(re.search(r"\\begin\{document\}", _strip_latex_comments(tex)))


def _has_active_end_document(tex: str) -> bool:
    return bool(re.search(r"\\end\{document\}", _strip_latex_comments(tex)))


def _is_complete_document(tex: str) -> bool:
    stripped = _strip_latex_comments(tex)
    return bool(
        re.search(r"\\documentclass\b", stripped)
        and re.search(r"\\begin\{document\}", stripped)
    )


def _strip_orphan_preamble(tex: str) -> str:
    """Remove fitline injection that was added without a full document."""
    return FITLINE_INJECT_RE.sub("", tex.strip())


def _strip_body_packages(tex: str) -> str:
    """Remove \\usepackage lines from a fragment body (preamble provides them)."""
    return re.sub(r"^\\usepackage(\[[^\]]*\])?\{[^}]+\}\s*\n?", "", tex, flags=re.MULTILINE)


def _wrap_for_preview(tex: str) -> str:
    body = _strip_orphan_preamble(tex)
    if _is_complete_document(body):
        return body
    if _has_documentclass(body):
        body = _insert_begin_document(body)
        if not _has_active_end_document(body):
            body = body.rstrip() + PREVIEW_POSTAMBLE
        return body
    body = _strip_body_packages(body).strip()
    return PREVIEW_PREAMBLE + body + PREVIEW_POSTAMBLE

# pdfLaTeX-only lines that break Tectonic/XeTeX (common in Overleaf resume templates)
PDFLATEX_ONLY = [
    re.compile(r"\\input\{glyphtounicode\}\s*", re.I),
    re.compile(r"\\pdfgentounicode\s*=\s*1\s*", re.I),
    re.compile(r"\\RequirePDFTeX\b[^\n]*\n?", re.I),
    re.compile(r"\\pdfoutput\s*=\s*1\s*", re.I),
    re.compile(r"\\usepackage(\[[^\]]*\])?\{glyphtounicode\}\s*", re.I),
]


def _patch_for_compile(tex: str, for_xetex: bool = False) -> str:
    """Fix common template bugs so preview compiles."""
    tex = _sanitize_corrupted_tex(tex)
    tex = _wrap_for_preview(tex)

    for pattern in PDFLATEX_ONLY:
        tex = pattern.sub("", tex)

    if for_xetex:
        # XeTeX ignores these and they can trigger glyphtounicode via dependencies
        tex = re.sub(
            r"\\usepackage(\[[^\]]*\])?\{inputenc\}\s*",
            "% inputenc not needed for XeTeX preview\n",
            tex,
        )
        tex = re.sub(
            r"\\usepackage(\[[^\]]*\])?\{fontenc\}\s*",
            "% fontenc not needed for XeTeX preview\n",
            tex,
        )

    tex = re.sub(r"^\\usepackage(\[[^\]]*\])?\{fitline\}\s*\n?", "", tex, flags=re.MULTILINE)
    tex = FITLINE_INJECT_RE.sub("", tex)
    if r"\rolefit{" in tex and r"\newcommand{\rolefit}" not in tex:
        if r"\begin{document}" in tex:
            tex = tex.replace(r"\begin{document}", PREVIEW_MACROS + r"\begin{document}", 1)

    tex = _fix_chicago_role_usages(tex)

    return tex


def _insert_begin_document(tex: str) -> str:
    if _has_active_begin_document(tex):
        return tex
    markers = (
        r"\name{",
        r"\contact{",
        r"\section{",
        r"\role{",
        r"\rolefit{",
        r"\resumeSubheading{",
        r"\resumeSubHeadingListStart",
        r"\resumeItemListStart",
        r"\begin{center}",
        r"\begin{itemize}",
    )
    marker_pat = r"(?m)^\s*(?:" + "|".join(re.escape(m) for m in markers) + ")"
    m = re.search(marker_pat, tex)
    if m:
        insert_at = m.start()
        return tex[:insert_at].rstrip() + "\n\n\\begin{document}\n\n" + tex[insert_at:].lstrip()
    return tex.rstrip() + "\n\\begin{document}\n"


def _fix_stray_item_braces(tex: str) -> str:
    """Remove trailing } accidentally appended to item lines."""
    lines: list[str] = []
    for line in tex.splitlines(keepends=True):
        stripped = line.rstrip("\n\r")
        newline = "\n" if line.endswith("\n") else ""
        m = re.match(r"^(\s*)\\item\s+(.*)\}\s*$", stripped)
        if m and m.group(2).count("{") < m.group(2).count("}"):
            lines.append(f"{m.group(1)}\\item {m.group(2).rstrip('}')}{newline}")
            continue
        m2 = re.match(r"^(\s*)\\resumeItem\{(.*)\}\}\s*$", stripped)
        if m2:
            lines.append(f"{m2.group(1)}\\resumeItem{{{m2.group(2)}}}{newline}")
            continue
        lines.append(line)
    return "".join(lines)


def _force_preview_document(tex: str) -> str:
    """Wrap resume body in a self-contained preview document (drops broken preamble)."""
    body = _strip_orphan_preamble(tex)
    stripped = _strip_latex_comments(body)
    if _has_active_begin_document(stripped):
        m = re.search(r"\\begin\{document\}", stripped)
        if m:
            start = m.end()
            end_match = re.search(r"\\end\{document\}", stripped[m.end() :])
            end = m.end() + end_match.start() if end_match else len(stripped)
            body = stripped[start:end].strip()
    else:
        body = re.sub(r"\\documentclass[^\n]*\n?", "", stripped)
        body = _strip_body_packages(body).strip()
    return PREVIEW_PREAMBLE + body + PREVIEW_POSTAMBLE


def auto_repair_tex(tex: str, error: str | None = None) -> tuple[str, str | None]:
    """
    Repair common LaTeX structure problems for preview.
    Returns (repaired_tex, short user-facing notice).
    """
    original = tex
    fixes: list[str] = []
    err = (error or "").lower()

    tex = _sanitize_corrupted_tex(tex)
    tex = _strip_orphan_preamble(tex)

    missing_begin = "missing" in err and "begin{document}" in err
    preamble_order = (
        "usepackage before \\documentclass" in err
        or "can be used only in preamble" in err
    )

    if preamble_order or (
        tex.strip().startswith(r"\usepackage") and not _has_documentclass(tex)
    ):
        tex = _force_preview_document(tex)
        fixes.append("fixed the document structure for preview")

    elif missing_begin or not _is_complete_document(tex):
        if not _has_documentclass(tex):
            tex = _force_preview_document(tex)
            fixes.append("wrapped your content in a preview document")
        else:
            if not _has_active_begin_document(tex):
                tex = _insert_begin_document(tex)
                fixes.append("added \\begin{document}")
            if not _has_active_end_document(tex):
                tex = tex.rstrip() + PREVIEW_POSTAMBLE
                fixes.append("added \\end{document}")
        if missing_begin and tex == original:
            tex = _force_preview_document(tex)
            fixes.append("fixed the document structure for preview")

    if any(k in err for k in ("extra }", "forgotten \\endgroup", "forgotten $")):
        tex = _fix_stray_item_braces(tex)
        fixes.append("fixed bullet brace formatting")

    if tex != original:
        if fixes:
            notice = "I fixed this for you (" + ", ".join(fixes) + ")."
        else:
            notice = "I fixed your LaTeX so the preview can render."
        return tex, notice
    return tex, None


def _compile_in_temp(tex: str, *, for_xetex: bool) -> tuple[bytes | None, str | None]:
    with tempfile.TemporaryDirectory(prefix="resume-preview-") as tmp:
        work = Path(tmp)
        tex_path = work / "resume.tex"
        tex_path.write_text(tex, encoding="utf-8")
        try:
            pdflatex = _find_pdflatex()
            if pdflatex and not for_xetex:
                pdf, err = _compile_pdflatex(work)
                if pdf:
                    return pdf, None
                if err:
                    tex2 = _patch_for_compile(tex, for_xetex=True)
                    tex_path.write_text(tex2, encoding="utf-8")
            return _compile_tectonic(work)
        except subprocess.TimeoutExpired:
            return None, "Compile timed out (120s)"
        except OSError as e:
            return None, str(e)


def _find_pdflatex() -> str | None:
    path = shutil.which("pdflatex")
    if path:
        return path
    # BasicTeX / MacTeX default install location on macOS
    for candidate in (
        Path("/Library/TeX/texbin/pdflatex"),
        Path("/usr/local/texlive/2024/bin/universal-darwin/pdflatex"),
        Path("/usr/local/texlive/2023/bin/universal-darwin/pdflatex"),
    ):
        if candidate.exists():
            return str(candidate)
    return None


def _find_tectonic() -> str | None:
    path = shutil.which("tectonic")
    if path:
        return path
    for candidate in (
        Path("/opt/homebrew/bin/tectonic"),
        Path("/usr/local/bin/tectonic"),
    ):
        if candidate.exists():
            return str(candidate)
    return None


def _compile_pdflatex(work: Path) -> tuple[bytes | None, str | None]:
    pdflatex = _find_pdflatex()
    if not pdflatex:
        return None, None  # signal fallback

    env = os.environ.copy()
    texbin = Path(pdflatex).parent
    if str(texbin) not in env.get("PATH", ""):
        env["PATH"] = f"{texbin}:{env.get('PATH', '')}"

    for _ in range(2):  # two passes for references
        result = subprocess.run(
            [pdflatex, "-interaction=nonstopmode", "-halt-on-error", "resume.tex"],
            cwd=work,
            capture_output=True,
            text=True,
            timeout=120,
            env=env,
        )

    pdf_path = work / "resume.pdf"
    if pdf_path.exists():
        return pdf_path.read_bytes(), None

    return None, _extract_error(result.stdout + result.stderr)


def _compile_tectonic(work: Path) -> tuple[bytes | None, str | None]:
    tectonic = _find_tectonic()
    if not tectonic:
        return None, (
            "No LaTeX compiler found. Install one of:\n"
            "• `brew install tectonic` (fastest)\n"
            "• `brew install --cask basictex` then restart the app"
        )

    env = os.environ.copy()
    tectonic_bin = Path(tectonic).parent
    if str(tectonic_bin) not in env.get("PATH", ""):
        env["PATH"] = f"{tectonic_bin}:{env.get('PATH', '')}"

    result = subprocess.run(
        [tectonic, "resume.tex"],
        cwd=work,
        capture_output=True,
        text=True,
        timeout=120,
        env=env,
    )

    pdf_path = work / "resume.pdf"
    if pdf_path.exists():
        return pdf_path.read_bytes(), None

    return None, _extract_error(result.stderr + result.stdout)


def _extract_error(log: str) -> str:
    for line in log.splitlines():
        if line.startswith("error:"):
            return line.replace("error:", "").strip()
        if line.startswith("! "):
            return line[2:].strip()
    return log.strip()[-400:] if log.strip() else "PDF compile failed"


def sanitize_tex(tex: str) -> str:
    """Repair known LaTeX corruption before storing or compiling."""
    return _sanitize_corrupted_tex(tex)


def compile_tex_to_pdf(tex: str) -> tuple[bytes | None, str | None, str | None, str | None]:
    """
    Compile LaTeX string to PDF bytes.
    Returns (pdf_bytes, error_message, repaired_tex_or_none, auto_fix_notice).
    On preview errors, attempts automatic repairs before giving up.
    """
    pdflatex = _find_pdflatex()
    for_xetex = pdflatex is None
    working = tex
    fix_notice: str | None = None

    if not _is_complete_document(tex):
        repaired, notice = auto_repair_tex(tex)
        if repaired != tex:
            working = repaired
            fix_notice = notice

    for attempt in range(2):
        patched = _patch_for_compile(working, for_xetex=for_xetex)
        pdf, err = _compile_in_temp(patched, for_xetex=for_xetex)
        if pdf:
            repaired = working if working != tex else None
            return pdf, None, repaired, fix_notice

        if attempt == 0:
            repaired, notice = auto_repair_tex(working, err)
            if repaired != working:
                working = repaired
                fix_notice = notice or fix_notice
                continue
            err_l = (err or "").lower()
            if "missing" in err_l and "begin{document}" in err_l:
                forced = _force_preview_document(working)
                if forced != working:
                    working = forced
                    fix_notice = fix_notice or (
                        "I fixed this for you (fixed the document structure for preview)."
                    )
                    continue
        return None, err, None, None

    return None, err, None, None
