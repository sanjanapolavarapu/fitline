#!/usr/bin/env python3
"""
Preprocess LaTeX resume files so bullet points fit on one line and stay strong.

Usage:
  python fit_resume.py resume.tex -o resume_fit.tex
  python fit_resume.py resume.tex --no-strong          # wrap only, no rewriting
  python fit_resume.py resume.tex --watch
"""

from __future__ import annotations

import argparse
import re
import sys
import time
from pathlib import Path

from ai_rewriter import rewrite_section_bullets, _clean_bullet, _finalize_bullet, _enforce_edge_to_edge, _looks_truncated
from bullet_strong import bullet_needs_work, fit_bullet_to_line, _is_prefix_truncation, tighten_bullet, fill_bullet_line
from pdf_to_latex import flatten_resume_bullets
from sections import (
    ExperienceBlock,
    find_best_block,
    find_experience,
    format_not_found_error,
    list_itemize_blocks,
    parse_experiences,
    resolve_selection,
)

DEFAULT_MAX_CHARS = 92

RESUME_ITEM_LINE_RE = re.compile(r"^(\s*)\\resumeItem\{(.*)\}\s*$")
ITEM_LINE_RE = re.compile(r"^(\s*)\\item\s+(.*)$")
ROLE_RE = re.compile(
    r"^(\s*)\\role\{([^}]*)\}\{([^}]*)\}\{([^}]*)\}\{([^}]*)\}\s*$",
    re.MULTILINE,
)


def _escape_latex_arg(text: str) -> str:
    """Escape unescaped special characters for LaTeX macro arguments."""
    out: list[str] = []
    i = 0
    special = set("#$%&_{}")
    while i < len(text):
        ch = text[i]
        if ch == "\\" and i + 1 < len(text):
            out.append(ch)
            out.append(text[i + 1])
            i += 2
            continue
        if ch in special:
            out.append("\\" + ch)
        else:
            out.append(ch)
        i += 1
    return "".join(out)


def _parse_bullet_line(line: str) -> tuple[str, str, str] | None:
    """Return (indent, body, kind) for item / resumeItem lines."""
    stripped = line.rstrip("\n\r")
    m = RESUME_ITEM_LINE_RE.match(stripped)
    if m:
        return m.group(1), _unwrap_item_body(m.group(2)), "resumeItem"
    m = ITEM_LINE_RE.match(stripped)
    if m:
        return m.group(1), _unwrap_item_body(m.group(2)), "item"
    return None


def _unwrap_item_body(body: str) -> str:
    body = body.strip()
    if body.endswith("}") and body.count("{") == body.count("}"):
        # \resumeItem{content} — strip trailing brace from line match
        inner = body
        if inner.endswith("}"):
            inner = inner[:-1]
        body = inner
    for prefix in (r"\resumeitem{", r"\fitline{"):
        if body.startswith(prefix) and body.endswith("}"):
            return body[len(prefix) : -1]
    return body


def _extract_bullets(section: str) -> list[tuple[str, str, str]]:
    """Return (full_line, indent, body) for each \\item / \\resumeItem in section."""
    section = flatten_resume_bullets(section)
    bullets: list[tuple[str, str, str]] = []
    seen_spans: set[tuple[int, int]] = set()

    marker = r"\resumeItem{"
    i = 0
    while i < len(section):
        pos = section.find(marker, i)
        if pos == -1:
            break
        line_start = section.rfind("\n", 0, pos) + 1
        line_end = section.find("\n", pos)
        if line_end == -1:
            line_end = len(section)
        indent = section[line_start:pos]
        j = pos + len(marker)
        depth = 1
        body_start = j
        while j < len(section) and depth:
            ch = section[j]
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
            j += 1
        body = section[body_start : j - 1]
        span = (line_start, j)
        if span not in seen_spans:
            seen_spans.add(span)
            full_line = section[line_start:j]
            if full_line.endswith("\n"):
                full_line = full_line[:-1]
            bullets.append((full_line, indent, body))
        i = j

    for line in section.splitlines(keepends=True):
        stripped = line.rstrip("\n\r")
        parsed = _parse_bullet_line(stripped)
        if not parsed:
            continue
        indent, body, kind = parsed
        if kind == "resumeItem":
            continue
        if body.startswith(r"\fitline") or body.startswith(r"\resumeitem"):
            continue
        bullets.append((stripped, indent, body))

    bullets.sort(key=lambda b: section.find(b[0][: min(40, len(b[0]))]))
    return bullets


def list_section_bullet_texts(section: str) -> list[str]:
    """Plain-text preview of each bullet in a section (for UI pickers)."""
    return [_clean_bullet(body) for _line, _indent, body in _extract_bullets(section)]


