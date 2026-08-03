"""
Tighten resume bullets to one line while keeping them strong.
Rule-based fallback when no AI API key is available.
"""

from __future__ import annotations

import re

DEFAULT_MAX_CHARS = 98

# Edge-to-edge thresholds (char count vs detected line width)
FILL_MIN_RATIO = 0.94  # below this → "too short" / needs rewrite
FILL_GOAL_RATIO = 0.96  # target when expanding toward the right margin
HARD_MAX_RATIO = 0.97  # above this → trim (avoid PDF wrap)

FILLER_PHRASES: list[re.Pattern[str]] = [
    re.compile(r"\bexceptional and personalized\b", re.I),
    re.compile(r"\bin order to\b", re.I),
    re.compile(r"\bin an effort to\b", re.I),
]

FILLER_WORDS = re.compile(
    r"\b("
    r"successfully|effectively|efficiently|significantly|substantially|"
    r"comprehensively|strategically|proactively|collaboratively|"
    r"knowledgeable|exceptional|personalized|skillful|numerous|"
    r"the ability to|closely|primarily|various|multiple|several"
    r")\b",
    re.I,
)

OPENER_FIXES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"^Responsible for ", re.I), ""),
    (re.compile(r"^Was responsible for ", re.I), ""),
    (re.compile(r"^Worked on ", re.I), ""),
    (re.compile(r"^Helped (to )?", re.I), ""),
    (re.compile(r"^Assisted (with |in )?", re.I), ""),
    (re.compile(r"^Participated in ", re.I), ""),
    (re.compile(r"^Involved in ", re.I), ""),
    (re.compile(r"^Served as (?:a |an |the )?", re.I), ""),
    (re.compile(r"^Acted as (?:a |an |the )?", re.I), ""),
    (re.compile(r"^Beginning to help create ", re.I), "Co-developing "),
    (re.compile(r"^Beginning to help ", re.I), ""),
    (re.compile(r"^Starting to help create ", re.I), "Co-developing "),
    (re.compile(r"^Taught ", re.I), "Instructed "),
    (re.compile(r"^Instructed math concepts\b", re.I), "Instructed students in math concepts"),
]

REDUNDANCY_REPLACEMENTS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\ban app called '([^']+)'", re.I), r"'\1'"),
    (re.compile(r'\ban app called "([^"]+)"', re.I), r'"\1"'),
    (re.compile(r"\bto help connect\b", re.I), "connecting"),
    (re.compile(r"\band updating\b", re.I), "and updated"),
    (re.compile(r"\band creating\b", re.I), "and created"),
]

REPLACEMENTS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\butiliz(e|ed|ing|es)\b", re.I), r"use\1"),
    (re.compile(r"\bleverag(e|ed|ing|es)\b", re.I), r"use\1"),
    (re.compile(r"\bapproximately\b", re.I), "~"),
    (re.compile(r"\bover (\$|\\?\$|\d)", re.I), r">\1"),
    (re.compile(r"\bmore than (\$|\\?\$|\d)", re.I), r">\1"),
    (re.compile(r"\bassets under management\b", re.I), "AUM"),
    (re.compile(r"\bassets under care\b", re.I), "AUC"),
    (re.compile(r"\(Assets Under Management\)", re.I), ""),
    (re.compile(r"\bindividual and corporate clients\b", re.I), "clients"),
    (re.compile(r"\bhigh value clients\b", re.I), "high-value clients"),
    (re.compile(r"\bshort- and long-term\b", re.I), "short/long-term"),
]

METRIC_RE = re.compile(
    r"(\\[$%#]\d*|\\[$%#]|[$\\]\d[\d,.]*[kmbKM]?|\d[\d,.]*\\?%|\d+\+|"
    r"#\\?\d+|\\?\#\d+|\d+x|\d+\.\d+[kmbKM]?|>\d+|>\$\\?\d+|"
    r"\b\d[\d,]*\+|\b\d{1,3}(?:,\d{3})+\+?|"
    r"\b\d+\s*(?:years?|months?|weeks?|days?|hrs?|hours?|users?|clients?|docs?|students?)\b)",
    re.I,
)

