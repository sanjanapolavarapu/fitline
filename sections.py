"""Parse experience / project blocks from LaTeX resumes."""

from __future__ import annotations

import re
from dataclasses import dataclass

LIST_ENV_NAMES = ("itemize", "tightemize", "compactitem", "enumerate")

ITEMIZE_RE = re.compile(
    r"\\begin\{itemize\}(\[.*?\])?(.*?)\\end\{itemize\}",
    re.DOTALL,
)

RESUME_ITEM_LIST_RE = re.compile(
    r"\\resumeItemListStart(.*?)\\resumeItemListEnd",
    re.DOTALL,
)

SKIP_SECTIONS = frozenset(
    {"skills", "skill", "education", "coursework", "certifications", "certification", "interests", "languages"}
)

# Jake / Overleaf list wrapper macros — never treat as company or job titles
RESUME_MACRO_NAMES = frozenset(
    {
        "resumesubheadingliststart",
        "resumesubheadinglistend",
        "resumeitemliststart",
        "resumeitemlistend",
        "resumeitem",
        "resumeitemlist",
        "resumesubheading",
        "resumeprojectheading",
        "resumeprojectheadingliststart",
        "resumeprojectheadinglistend",
    }
)

ROLE_CMD_RE = re.compile(r"\\role(?:fit)?(?![\w-])\s*", re.MULTILINE)
ROLE_USE_RE = re.compile(r"\\role(?:fit)?(?![\w-])\s*\{", re.MULTILINE)

SECTION_BREAK_RE = re.compile(
    r"\\(?:section|role(?:fit)?|resumeSubheading|resumeProjectHeading)\s*[\{\[]",
    re.MULTILINE,
)

SUBHEADING_CMD_RE = re.compile(r"\\resumeSubheading\s*", re.MULTILINE)
PROJECT_HEADING_CMD_RE = re.compile(r"\\resumeProjectHeading\s*", re.MULTILINE)
CVENTRY_CMD_RE = re.compile(r"\\cventry\s*", re.MULTILINE)


def _list_patterns() -> list[re.Pattern[str]]:
    patterns = [
        re.compile(
            rf"\\begin\{{{env}\}}(\[.*?\])?(.*?)\\end\{{{env}\}}",
            re.DOTALL,
        )
        for env in LIST_ENV_NAMES
    ]
    patterns.append(RESUME_ITEM_LIST_RE)
    return patterns


def iter_list_blocks(tex: str):
    """Yield bullet-list regions (itemize, tightemize, resumeItemListStart, etc.)."""
    seen: set[tuple[int, int]] = set()
    for pat in _list_patterns():
        for m in pat.finditer(tex):
            span = (m.start(), m.end())
            if span in seen:
                continue
            seen.add(span)
            yield m


def _block_has_bullets(text: str) -> bool:
    return bool(re.search(r"\\item\b", text) or re.search(r"\\resumeItem\{", text))


def _count_list_blocks(tex: str) -> int:
    return sum(1 for _ in iter_list_blocks(tex))


def _section_name_at(tex: str, pos: int) -> str:
    current = ""
    for m in re.finditer(r"\\section\{([^}]+)\}", tex, re.I):
        if m.start() <= pos:
            current = m.group(1).strip().lower()
    return current


def _should_skip_itemize(tex: str, iz_start: int) -> bool:
    section = _section_name_at(tex, iz_start)
    if not section:
        return False
    return any(s in section for s in SKIP_SECTIONS)


def _company_from_plain_header(header: str) -> tuple[str, str, str]:
    """Extract company/title/dates from plain or lightly formatted header lines."""
    lines = [ln.strip() for ln in header.splitlines() if ln.strip()]
    for line in reversed(lines):
        if line.startswith("%"):
            continue
        clean = _strip_latex(line)
        if not clean or clean.lower().startswith("professional experience"):
            continue
        if clean.startswith("\\section") or _is_resume_macro_label(clean):
            continue
        # e.g. "IBM — Software Engineer (2020–2023)" or "IBM | Engineer"
        for sep in (" — ", " – ", " - ", " | ", " · "):
            if sep in clean:
                left, right = clean.split(sep, 1)
                return left.strip(), right.strip(), ""
        if re.search(r"[A-Za-z]", clean) and len(clean) <= 80:
            return clean, "", ""
    return "", "", ""