def _rewrite_bullet_body(original: str, max_chars: int) -> str:
    """Rule-based pass: read original text and fit to one full line by char count."""
    from bullet_strong import _contextual_pad, _append_original_words, _expand_toward_limit

    cleaned = _clean_bullet(original)
    target = int(max_chars * 0.96)
    body = tighten_bullet(cleaned, max_chars)
    if len(body) < target:
        body = fill_bullet_line(cleaned, body, max_chars)
        body = _expand_toward_limit(cleaned, body, max_chars)
        body = _append_original_words(cleaned, body, max_chars, target)
        if len(body) < target:
            body = _contextual_pad(cleaned, body, max_chars, target)
    body = _finalize_bullet(cleaned, body, max_chars)
    if bullet_needs_work(body, max_chars) or _is_prefix_truncation(cleaned, body):
        body = fit_bullet_to_line(cleaned, max_chars)
        body = _finalize_bullet(cleaned, body, max_chars)
    return body


def _apply_bullets_to_section(
    section: str,
    new_bodies: list[str],
    *,
    originals: list[str] | None = None,
    bullet_indices: set[int] | None = None,
) -> tuple[str, list[tuple[str, str]]]:
    """Replace bullet bodies by index; return updated section and change list."""
    section = flatten_resume_bullets(section)
    changes: list[tuple[str, str]] = []
    out: list[str] = []
    last = 0
    bullet_idx = 0

    marker = r"\resumeItem{"
    i = 0
    spans: list[tuple[int, int, str, str]] = []
    while i < len(section):
        pos = section.find(marker, i)
        if pos == -1:
            break
        line_start = section.rfind("\n", 0, pos) + 1
        indent = section[line_start:pos]
        j = pos + len(marker)
        depth = 1
        body_start = j
        while j < len(section) and depth:
            ch = section[j]
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
            j += 1
        body = section[body_start : j - 1]
        spans.append((line_start, j, indent, body))
        i = j

    if spans:
        for start, end, indent, body in spans:
            out.append(section[last:start])
            orig_clean = _clean_bullet(body)
            should_fix = bullet_indices is None or bullet_idx in bullet_indices
            if should_fix and bullet_idx < len(new_bodies):
                new_body = new_bodies[bullet_idx]
            else:
                new_body = body
            if should_fix and (
                _clean_bullet(new_body) != orig_clean or new_body.strip() != body.strip()
            ):
                before = originals[bullet_idx] if originals and bullet_idx < len(originals) else body
                changes.append((_clean_bullet(before), new_body))
            out.append(f"{indent}\\resumeItem{{{_escape_latex_arg(new_body)}}}")
            bullet_idx += 1
            last = end
        out.append(section[last:])
        return "".join(out), changes

    lines: list[str] = []
    for line in section.splitlines(keepends=True):
        stripped = line.rstrip("\n")
        parsed = _parse_bullet_line(stripped)
        if not parsed:
            lines.append(line)
            continue
        indent, body, kind = parsed
        if body.startswith(r"\fitline") or body.startswith(r"\resumeitem"):
            lines.append(line)
            continue
        should_fix = bullet_indices is None or bullet_idx in bullet_indices
        if should_fix and bullet_idx < len(new_bodies):
            new_body = new_bodies[bullet_idx]
        else:
            new_body = body
        orig_clean = _clean_bullet(body)
        if should_fix and (
            _clean_bullet(new_body) != orig_clean or new_body.strip() != body.strip()
        ):
            before = originals[bullet_idx] if originals and bullet_idx < len(originals) else body
            changes.append((_clean_bullet(before), new_body))
        bullet_idx += 1
        if kind == "resumeItem":
            lines.append(
                f"{indent}\\resumeItem{{{_escape_latex_arg(new_body)}}}"
                + ("\n" if line.endswith("\n") else "")
            )
        else:
            lines.append(f"{indent}\\item {new_body}" + ("\n" if line.endswith("\n") else ""))
    return "".join(lines), changes


def transform_items_rules(
    tex: str,
    strong: bool,
    max_chars: int,
    bullet_indices: set[int] | None = None,
) -> tuple[str, int, list[tuple[str, str]]]:
    tex = flatten_resume_bullets(tex)
    bullets = _extract_bullets(tex)
    if not bullets:
        return tex, 0, []

    originals = [b[2] for b in bullets]
    cleaned = [_clean_bullet(b) for b in originals]
    new_bodies: list[str] = []

    for i, raw in enumerate(originals):
        if strong and (bullet_indices is None or i in bullet_indices):
            new_bodies.append(_rewrite_bullet_body(raw, max_chars))
        else:
            new_bodies.append(raw)

    updated, changes = _apply_bullets_to_section(
        tex,
        new_bodies,
        originals=originals,
        bullet_indices=bullet_indices,
    )
    return updated, len(bullets), changes


