"""Parse natural-language chat into fix targets and feedback for the AI."""

from __future__ import annotations

import re

from sections import ExperienceBlock, company_from_message, company_query_from_fix_message

FIX_VERBS = re.compile(
    r"\b("
    r"fix|rewrite|revise|update|improve|strengthen|shorten|tighten|"
    r"make|change|adjust|redo|keep\s+more|add\s+back|emphasize|highlight|"
    r"focus\s+on|mention|include|remove|drop|cut|expand|lengthen"
    r")\b",
    re.I,
)

ACCEPT_RE = re.compile(
    r"\b(looks?\s+good|accept|approved?|correct|perfect|yes\s*looks?\s+good|"
    r"that'?s?\s+good|keep\s+it|no\s+changes?)\b",
    re.I,
)

REVISION_HINT = re.compile(
    r"\b("
    r"keep|metric|metrics|percent|%|stronger|weaker|shorter|longer|"
    r"edge-to-edge|edge\s+to\s+edge|bullet|wording|phrase|tone|detail|"
    r"first|second|third|fourth|fifth|1st|2nd|3rd|"
    r"add|remove|mention|include|emphasize|lead\s+with|start\s+with|"
    r"accurate|word|words|line|lines|rewrite|revise|change|fix|"
    r"metric|number|numbers"
    r")\b",
    re.I,
)

SECTION_HINT = re.compile(
    r"\b(?:for|at|on|in|under)\s+(?:the\s+)?(.+?)(?:\s+section|\s+role|\s+job|\s+bullets?|$)",
    re.I,
)

STOP_WORDS = frozenset(
    {
        "make", "this", "that", "with", "from", "have", "keep", "more", "bullet",
        "bullets", "strong", "stronger", "please", "resume", "section", "change",
        "fix", "rewrite", "update", "improve", "about", "need", "want", "like",
        "just", "also", "very", "much", "some", "them", "they", "your", "what",
    }
)

ALL_BULLETS_RE = re.compile(
    r"\b(?:all|every|each)\s+(?:the\s+)?bullets?\b|\bfix\s+(?:them|everything)\b|\bbullets?\s+all\b",
    re.I,
)

ORDINAL_BULLETS = {
    "first": 0,
    "1st": 0,
    "second": 1,
    "2nd": 1,
    "third": 2,
    "3rd": 2,
    "fourth": 3,
    "4th": 3,
    "fifth": 4,
    "5th": 4,
    "sixth": 5,
    "6th": 5,
}


def resolve_bullet_indices(text: str, bullet_count: int) -> set[int] | None:
    """
    Parse which bullets the user wants fixed from chat text.
    Returns None when no specific bullets mentioned (caller should fix all).
    """
    if bullet_count <= 0:
        return None

    lower = text.lower()
    if ALL_BULLETS_RE.search(text):
        return set(range(bullet_count))

    indices: set[int] = set()

    for m in re.finditer(r"\bbullet\s+(\d+)\b", lower):
        idx = int(m.group(1)) - 1
        if 0 <= idx < bullet_count:
            indices.add(idx)

    for m in re.finditer(r"\bbullets?\s+([\d,\sand&]+)", lower):
        chunk = m.group(1)
        for num in re.findall(r"\d+", chunk):
            idx = int(num) - 1
            if 0 <= idx < bullet_count:
                indices.add(idx)

    for word, idx in ORDINAL_BULLETS.items():
        if re.search(rf"\b{word}\s+bullet", lower) and idx < bullet_count:
            indices.add(idx)

    if indices:
        return indices

    if re.search(r"\b(?:that|this|the)\s+bullet\b", lower):
        return {0}

    return None


def _strip_fix_preamble(text: str) -> str:
    t = text.strip()
    t = re.sub(r"^(please|can you|could you|i want to|i need to)\s+", "", t, flags=re.I)
    t = re.sub(
        r"^(fix|rewrite|revise|update|improve|strengthen|make)\s+(?:it|this|my\s+resume|the)?\s*",
        "",
        t,
        flags=re.I,
    )
    return t.strip(" .")


def _match_experience(text: str, experiences: list[ExperienceBlock]) -> ExperienceBlock | None:
    block = company_from_message(text, experiences)
    if block:
        return block

    q = company_query_from_fix_message(text)
    if q:
        for exp in experiences:
            if q.lower() in exp.company.lower() or q.lower() in exp.title.lower():
                return exp
            short = exp.company.split()[0].lower()
            if len(short) >= 3 and short in q.lower():
                return exp

    m = SECTION_HINT.search(text)
    if m:
        hint = m.group(1).strip(" .")
        for exp in experiences:
            if hint.lower() in exp.label.lower() or hint.lower() in exp.company.lower():
                return exp

    lower = text.lower()
    for exp in experiences:
        if exp.company.lower() in lower:
            return exp
        short = exp.company.split()[0].lower()
        if len(short) >= 4 and short in lower:
            return exp
    return None


def _match_by_content(
    text: str,
    experiences: list[ExperienceBlock],
    source_tex: str,
) -> ExperienceBlock | None:
    """Match when user names a technology or accomplishment from a bullet."""
    quoted = re.findall(r'"([^"]+)"|\'([^\']+)\'', text)
    keywords: list[str] = []
    for a, b in quoted:
        keywords.extend(re.findall(r"[a-z0-9]{3,}", (a or b).lower()))
    keywords.extend(
        w
        for w in re.findall(r"[a-z0-9]{4,}", text.lower())
        if w not in STOP_WORDS
    )
    if not keywords:
        return None

    best: ExperienceBlock | None = None
    best_score = 0
    for exp in experiences:
        chunk = source_tex[exp.start : exp.end].lower()
        score = sum(1 for k in keywords if k in chunk)
        if score > best_score:
            best_score = score
            best = exp
    if best_score >= 2 or (best_score == 1 and any(len(k) >= 5 for k in keywords)):
        return best
    return None