def diagnose_tex(tex: str) -> dict[str, int | list[str]]:
    body = tex.split(r"\begin{document}")[-1] if r"\begin{document}" in tex else tex
    roles = len(ROLE_USE_RE.findall(body))
    subheadings = len(re.findall(r"\\resumeSubheading\s*\{", body))
    itemizes = _count_list_blocks(body)
    hints = [e.company for e in parse_experiences(tex) if not _is_resume_macro_label(e.company)]
    if not hints:
        for iz in iter_list_blocks(body):
            if _should_skip_itemize(body, iz.start()):
                continue
            header = body[max(0, iz.start() - 1200) : iz.start()]
            if not _block_has_bullets(iz.group(0)):
                continue
            for token in re.findall(r"\\role(?:fit)?(?![\w-])\s*\{([^{}]+)\}", header):
                name = _strip_latex(token)
                if name and name[0].isalnum():
                    hints.append(name)
            co, _, _ = _company_from_plain_header(header)
            if co and co[0].isalnum():
                hints.append(co)
    return {
        "role_commands": roles,
        "subheading_commands": subheadings,
        "itemize_blocks": itemizes,
        "company_hints": list(dict.fromkeys(hints)),
    }


def _read_braced_arg(tex: str, pos: int) -> tuple[str, int] | None:
    """Read a single {…} argument, respecting nested braces."""
    while pos < len(tex) and tex[pos].isspace():
        pos += 1
    if pos >= len(tex) or tex[pos] != "{":
        return None

    depth = 1
    start = pos + 1
    pos += 1
    while pos < len(tex):
        ch = tex[pos]
        if ch == "\\":
            pos += 2
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return tex[start:pos], pos + 1
        pos += 1
    return None


def _strip_latex(text: str) -> str:
    """Flatten simple formatting macros for display/matching."""
    prev = None
    out = text.strip()
    while prev != out:
        prev = out
        out = re.sub(r"\\textbf\{([^{}]*)\}", r"\1", out)
        out = re.sub(r"\\textit\{([^{}]*)\}", r"\1", out)
        out = re.sub(r"\\emph\{([^{}]*)\}", r"\1", out)
        out = re.sub(r"\\textsc\{([^{}]*)\}", r"\1", out)
        out = re.sub(r"\\hfill\s*", " ", out)
        out = re.sub(r"\\\\(\[[^\]]*\])?\s*", " ", out)
        out = re.sub(r"\s+", " ", out).strip()
    return out


def _is_resume_macro_label(text: str) -> bool:
    """True for LaTeX wrapper macros like \\resumeSubHeadingListStart."""
    if not text or not text.strip():
        return False
    clean = _strip_latex(text).strip().lower().lstrip("\\")
    clean = re.sub(r"[^a-z]", "", clean)
    if clean in RESUME_MACRO_NAMES:
        return True
    return bool(clean.startswith("resume") and clean.endswith(("liststart", "listend")))


def _is_valid_experience_block(block: "ExperienceBlock") -> bool:
    for field in (block.company, block.title, block.label):
        if _is_resume_macro_label(field):
            return False
    return bool((block.company or block.title or "").strip())


def _is_wrapper_list_block(block_text: str) -> bool:
    """Outer Jake list that wraps subheadings — not a bullet section to fix."""
    if re.search(r"\\resumeSubheading\s*\{", block_text) and not re.search(
        r"\\resumeItem\{", block_text
    ):
        return True
    if re.search(r"\\resumeProjectHeading\s*\{", block_text) and not re.search(
        r"\\resumeItem\{", block_text
    ):
        return True
    return False