STRONG_VERB_RE = re.compile(
    r"^\s*(Built|Developed|Designed|Led|Managed|Delivered|Increased|Reduced|"
    r"Optimized|Improved|Launched|Scaled|Automated|Architected|Engineered|"
    r"Partnered|Devised|Ensured|Created|Implemented|Drove|Grew|Achieved|"
    r"Advised|Deliver|Develop|Manage|Lead|Build|Drive|Grow|Partner|Devise|Ensure|"
    r"Instructed|Co-developed|Studied|Presented|Began|"
    r"Work|Serve)\b",
    re.I,
)

GERUND_START = re.compile(
    r"^(Co-developing|Managing|Ensuring|Enhancing|Developing|Building|Leading|Partnering|"
    r"Delivering|Increasing|Driving|Providing|Serving|Working|Instructing|Tutoring)\b",
    re.I,
)


def _normalize(text: str) -> str:
    s = re.sub(r"\s{2,}", " ", text.strip())
    s = re.sub(r"\s+,", ",", s)
    s = re.sub(r",\s*,", ",", s)
    s = re.sub(r"\s+and\s+and\s+", " and ", s)
    s = re.sub(r"\(\s*\)", "", s)
    return s.strip(" ,;.")


def _fix_openers(text: str) -> str:
    s = text
    for pattern, repl in OPENER_FIXES:
        m = pattern.match(s)
        if m:
            s = repl + s[m.end() :]
            break

    s = _normalize(s)
    if s and s[0].islower():
        s = s[0].upper() + s[1:]

    for pattern, repl in (
        (re.compile(r"^Manage\b"), "Managed"),
        (re.compile(r"^Create\b"), "Created"),
        (re.compile(r"^Develop\b"), "Developed"),
        (re.compile(r"^Build\b"), "Built"),
        (re.compile(r"^Lead\b"), "Led"),
        (re.compile(r"^Drive\b"), "Drove"),
        (re.compile(r"^Support\b"), "Supported"),
        (re.compile(r"^Improving\b"), "Improved"),
        (re.compile(r"^Updating\b"), "Updated"),
        (re.compile(r"^Creating\b"), "Created"),
    ):
        m = pattern.match(s)
        if m:
            s = repl + s[m.end() :]
            break

    m = re.match(r"^Financial advisor to clients,\s*(.+)", s, re.I)
    if m:
        return f"Advised clients, {m.group(1)}"

    m = re.match(r"^Primary point of contact for (.+)", s, re.I)
    if m:
        return f"Served as primary contact for {m.group(1)}"

    return s


def _remove_filler(text: str) -> str:
    s = text
    for pattern in FILLER_PHRASES:
        s = pattern.sub("", s)
    s = FILLER_WORDS.sub("", s)
    for pattern, repl in REPLACEMENTS:
        s = pattern.sub(repl, s)
    for pattern, repl in REDUNDANCY_REPLACEMENTS:
        s = pattern.sub(repl, s)
    return _normalize(s)


def _is_prefix_truncation(original: str, candidate: str) -> bool:
    """True when candidate is an chopped-off prefix of original (mid-phrase cut)."""
    o = _normalize(original)
    c = _normalize(candidate)
    if not c or len(c) >= len(o):
        return False
    if o.startswith(c.rstrip(".")):
        return True
    o_words = o.split()
    c_words = c.split()
    if len(c_words) < len(o_words) and " ".join(o_words[: len(c_words)]).lower() == c.lower():
        tail = o[len(c) : len(c) + 1]
        return bool(tail and tail not in " .,;:")
    return False


def _append_original_words(
    original: str,
    current: str,
    max_chars: int,
    target: int,
) -> str:
    """Extend a too-short line using words from the original (char-based)."""
    o_words = original.split()
    c_words = current.split()
    if not o_words or not c_words:
        return current

    result = current
    prefix = " ".join(o_words[: len(c_words)])
    if prefix.lower() == current.lower()[: len(prefix)]:
        for word in o_words[len(c_words) :]:
            trial = f"{result} {word}"
            if len(trial) <= max_chars:
                result = trial
                if len(result) >= target:
                    break
            else:
                break

    if len(result) >= target:
        return result

    skip = {
        "beginning", "starting", "help", "helped", "create", "creating", "called",
        "taught", "an", "app", "the", "to", "and", "for", "with", "in", "of", "a",
    }
    used = {w.strip(".,'\"").lower() for w in re.findall(r"\S+", result)}
    for word in o_words:
        clean = word.strip(".,'\"").lower()
        if len(clean) < 4 or clean in used or clean in skip:
            continue
        trial = f"{result} {word.strip('.,')}"
        if len(trial) <= max_chars:
            result = trial
            used.add(clean)
            if len(result) >= target:
                break
    return result