def transform_items_ai(
    section: str,
    block: ExperienceBlock,
    strong: bool,
    max_chars: int,
    api_key: str | None,
    provider: str = "gemini",
    feedback: str = "",
    bullet_indices: set[int] | None = None,
) -> tuple[str, int, list[tuple[str, str]], str | None]:
    section = flatten_resume_bullets(section)
    bullets = _extract_bullets(section)
    if not bullets:
        return section, 0, [], None

    originals = [b[2] for b in bullets]
    bodies = [_clean_bullet(b) for b in originals]
    count = len(bodies)

    if not strong:
        updated, changes = _apply_bullets_to_section(
            section, bodies, originals=originals, bullet_indices=bullet_indices
        )
        return updated, count, changes, None

    rewritten, ai_error = rewrite_section_bullets(
        bodies,
        company=block.company,
        title=block.title,
        dates=block.dates,
        max_chars=max_chars,
        api_key=api_key,
        provider=provider,  # type: ignore[arg-type]
        feedback=feedback,
        indices_to_rewrite=bullet_indices,
    )

    final_bodies: list[str] = []
    for i, (orig_raw, orig_clean, ai_line) in enumerate(zip(originals, bodies, rewritten)):
        if bullet_indices is not None and i not in bullet_indices:
            final_bodies.append(orig_raw)
            continue
        line = _enforce_edge_to_edge(orig_clean, ai_line, max_chars)
        if (
            bullet_needs_work(line, max_chars)
            or _looks_truncated(orig_clean, line)
            or _is_prefix_truncation(orig_clean, line)
        ):
            line = fit_bullet_to_line(orig_clean, max_chars)
            line = _enforce_edge_to_edge(orig_clean, line, max_chars)
        if bullet_needs_work(line, max_chars):
            line = _rewrite_bullet_body(orig_raw, max_chars)
        if _clean_bullet(line) == orig_clean and bullet_needs_work(orig_clean, max_chars):
            forced = fit_bullet_to_line(orig_clean, max_chars)
            if len(_clean_bullet(forced)) > len(orig_clean):
                line = _enforce_edge_to_edge(orig_clean, forced, max_chars)
            else:
                line = _rewrite_bullet_body(orig_raw, max_chars)
        final_bodies.append(_enforce_edge_to_edge(orig_clean, line, max_chars))

    updated, changes = _apply_bullets_to_section(
        section,
        final_bodies,
        originals=originals,
        bullet_indices=bullet_indices,
    )
    return updated, count, changes, ai_error