def _read_n_args(tex: str, pos: int, n: int) -> tuple[list[str], int] | None:
    args: list[str] = []
    for _ in range(n):
        parsed = _read_braced_arg(tex, pos)
        if not parsed:
            return None
        args.append(_strip_latex(parsed[0]))
        pos = parsed[1]
    return args, pos


def _list_for_role(after: str) -> re.Match[str] | None:
    """Bullet list must belong to this role — stop at next section or role."""
    chunk = re.split(r"\\section\{", after, maxsplit=1)[0]
    chunk = re.split(r"\\role(?:fit)?\s*\{", chunk, maxsplit=1)[0]
    chunk = re.split(r"\\resumeSubheading\s*\{", chunk, maxsplit=1)[0]
    chunk = re.split(r"\\resumeProjectHeading\s*\{", chunk, maxsplit=1)[0]
    for pat in _list_patterns():
        m = pat.search(chunk)
        if m and _block_has_bullets(m.group(0)):
            return m
    # Jake's resume: \resumeItem lines without a list wrapper
    if re.search(r"\\resumeItem\{", chunk):
        m = re.search(r"((?:\s*\\resumeItem\{[^{}]*\}\s*)+)", chunk)
        if m:
            return m
    return None


def _block_from_command(
    tex: str,
    cmd_start: int,
    args_end: int,
    company: str,
    location: str,
    title: str,
    dates: str,
) -> ExperienceBlock | None:
    after = tex[args_end:]
    iz = _list_for_role(after)
    if not iz:
        return None
    return ExperienceBlock(
        company=company,
        location=location,
        title=title,
        dates=dates,
        start=cmd_start,
        end=args_end + iz.end(),
        section_name=_section_name_at(tex, cmd_start),
    )


def _parse_role_commands(tex: str) -> list[ExperienceBlock]:
    blocks: list[ExperienceBlock] = []
    for m in ROLE_CMD_RE.finditer(tex):
        parsed = _read_n_args(tex, m.end(), 4)
        if not parsed:
            continue
        args, args_end = parsed
        block = _block_from_command(
            tex, m.start(), args_end, args[0], args[1], args[2], args[3]
        )
        if block:
            blocks.append(block)
    return blocks


def _parse_subheading_commands(tex: str) -> list[ExperienceBlock]:
    """Jake's Resume: \\resumeSubheading{title}{dates}{company}{location}."""
    blocks: list[ExperienceBlock] = []
    for m in SUBHEADING_CMD_RE.finditer(tex):
        parsed = _read_n_args(tex, m.end(), 4)
        if not parsed:
            continue
        title, dates, company, location = parsed[0]
        block = _block_from_command(
            tex, m.start(), parsed[1], company, location, title, dates
        )
        if block:
            blocks.append(block)
    return blocks


def _parse_project_heading_commands(tex: str) -> list[ExperienceBlock]:
    blocks: list[ExperienceBlock] = []
    for m in PROJECT_HEADING_CMD_RE.finditer(tex):
        parsed = _read_n_args(tex, m.end(), 2)
        if not parsed:
            continue
        title, dates = parsed[0]
        block = _block_from_command(
            tex, m.start(), parsed[1], title, "", "Project", dates
        )
        if block:
            blocks.append(block)
    return blocks


def _parse_cventry_commands(tex: str) -> list[ExperienceBlock]:
    """moderncv: \\cventry{dates}{title}{company}{location}{}{}."""
    blocks: list[ExperienceBlock] = []
    for m in CVENTRY_CMD_RE.finditer(tex):
        parsed = _read_n_args(tex, m.end(), 6)
        if not parsed:
            continue
        dates, title, company, location = parsed[0][:4]
        block = _block_from_command(
            tex, m.start(), parsed[1], company, location, title, dates
        )
        if block:
            blocks.append(block)
    return blocks