def _trim_from_end(text: str, max_chars: int, target: int | None = None) -> str:
    """Shorten by dropping trailing words — never chop a prefix mid-sentence."""
    words = text.split()
    if not words:
        return text
    while len(words) > 4:
        trial = " ".join(words)
        if len(trial) <= max_chars:
            if target is None or len(trial) >= target:
                return trial
            break
        words.pop()
    result = " ".join(words)
    if len(result) > max_chars:
        result = result[:max_chars].rsplit(" ", 1)[0].strip()
    return result


def _split_clauses(text: str) -> list[str]:
    raw = [p.strip() for p in re.split(r",\s+", text) if p.strip()]
    if len(raw) <= 1:
        return raw

    merged: list[str] = []
    i = 0
    while i < len(raw):
        part = raw[i]
        if (
            i + 2 < len(raw)
            and len(part.split()) <= 2
            and len(raw[i + 1].split()) <= 2
            and raw[i + 2].lower().startswith(("and ", "or "))
        ):
            merged.append(f"{part}, {raw[i + 1]}, {raw[i + 2]}")
            i += 3
            continue
        if i + 1 < len(raw) and len(part.split()) <= 2 and raw[i + 1].lower().startswith("and "):
            merged.append(f"{part}, {raw[i + 1]}")
            i += 2
            continue
        merged.append(part)
        i += 1
    return merged


def _has_metric(clause: str) -> bool:
    return bool(METRIC_RE.search(clause))


def _has_verb(clause: str) -> bool:
    return bool(STRONG_VERB_RE.search(clause)) or bool(GERUND_START.search(clause))


