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


def _sanitize_corrupted_tex(tex: str) -> str:
    """Repair known LaTeX corruption patterns from bad section splices."""
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


def _is_complete_document(tex: str) -> bool:
    return bool(re.search(r"\\documentclass\b", tex) and re.search(r"\\begin\{document\}", tex))


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
    if r"\begin{document}" in tex:
        return tex
    markers = (
        r"\name{",
        r"\contact{",
        r"\section{",
        r"\role{",
        r"\rolefit{",
        r"\resumeSubheading{",
        r"\begin{center}",
        r"\begin{itemize}",
    )
    insert_at = len(tex)
    for marker in markers:
        pos = tex.find(marker)
        if pos >= 0:
            insert_at = min(insert_at, pos)
    if insert_at < len(tex):
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

    needs_document = (
        ("missing" in err and "begin{document}" in err)
        or not _is_complete_document(tex)
    )
    if needs_document:
        if not re.search(r"\\documentclass\b", tex):
            tex = _strip_body_packages(tex).strip()
            tex = PREVIEW_PREAMBLE + tex + PREVIEW_POSTAMBLE
            fixes.append("wrapped content in a preview document")
        else:
            if not re.search(r"\\begin\{document\}", tex):
                tex = _insert_begin_document(tex)
                fixes.append("added \\begin{document}")
            if not re.search(r"\\end\{document\}", tex):
                tex = tex.rstrip() + PREVIEW_POSTAMBLE
                fixes.append("added \\end{document}")

    if (
        "usepackage before \\documentclass" in err
        or "can be used only in preamble" in err
        or (
            tex.strip().startswith(r"\usepackage")
            and not re.search(r"\\documentclass\b", tex)
        )
    ):
        tex = _strip_orphan_preamble(tex)
        if not _is_complete_document(tex):
            tex = _strip_body_packages(tex).strip()
            tex = PREVIEW_PREAMBLE + tex + PREVIEW_POSTAMBLE
            fixes.append("fixed package order for preview")

    if any(k in err for k in ("extra }", "forgotten \\endgroup", "forgotten $")):
        tex = _fix_stray_item_braces(tex)
        fixes.append("fixed bullet brace formatting")

    if tex != original:
        if fixes:
            notice = "I auto-fixed the preview (" + ", ".join(fixes) + ")."
        else:
            notice = "I auto-fixed the LaTeX so the preview can render."
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
    # BasicTeX default install location on macOS
    mac_path = Path("/Library/TeX/texbin/pdflatex")
    if mac_path.exists():
        return str(mac_path)
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
    tectonic = shutil.which("tectonic")
    if not tectonic:
        return None, "No LaTeX compiler found. Run: brew install --cask basictex"

    result = subprocess.run(
        [tectonic, "resume.tex"],
        cwd=work,
        capture_output=True,
        text=True,
        timeout=120,
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
            repaired, notice = auto_repair_tex(tex, err)
            if repaired != tex:
                working = repaired
                fix_notice = notice or fix_notice
                continue
        return None, err, None, None

    return None, err, None, None