def _parse_itemize_fallback(tex: str) -> list[ExperienceBlock]:
    """When no \\role macros match, pair itemize blocks with nearby headers."""
    blocks: list[ExperienceBlock] = []
    seen: set[tuple[int, int]] = set()

    for iz in iter_list_blocks(tex):
        span = (iz.start(), iz.end())
        if span in seen:
            continue
        if _should_skip_itemize(tex, iz.start()):
            continue
        if _is_wrapper_list_block(iz.group(0)):
            continue

        header = tex[max(0, iz.start() - 1200) : iz.start()]
        if not _block_has_bullets(iz.group(0)):
            continue

        company = title = location = dates = ""
        role_m = None
        for rm in ROLE_CMD_RE.finditer(header):
            role_m = rm
        if role_m:
            parsed = _read_n_args(tex, role_m.end(), 4)
            if parsed:
                args, _ = parsed
                company, location, title, dates = args
                start = role_m.start()
            else:
                start = iz.start()
        else:
            sub_m = None
            for sm in SUBHEADING_CMD_RE.finditer(header):
                sub_m = sm
            if sub_m:
                parsed = _read_n_args(tex, sub_m.end(), 4)
                if parsed:
                    title, dates, company, location = parsed[0]
                    start = sub_m.start()
                else:
                    start = iz.start()
            else:
                bold = list(re.finditer(r"\\textbf\{([^{}]+)\}", header))
                if bold:
                    company = _strip_latex(bold[-1].group(1))
                    title_m = re.findall(r"\\textit\{([^{}]+)\}", header)
                    title = _strip_latex(title_m[-1]) if title_m else ""
                    dates_m = re.search(
                        r"(\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[^\\{}]*"
                        r"|\b\d{4}\s*[-–—]\s*(?:Present|\d{4}))",
                        header,
                        re.I,
                    )
                    dates = dates_m.group(1).strip() if dates_m else ""
                    start = bold[-1].start() + max(0, iz.start() - 1200)
                else:
                    company, title, dates = _company_from_plain_header(header)
                    if not company or _is_resume_macro_label(company):
                        continue
                    start = max(0, iz.start() - 1200)

        if not company and not title:
            continue
        if _is_resume_macro_label(company) or _is_resume_macro_label(title):
            continue

        seen.add(span)
        blocks.append(
            ExperienceBlock(
                company=company or title,
                location=location,
                title=title or company,
                dates=dates,
                start=start,
                end=iz.end(),
                section_name=_section_name_at(tex, iz.start()),
            )
        )

    blocks.sort(key=lambda b: b.start)
    return blocks


@dataclass
class ExperienceBlock:
    company: str
    location: str
    title: str
    dates: str
    start: int
    end: int
    section_name: str = ""

    @property
    def label(self) -> str:
        name = self.company or self.title or "Section"
        role = self.title if self.title and self.title != self.company else ""
        sec = (self.section_name or "").strip().lower()
        if sec and sec not in {"experience", "professional experience", "work experience"}:
            sec_label = self.section_name.strip().title()
            if name.lower() == sec or name.lower() == sec_label.lower():
                return sec_label
            if role and role not in (name, "Bullets", "Project", "Entry"):
                return f"{sec_label}: {name} — {role}"
            return f"{sec_label}: {name}"
        if role and role not in (name, "Bullets"):
            return f"{name} — {role}"
        return name


def _header_before_itemize(tex: str, iz_start: int, *, max_chars: int = 1200) -> str:
    """Header text immediately above a bullet list, staying within the current \\section."""
    chunk = tex[max(0, iz_start - max_chars) : iz_start]
    parts = re.split(r"\\section\{[^}]+\}", chunk, flags=re.I)
    return parts[-1] if parts else chunk


def _block_specificity(block: ExperienceBlock) -> int:
    score = 0
    if block.dates:
        score += 4
    if block.section_name:
        score += 1
    if block.title not in ("Bullets", "Entry"):
        score += 2
    return score