def transform_roles(tex: str, strong: bool, max_chars: int) -> tuple[str, int]:
    count = 0
    field_max = max(28, max_chars // 3)

    def repl_role(m: re.Match[str]) -> str:
        nonlocal count
        indent = m.group(1)
        fields = [m.group(i).strip() for i in range(2, 6)]
        if strong:
            fields = [tighten_bullet(f, field_max) for f in fields]
        count += 1
        a, b, c, d = fields
        return f"{indent}\\role{{{a}}}{{{b}}}{{{c}}}{{{d}}}"

    return ROLE_RE.sub(repl_role, tex), count


def process(
    tex: str,
    strong: bool = True,
    max_chars: int = DEFAULT_MAX_CHARS,
    company: str | None = None,
    api_key: str | None = None,
    use_ai: bool = True,
    provider: str = "gemini",
    feedback: str = "",
    bullet_indices: set[int] | None = None,
) -> tuple[str, dict]:
    """
    Process resume tex. If `company` is set, only fix that experience block.
    When `use_ai` and an API key is available, rewrites bullets with job context.
    """
    tex = flatten_resume_bullets(tex)
    experiences = parse_experiences(tex)
    if not experiences:
        experiences = list_itemize_blocks(tex)

    block = resolve_selection(tex, company) if company else None
    if not block and company:
        block = find_experience(tex, company)
    fallback_note: str | None = None
    if company and not block:
        block, fallback_note = find_best_block(tex, company)

    if company and not block:
        return tex, {
            "items": 0,
            "roles": 0,
            "rewritten": 0,
            "changes": [],
            "error": format_not_found_error(tex, company),
            "experiences": experiences,
            "mode": "none",
        }

    if block:
        label = block.label
        section = tex[block.start : block.end]
        ai_error: str | None = None
        from ai_rewriter import resolve_api_key

        has_key = bool(resolve_api_key(provider, api_key))  # type: ignore[arg-type]
        if use_ai and strong and has_key:
            section, items, changes, ai_error = transform_items_ai(
                section,
                block,
                strong,
                max_chars,
                api_key,
                provider,
                feedback,
                bullet_indices=bullet_indices,
            )
            mode = "ai" if not ai_error else "rules"
            if ai_error and "No " not in ai_error:
                section, items, changes = transform_items_rules(
                    tex[block.start : block.end],
                    strong,
                    max_chars,
                    bullet_indices=bullet_indices,
                )
                mode = "rules"
            elif not changes:
                section, items, changes = transform_items_rules(
                    section,
                    strong,
                    max_chars,
                    bullet_indices=bullet_indices,
                )
                if changes:
                    mode = "rules"
                    ai_error = ai_error or "AI returned no changes — applied rule-based line fill."
        else:
            section, items, changes = transform_items_rules(
                section, strong, max_chars, bullet_indices=bullet_indices
            )
            mode = "rules"
            if use_ai and strong and not has_key:
                ai_error = (
                    "Get a free Gemini key at aistudio.google.com/apikey "
                    "(no credit card) for smart rewrites."
                )

        section, roles = transform_roles(section, strong, max_chars)
        block = resolve_selection(tex, label) or block
        tex = tex[: block.start] + section + tex[block.end :]
        stats: dict = {
            "items": items,
            "roles": roles,
            "rewritten": len(changes),
            "changes": changes,
            "section": block.label,
            "experiences": experiences,
            "mode": mode,
        }
        if ai_error:
            stats["ai_note"] = ai_error
        if fallback_note:
            stats["fallback_note"] = fallback_note
        return tex, stats

    tex, items, changes = transform_items_rules(tex, strong, max_chars)
    tex, roles = transform_roles(tex, strong, max_chars)
    stats = {
        "items": items,
        "roles": roles,
        "rewritten": len(changes),
        "changes": changes,
        "section": "All sections",
        "experiences": experiences,
        "mode": "rules",
    }
    if use_ai and strong:
        from ai_rewriter import resolve_api_key

        if not resolve_api_key(provider, api_key):  # type: ignore[arg-type]
            stats["ai_note"] = (
                "Select one experience and add a free Gemini key for AI rewrites."
            )
    return tex, stats


def watch(path: Path, out: Path | None, strong: bool, max_chars: int) -> None:
    print(f"Watching {path} — save to re-fit (Ctrl+C to stop)", file=sys.stderr)
    last = None
    while True:
        try:
            mtime = path.stat().st_mtime
            if last != mtime:
                last = mtime
                tex = path.read_text(encoding="utf-8")
                result, stats = process(tex, strong=strong, max_chars=max_chars)
                dest = out or path
                dest.write_text(result, encoding="utf-8")
                print(
                    f"[{time.strftime('%H:%M:%S')}] {dest}: "
                    f"{stats['items']} bullets, {stats['rewritten']} tightened",
                    file=sys.stderr,
                )
            time.sleep(0.5)
        except KeyboardInterrupt:
            print("\nStopped.", file=sys.stderr)
            break


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fit LaTeX resume bullets to one line while keeping them strong"
    )
    parser.add_argument("input", type=Path, help=".tex resume file")
    parser.add_argument("-o", "--output", type=Path, help="Output file (default: stdout)")
    parser.add_argument(
        "--no-strong",
        action="store_true",
        help="Only wrap macros; do not rewrite bullets for strength/length",
    )
    parser.add_argument(
        "--max-chars",
        type=int,
        default=DEFAULT_MAX_CHARS,
        help=f"Target chars per bullet line (default {DEFAULT_MAX_CHARS})",
    )
    parser.add_argument(
        "--watch",
        action="store_true",
        help="Re-process whenever the input file is saved",
    )
    parser.add_argument(
        "--show-changes",
        action="store_true",
        help="Print before/after for rewritten bullets",
    )
    args = parser.parse_args()

    if not args.input.exists():
        sys.exit(f"File not found: {args.input}")

    strong = not args.no_strong

    if args.watch:
        watch(args.input, args.output, strong, args.max_chars)
        return

    tex = args.input.read_text(encoding="utf-8")
    result, stats = process(tex, strong=strong, max_chars=args.max_chars)

    if args.show_changes and stats["changes"]:
        print("Tightened bullets:", file=sys.stderr)
        for before, after in stats["changes"]:
            print(f"\n  BEFORE ({len(before)}): {before}", file=sys.stderr)
            print(f"  AFTER  ({len(after)}): {after}", file=sys.stderr)

    if args.output:
        args.output.write_text(result, encoding="utf-8")
        print(
            f"Wrote {args.output} ({stats['items']} bullets, "
            f"{stats['rewritten']} tightened to stay strong)",
            file=sys.stderr,
        )
    else:
        sys.stdout.write(result)


if __name__ == "__main__":
    main()