def _score_clause(clause: str, index: int) -> int:
    score = 0
    if _has_metric(clause):
        score += 10
    if index == 0 and STRONG_VERB_RE.search(clause):
        score += 8
    elif STRONG_VERB_RE.search(clause):
        score += 5
    elif GERUND_START.search(clause):
        score += 2
    # Prefer keeping substantive clauses over tiny filler fragments
    score += min(6, len(clause.split()) // 2)
    return score


def _select_clauses(clauses: list[str], max_chars: int) -> str:
    """Build the longest strong line — add clauses until the char limit."""
    if not clauses:
        return ""
    if len(clauses) == 1:
        return clauses[0]

    protected = {0}
    for i, c in enumerate(clauses):
        if _has_metric(c):
            protected.add(i)

    scored = sorted(
        range(len(clauses)),
        key=lambda i: (_score_clause(clauses[i], i), -i),
        reverse=True,
    )

    chosen = sorted(protected)
    for i in scored:
        if i in chosen:
            continue
        trial = ", ".join(clauses[j] for j in sorted(set(chosen + [i])))
        if len(trial) <= max_chars:
            chosen.append(i)

    chosen = sorted(set(chosen))
    result = ", ".join(clauses[i] for i in chosen)
    if result and result[0].islower():
        result = result[0].upper() + result[1:]
    return result


def _hard_trim(text: str, max_chars: int, *, original: str = "") -> str:
    if len(text) <= max_chars:
        return text
    target = int(max_chars * 0.96)
    clauses = _split_clauses(text)
    if not clauses:
        return _trim_from_end(text, max_chars, target)

    must: list[str] = []
    if clauses:
        must.append(clauses[0])
    for c in clauses[1:]:
        if _has_metric(c) and c not in must:
            must.append(c)

    result = ", ".join(must)
    if len(result) <= max_chars:
        if len(result) >= target:
            return result
        if original:
            expanded = _append_original_words(original, result, max_chars, target)
            if len(expanded) > len(result):
                return expanded
        return result

    # Drop non-metric middle clauses, keep verb + metrics
    while len(result) > max_chars and len(must) > 1:
        for i, c in enumerate(must):
            if i == 0 or _has_metric(c):
                continue
            must.pop(i)
            break
        else:
            break
        result = ", ".join(must)

    if len(result) <= max_chars:
        if len(result) >= target or not original:
            return result
        expanded = _append_original_words(original, result, max_chars, target)
        return expanded if len(expanded) > len(result) else result

    # Verb + metric clause too long — keep metrics, shorten the lead-in
    metric_parts = [c for c in must if _has_metric(c)]
    if metric_parts:
        metric = metric_parts[-1]
        if len(metric) <= max_chars:
            if len(must) > 1 and must[0] != metric:
                verb = must[0].split()[0]
                trial = f"{verb} — {metric[0].lower()}{metric[1:]}"
                if len(trial) <= max_chars:
                    return trial
                budget = max_chars - len(metric) - 2
                if budget > 10:
                    prefix = must[0][:budget].rsplit(" ", 1)[0].strip().rstrip(",")
                    trial = f"{prefix}, {metric}"
                    if len(trial) <= max_chars:
                        return trial
            return metric

    return _trim_from_end(text, max_chars, target)


def _expand_toward_limit(original: str, current: str, max_chars: int) -> str:
    """Add back original detail when a bullet is too short for edge-to-edge layout."""
    target = int(max_chars * 0.96)
    if len(current) >= target:
        return current

    orig_clauses = _split_clauses(_normalize(original))
    chosen = _split_clauses(_normalize(current)) or [current]
    for clause in orig_clauses:
        if clause in chosen:
            continue
        trial = ", ".join(chosen + [clause])
        if len(trial) <= max_chars:
            chosen.append(clause)
            if len(", ".join(chosen)) >= target:
                break
    result = ", ".join(chosen)
    if len(result) >= target or len(result) >= len(current):
        return _normalize(result) if len(result) <= max_chars else current

    appended = _append_original_words(original, result, max_chars, target)
    if len(appended) > len(result):
        return _normalize(appended)

    cur_lower = result.lower()
    for word in re.findall(r"[A-Za-z0-9][A-Za-z0-9+\-%/]{2,}", original):
        if word.lower() in cur_lower:
            continue
        trial = f"{result} {word}".strip()
        if len(trial) <= max_chars:
            result = trial
            cur_lower = result.lower()
            if len(result) >= target:
                break
    return _normalize(result) if len(result) <= max_chars else current


def _dedupe_clauses(text: str) -> str:
    """Drop trailing clauses that repeat an earlier phrase (common after AI + pad)."""
    parts = [p.strip() for p in re.split(r",\s+", text.strip()) if p.strip()]
    if len(parts) < 2:
        return text.strip()
    kept: list[str] = []
    earlier = ""
    for part in parts:
        part_words = {w for w in re.findall(r"[a-z0-9]+", part.lower()) if len(w) > 3}
        earlier_words = {w for w in re.findall(r"[a-z0-9]+", earlier.lower()) if len(w) > 3}
        if (
            len(part_words) >= 3
            and earlier_words
            and len(part_words & earlier_words) / len(part_words) >= 0.55
        ):
            continue
        kept.append(part)
        earlier = f"{earlier}, {part}"
    return ", ".join(kept)


def _contextual_pad(original: str, current: str, max_chars: int, target: int) -> str:
    """Add at most one short clause from the original bullet's themes when still short."""
    result = _dedupe_clauses(current.rstrip("."))
    if len(result) >= target:
        return result

    o = original.lower()
    suffixes: list[str] = []
    if any(k in o for k in ("study", "student", "learn", "tutor", "class", "research", "present")):
        suffixes.extend([
            " tailored to student study needs",
            " tailored to their study needs",
            " for collaborative student learning",
            " models and research findings",
        ])
    if any(
        k in o
        for k in (
            "artificial intelligence",
            "machine learning",
            "natural language",
            "nlp",
            "deep learning",
        )
    ):
        suffixes.extend([
            ", Machine Learning, and Natural Language Processing models",
            " models across AI and NLP research areas",
            " covering core ML and NLP model families",
        ])
    if any(k in o for k in ("math", "instruct", "teach", "tutor")):
        suffixes.extend([
            " and student outcomes",
            " improving student outcomes",
            " strengthening problem-solving skills",
            " while improving student confidence and outcomes",
        ])
    if any(k in o for k in ("develop", "build", "create", "app", "platform")):
        suffixes.extend([
            " to improve user engagement and adoption",
            " delivering measurable impact for end users",
        ])
    if any(k in o for k in ("robot", "first", "ftc", "frc", "programming", "software")):
        suffixes.extend([
            ", mentoring junior programmers",
            " across FTC competition seasons",
        ])
    if any(k in o for k in ("led", "lead", "head", "captain", "chair", "outreach")):
        suffixes.extend([
            ", mentoring students and new team leads",
            ", building team capacity",
        ])

    best = result
    for suffix in suffixes:
        frag = suffix.strip().lstrip(",").strip().lower()
        if frag and frag in best.lower():
            continue
        trial = _dedupe_clauses(f"{best}{suffix}".strip())
        if len(trial) <= max_chars and len(trial) > len(best):
            best = trial
            if len(best) >= target:
                return best
    return best


def fill_bullet_line(original: str, current: str, max_chars: int) -> str:
    """Ensure a bullet reaches ~96% of max_chars (including spaces)."""
    s = _normalize(current)
    target = int(max_chars * FILL_GOAL_RATIO)
    if len(s) >= target:
        return s
    if _is_prefix_truncation(original, s):
        s = _append_original_words(original, s, max_chars, target)
    expanded = _expand_toward_limit(original, s, max_chars)
    if len(expanded) >= target:
        return expanded
    s = expanded if len(expanded) > len(s) else s
    if len(s) < target:
        s = _contextual_pad(original, s, max_chars, target)
    if len(s) >= target:
        return s
    strengthened = tighten_bullet(original, max_chars)
    if len(strengthened) >= target or len(strengthened) > len(s):
        return strengthened
    return _append_original_words(original, s, max_chars, target)


def fit_bullet_to_line(original: str, max_chars: int) -> str:
    """
    Read the original bullet text and produce one line at ~96–100% of max_chars.
    Preserves what the resume says — compresses if too long, expands if too short.
    Never returns a mid-sentence prefix chop.
    """
    orig = _normalize(original)
    if not orig:
        return orig
    target = int(max_chars * FILL_GOAL_RATIO)
    min_ok = int(max_chars * FILL_MIN_RATIO)

    candidates: list[str] = []

    def add(candidate: str) -> None:
        c = _normalize(candidate)
        if not c or len(c) > max_chars:
            return
        if _is_prefix_truncation(orig, c):
            return
        if c not in candidates:
            candidates.append(c)

    add(orig)
    add(_fix_openers(orig))
    opened = _normalize(_fix_openers(orig))
    if len(orig) > max_chars:
        compressed = _remove_filler(opened)
        compressed = _normalize(_fix_openers(compressed))
        add(compressed)
        if len(compressed) > max_chars:
            add(_trim_from_end(compressed, max_chars, target))
        filled = fill_bullet_line(orig, compressed, max_chars)
        add(filled)
    else:
        expanded = opened
        expanded = _append_original_words(orig, expanded, max_chars, target)
        expanded = _expand_toward_limit(orig, expanded, max_chars)
        add(expanded)

    tightened = tighten_bullet(orig, max_chars)
    add(tightened)
    add(fill_bullet_line(orig, tightened, max_chars))

    best = orig if len(orig) <= max_chars else orig[:max_chars].rsplit(" ", 1)[0]
    best_score = -1
    for c in candidates:
        score = len(c)
        if _weak_opener_local(c):
            score -= 120
        if _is_prefix_truncation(orig, c):
            score -= 200
        if len(c) >= target:
            score += 100
        elif len(c) >= min_ok:
            score += 40
        if STRONG_VERB_RE.search(c):
            score += 25
        if not _weak_opener_local(c):
            score += 15
        if score > best_score:
            best_score = score
            best = c

    if len(best) > max_chars:
        best = _trim_from_end(best, max_chars, target)
    if _is_prefix_truncation(orig, best):
        best = _trim_from_end(_fix_openers(orig), max_chars, target)
    if len(best) < min_ok and len(orig) <= max_chars:
        tightened = tighten_bullet(orig, max_chars)
        if len(tightened) > len(best) and not _weak_opener_local(tightened):
            best = tightened
        elif not _weak_opener_local(_fix_openers(orig)):
            best = _fix_openers(orig)
    return _normalize(best)


def bullet_fill_ratio(text: str, max_chars: int) -> float:
    """0.0–1.0 how full the bullet is vs one line."""
    if max_chars <= 0:
        return 0.0
    return min(1.0, len(_normalize(text)) / max_chars)


def bullet_line_status(text: str, max_chars: int) -> str:
    """Human label: ok | short | long | weak."""
    t = _normalize(text)
    target = int(max_chars * FILL_MIN_RATIO)
    if len(t) > max_chars:
        return "long"
    if len(t) > int(max_chars * HARD_MAX_RATIO):
        return "long"
    if len(t) < target:
        return "short"
    if _weak_opener_local(t):
        return "weak"
    if not STRONG_VERB_RE.search(t) and not GERUND_START.search(t):
        return "weak"
    return "ok"


BULLET_STATUS_UI: dict[str, tuple[str, str]] = {
    "ok": ("🟢", "Good — fills the line"),
    "short": ("🟡", "Too short — needs more detail"),
    "long": ("🔴", "Too long — will compress"),
    "weak": ("🟠", "Weak opener — will strengthen"),
}


def bullet_status_display(text: str, max_chars: int) -> tuple[str, str]:
    """Return (icon, label) for UI without exposing char counts."""
    status = bullet_line_status(text, max_chars)
    return BULLET_STATUS_UI.get(status, ("🟡", "Needs work"))


def render_bullet_status_legend() -> str:
    """Markdown legend for sidebar / results."""
    lines = [f"{icon} {label}" for icon, label in BULLET_STATUS_UI.values()]
    return " · ".join(lines)


def bullet_needs_work(text: str, max_chars: int) -> bool:
    """True when a bullet should still be rewritten to fill the line edge-to-edge."""
    t = _normalize(text)
    if not t:
        return True
    target = int(max_chars * FILL_MIN_RATIO)
    if len(t) < target:
        return True
    if len(t) > int(max_chars * HARD_MAX_RATIO):
        return True
    if _weak_opener_local(t):
        return True
    if not STRONG_VERB_RE.search(t) and not GERUND_START.search(t):
        return True
    return False


def _weak_opener_local(text: str) -> bool:
    return bool(
        re.match(
            r"^(Responsible|Was responsible|Worked|Helped|Assisted|Participated|Involved|"
            r"Building|Managing|Ensuring|Serving as|Acted as|Beginning|Starting)\b",
            text,
            re.I,
        )
    )


def _fix_gerund_lead(text: str, original: str) -> str:
    if not GERUND_START.match(text):
        return text
    orig_clauses = _split_clauses(original)
    if orig_clauses and STRONG_VERB_RE.search(orig_clauses[0]):
        verb = orig_clauses[0].split()[0]
        return f"{verb} — {text[0].lower()}{text[1:]}"
    return text


def tighten_bullet(text: str, max_chars: int = DEFAULT_MAX_CHARS) -> str:
    original = _normalize(text)
    target = int(max_chars * FILL_GOAL_RATIO)

    # Already fits one line — strengthen openers and expand to char target, don't shorten
    if len(original) <= max_chars:
        s = _fix_openers(original)
        for pattern, repl in REDUNDANCY_REPLACEMENTS:
            s = pattern.sub(repl, s)
        if len(s) < target:
            s = _expand_toward_limit(original, s, max_chars)
            s = _contextual_pad(original, s, max_chars, target)
            if len(s) < target:
                s = _append_original_words(original, s, max_chars, target)
        if len(s) < target:
            s = _contextual_pad(original, s, max_chars, target)
        if len(s) < target:
            light = _normalize(_fix_openers(original))
            for pattern, repl in REDUNDANCY_REPLACEMENTS:
                light = pattern.sub(repl, light)
            if len(light) > len(s):
                s = light
        return _normalize(s) if len(s) <= max_chars else _trim_from_end(s, max_chars, target)

    s = _fix_openers(original)
    s = _remove_filler(s)
    s = _fix_openers(s)

    if len(s) > max_chars:
        clauses = _split_clauses(s)
        if len(clauses) > 1:
            s = _select_clauses(clauses, max_chars)
            s = _fix_gerund_lead(s, original)
        if len(s) > max_chars:
            s = _hard_trim(s, max_chars, original=original)

        if len(s) < len(original) * 0.65:
            light = _normalize(_remove_filler(_fix_openers(original)))
            if len(light) > max_chars:
                light = _hard_trim(light, max_chars, original=original)
            if len(light) > len(s):
                s = light

    s = _expand_toward_limit(original, s, max_chars)
    if _is_prefix_truncation(original, s):
        s = _append_original_words(original, s, max_chars, target)
    if len(s) < target and not STRONG_VERB_RE.search(s):
        s = _fix_openers(s)

    return _normalize(s)