def _merge_experience_blocks(blocks: list[ExperienceBlock]) -> list[ExperienceBlock]:
    if not blocks:
        return []
    ordered = sorted(blocks, key=lambda b: (b.start, -(b.end - b.start)))
    drop = [False] * len(ordered)
    for i, outer in enumerate(ordered):
        if drop[i]:
            continue
        for j, inner in enumerate(ordered):
            if i == j or drop[j]:
                continue
            if inner.start >= outer.start and inner.end <= outer.end:
                if _block_specificity(inner) >= _block_specificity(outer):
                    drop[i] = True
                else:
                    drop[j] = True
    kept = [b for b, d in zip(ordered, drop) if not d]
    return sorted(kept, key=lambda b: b.start)


def _uncovered_itemize_blocks(tex: str, existing: list[ExperienceBlock]) -> list[ExperienceBlock]:
    """Bullet lists under Projects, Leadership, Awards, etc. not already tied to a heading macro."""
    extra: list[ExperienceBlock] = []
    for iz in iter_list_blocks(tex):
        if _should_skip_itemize(tex, iz.start()):
            continue
        if _is_wrapper_list_block(iz.group(0)):
            continue
        if not _block_has_bullets(iz.group(0)):
            continue
        if any(b.start <= iz.start() and iz.end() <= b.end for b in existing):
            continue

        section = _section_name_at(tex, iz.start())
        header = _header_before_itemize(tex, iz.start())
        company = title = ""

        for rm in ROLE_CMD_RE.finditer(header):
            parsed = _read_n_args(tex, rm.end(), 4)
            if parsed:
                company, _, title, _ = parsed[0]
                break
        else:
            sub_m = None
            for sm in SUBHEADING_CMD_RE.finditer(header):
                sub_m = sm
            if sub_m:
                parsed = _read_n_args(tex, sub_m.end(), 4)
                if parsed:
                    title, _, company, _ = parsed[0]
            else:
                proj_m = None
                for pm in PROJECT_HEADING_CMD_RE.finditer(header):
                    proj_m = pm
                if proj_m:
                    parsed = _read_n_args(tex, proj_m.end(), 2)
                    if parsed:
                        title, _ = parsed[0]
                        company = title
                else:
                    bold = list(re.finditer(r"\\textbf\{([^{}]+)\}", header))
                    if bold:
                        company = _strip_latex(bold[-1].group(1))
                        title_m = re.findall(r"\\textit\{([^{}]+)\}", header)
                        title = _strip_latex(title_m[-1]) if title_m else ""
                    else:
                        company, title, _ = _company_from_plain_header(header)

        if not company and not title:
            if section:
                company = section.title()
                title = "Bullets"
            else:
                continue

        if _is_resume_macro_label(company) or _is_resume_macro_label(title):
            continue

        extra.append(
            ExperienceBlock(
                company=company or title,
                location="",
                title=title or company,
                dates="",
                start=iz.start(),
                end=iz.end(),
                section_name=section,
            )
        )
    return extra


def parse_experiences(tex: str) -> list[ExperienceBlock]:
    """All fixable resume sections: experience, projects, leadership, volunteer, awards, etc."""
    blocks: list[ExperienceBlock] = []
    blocks.extend(_parse_role_commands(tex))
    blocks.extend(_parse_subheading_commands(tex))
    blocks.extend(_parse_project_heading_commands(tex))
    blocks.extend(_parse_cventry_commands(tex))
    if blocks:
        blocks = _merge_experience_blocks(blocks)
        blocks.extend(_uncovered_itemize_blocks(tex, blocks))
        blocks = _merge_experience_blocks(blocks)
    else:
        blocks = _parse_itemize_fallback(tex)
    return [b for b in blocks if _is_valid_experience_block(b)]


def _matches_query(block: ExperienceBlock, q: str) -> bool:
    hay = f"{block.label} {block.company} {block.title} {block.location} {block.section_name}".lower()
    if q in hay:
        return True
    for part in (block.company, block.title):
        if q in part.lower():
            return True
        short = part.split()[0].lower() if part.split() else ""
        if len(short) >= 3 and short == q:
            return True
    return False