def active_section(
    pending_review: dict | None,
    selected_section: str | None,
) -> str | None:
    """Section the user is currently editing — review panel or sidebar pick."""
    if pending_review:
        return pending_review.get("company") or pending_review.get("section")
    if selected_section and selected_section not in (
        "All sections",
        "— type company above —",
    ):
        return selected_section
    return None


def is_accept(text: str) -> bool:
    return bool(ACCEPT_RE.search(text)) and not FIX_VERBS.search(text) and not REVISION_HINT.search(text)


def is_revision_request(text: str) -> bool:
    if FIX_VERBS.search(text) or REVISION_HINT.search(text):
        return True
    return len(_strip_fix_preamble(text)) >= 6


def resolve_target(
    text: str,
    experiences: list[ExperienceBlock],
    *,
    selected_section: str | None = None,
    source_tex: str = "",
    allow_sidebar: bool = False,
) -> str | None:
    block = _match_experience(text, experiences)
    if not block and source_tex:
        block = _match_by_content(text, experiences, source_tex)
    if block:
        return block.label
    q = company_query_from_fix_message(text)
    if q:
        for exp in experiences:
            if q.lower() in exp.company.lower() or q.lower() in exp.title.lower():
                return exp.label
    if allow_sidebar and selected_section and selected_section not in (
        "All sections",
        "— type company above —",
    ):
        return selected_section
    return None


def build_feedback(
    prompt: str,
    *,
    recent_user_messages: list[str] | None = None,
    pending_section: str | None = None,
) -> str:
    """Combine current message with recent chat for AI context."""
    parts: list[str] = []
    if recent_user_messages:
        prior = [m.strip() for m in recent_user_messages if m.strip() and m.strip() != prompt.strip()]
        if prior:
            parts.append("Recent user requests:\n" + "\n".join(f"- {m}" for m in prior[-3:]))
    body = _strip_fix_preamble(prompt)
    if body:
        parts.append(f"Current request: {body}")
    if pending_section:
        parts.append(f"Section being edited: {pending_section}")
    parts.append(
        "Keep each bullet one full line edge-to-edge — if adding metrics or detail, "
        "compress filler elsewhere so the line stays the same length."
    )
    return "\n".join(parts)


def parse_chat_intent(
    prompt: str,
    experiences: list[ExperienceBlock],
    *,
    pending_review: dict | None = None,
    selected_section: str | None = None,
    source_tex: str = "",
    recent_user_messages: list[str] | None = None,
) -> dict:
    """
    Returns dict with keys:
      action: help | accept | fix | none
      target: section label or None
      feedback: str for AI
    """
    text = prompt.strip()
    if not text:
        return {"action": "none", "target": None, "feedback": ""}

    current = active_section(pending_review, selected_section)

    if is_accept(text):
        if pending_review:
            return {"action": "accept", "target": None, "feedback": ""}
        return {"action": "help", "target": None, "feedback": ""}

    explicit = resolve_target(
        text,
        experiences,
        selected_section=selected_section,
        source_tex=source_tex,
        allow_sidebar=False,
    )
    target = explicit or current

    if target and is_revision_request(text):
        return {
            "action": "fix",
            "target": target,
            "feedback": build_feedback(
                text,
                recent_user_messages=recent_user_messages,
                pending_section=target,
            ),
        }

    wants_fix = bool(FIX_VERBS.search(text))
    if experiences and wants_fix:
        if not target:
            target = resolve_target(
                text,
                experiences,
                selected_section=selected_section,
                source_tex=source_tex,
                allow_sidebar=True,
            ) or current
        feedback = build_feedback(
            text,
            recent_user_messages=recent_user_messages,
            pending_section=target,
        )
        return {
            "action": "fix" if target else "help",
            "target": target,
            "feedback": feedback if len(_strip_fix_preamble(text)) > 3 else "",
        }

    return {"action": "help", "target": None, "feedback": ""}


def help_message(
    experiences: list[ExperienceBlock],
    *,
    active_section: str | None = None,
) -> str:
    names = ", ".join(e.company for e in experiences[:3]) if experiences else "Acme Corp"
    if active_section:
        return (
            f"Tell me what to change for **{active_section}** — I'll rewrite those bullets.\n\n"
            f"**Examples:**\n"
            f'- "Keep the 32% metric and lead with impact"\n'
            f'- "Make every line edge-to-edge"\n'
            f'- "Strengthen the first bullet"\n'
            f'- "Looks good" (to accept after a fix)'
        )
    return (
        "Tell me what to change in plain English — I'll rewrite that section.\n\n"
        f"**Examples:**\n"
        f'- "Fix all bullets at **{names.split(",")[0].strip()}** — every line edge-to-edge"\n'
        f'- "Strengthen bullet 2 at **{names.split(",")[0].strip()}** — keep the 22% metric"\n'
        f'- "This looks good" (after a fix, to accept)\n\n'
        "Pick a job in the sidebar, or name the company in chat."
    )