def find_experience(tex: str, query: str) -> ExperienceBlock | None:
    """Match by company/title substring (case-insensitive)."""
    q = query.strip().lower()
    if not q or q in ("all", "everything", "entire resume", "all sections"):
        return None

    for block in parse_experiences(tex):
        if block.label.lower() == q:
            return block
        if _matches_query(block, q):
            return block

    # Match \\role{...IBM...} anywhere in document
    for m in ROLE_CMD_RE.finditer(tex):
        parsed = _read_n_args(tex, m.end(), 4)
        if not parsed:
            continue
        args, args_end = parsed
        hay = " ".join(args).lower()
        if re.search(rf"\b{re.escape(q)}\b", hay):
            after = tex[args_end:]
            iz = _list_for_role(after)
            if iz and _block_has_bullets(iz.group(0)):
                return ExperienceBlock(
                    company=args[0],
                    location=args[1],
                    title=args[2],
                    dates=args[3],
                    start=m.start(),
                    end=args_end + iz.end(),
                )

    # Last resort: itemize whose header mentions the company
    for iz in iter_list_blocks(tex):
        if _should_skip_itemize(tex, iz.start()):
            continue
        header = tex[max(0, iz.start() - 1200) : iz.start()]
        if not re.search(rf"\b{re.escape(q)}\b", header, re.I):
            continue
        if not _block_has_bullets(iz.group(0)):
            continue

        company = query.strip()
        title = ""
        for block in parse_experiences(tex):
            if block.start <= iz.start() <= block.end:
                return block

        parsed = None
        for rm in ROLE_CMD_RE.finditer(header):
            parsed = _read_n_args(tex, rm.end(), 4)
            if parsed:
                args, _ = parsed
                company, _, title, _ = args
                start = rm.start() + max(0, iz.start() - 1200)
                break
        if not parsed:
            bold = list(re.finditer(r"\\textbf\{([^{}]+)\}", header))
            if bold:
                company = _strip_latex(bold[-1].group(1))
                title_m = re.findall(r"\\textit\{([^{}]+)\}", header)
                if title_m:
                    title = _strip_latex(title_m[-1])
                start = bold[-1].start() + max(0, iz.start() - 1200)
            else:
                company, title, _ = _company_from_plain_header(header)
                if not company:
                    continue
                start = max(0, iz.start() - 1200)

        return ExperienceBlock(
            company=company,
            location="",
            title=title or company,
            dates="",
            start=start,
            end=iz.end(),
        )

    return None


def _block_from_itemize(
    tex: str,
    iz: re.Match[str],
    *,
    company: str,
    title: str = "Bullets",
    header_start: int | None = None,
) -> ExperienceBlock:
    start = header_start if header_start is not None else iz.start()
    return ExperienceBlock(
        company=company,
        location="",
        title=title,
        dates="",
        start=start,
        end=iz.end(),
        section_name=_section_name_at(tex, start),
    )


def list_itemize_blocks(tex: str) -> list[ExperienceBlock]:
    """All non-skipped bullet-list blocks, best-effort company from header."""
    blocks: list[ExperienceBlock] = []
    for iz in iter_list_blocks(tex):
        if _should_skip_itemize(tex, iz.start()):
            continue
        if not _block_has_bullets(iz.group(0)):
            continue
        header = _header_before_itemize(tex, iz.start())
        company = title = ""
        for rm in ROLE_CMD_RE.finditer(header):
            parsed = _read_n_args(tex, rm.end(), 4)
            if parsed:
                company, _, title, _ = parsed[0]
                blocks.append(
                    _block_from_itemize(
                        tex, iz, company=company, title=title, header_start=rm.start()
                    )
                )
                break
        else:
            bold = list(re.finditer(r"\\textbf\{([^{}]+)\}", header))
            if bold:
                company = _strip_latex(bold[-1].group(1))
                title_m = re.findall(r"\\textit\{([^{}]+)\}", header)
                title = _strip_latex(title_m[-1]) if title_m else "Bullets"
            else:
                company, title, _ = _company_from_plain_header(header)
                if not company:
                    company = "Pasted bullets"
                    title = "Section"
            blocks.append(
                _block_from_itemize(
                    tex,
                    iz,
                    company=company,
                    title=title or "Bullets",
                    header_start=max(0, iz.start() - 200) if company == "Pasted bullets" else None,
                )
            )
    return blocks


def find_best_block(tex: str, query: str | None) -> tuple[ExperienceBlock | None, str | None]:
    """
    Find an experience block to fix. Returns (block, fallback_note).
    Uses company match first, then content search, then lone itemize fallback.
    """
    q = (query or "").strip()
    if q and q.lower() not in ("all sections", "all", "— type company above —"):
        block = find_experience(tex, q)
        if block:
            return block, None

        # Company name might be inside bullet text
        for iz in iter_list_blocks(tex):
            if _should_skip_itemize(tex, iz.start()):
                continue
            body = iz.group(0)
            if q and re.search(rf"\b{re.escape(q)}\b", body, re.I):
                header = tex[max(0, iz.start() - 1200) : iz.start()]
                co, ti, _ = _company_from_plain_header(header)
                return (
                    _block_from_itemize(
                        tex,
                        iz,
                        company=co or q,
                        title=ti or q,
                        header_start=iz.start(),
                    ),
                    f"'{q}' found in bullet text (no job header detected).",
                )

    blocks = list_itemize_blocks(tex)
    if len(blocks) == 1:
        note = None
        if q and q.lower() not in ("all sections", "all", "— type company above —"):
            note = f"'{q}' not in your paste — fixed the only bullet section found."
        return blocks[0], note
    if len(blocks) > 1 and q:
        for b in blocks:
            if _matches_query(b, q.lower()):
                return b, None
    return None, None


def format_not_found_error(tex: str, query: str) -> str:
    diag = diagnose_tex(tex)
    hints = diag["company_hints"]
    msg = f"No section matching **{query}** in your pasted LaTeX."
    if hints:
        msg += f"\n\nSections detected in your paste: **{', '.join(hints[:8])}**"
        msg += "\n\nPick one of those from the dropdown, or paste your full `main.tex` from Overleaf **Source** view."
    elif diag["role_commands"] or diag["itemize_blocks"]:
        msg += (
            f"\n\nWe see `{diag['role_commands']}` role blocks and `{diag['itemize_blocks']}` bullet lists, "
            "but couldn't pair them. Paste the **complete** `main.tex` from Overleaf."
        )
    else:
        msg += "\n\nPaste your full `main.tex` from Overleaf **Source** view (not the PDF)."
        blocks = list_itemize_blocks(tex)
        if len(blocks) == 1:
            msg += "\n\nOr click **Fix pasted bullets** in the sidebar to rewrite the bullet list you pasted."
    return msg


def company_from_message(text: str, experiences: list[ExperienceBlock]) -> ExperienceBlock | None:
    lower = text.lower()
    for block in experiences:
        if block.company.lower() in lower:
            return block
        short = block.company.split()[0].lower()
        if len(short) >= 3 and short in lower:
            return block
    return None


def resolve_selection(tex: str, selection: str | None) -> ExperienceBlock | None:
    """Resolve sidebar dropdown value to an experience block."""
    if not selection or selection.strip().lower() in ("all sections", "all", ""):
        return None
    return find_experience(tex, selection)


def company_query_from_fix_message(text: str) -> str | None:
    """Extract company from messages like 'fix IBM' or 'fix Wells Fargo'."""
    m = re.search(r"\bfix(?:\s+it|\s+this|\s+my\s+resume)?\s+(.+)\s*$", text.strip(), re.I)
    if not m:
        return None
    name = m.group(1).strip().rstrip(".")
    if name.lower() in ("it", "this", "my resume", "all", "everything"):
        return None
    return name
