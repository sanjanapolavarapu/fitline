"""
Context-aware resume bullet rewriting via AI (Gemini free tier or OpenAI).

Rewrites bullets using job context (company, title, sibling bullets) so each
line stays strong, factual, and within the character limit.
"""

from __future__ import annotations

import json
import os
import re
import time
from typing import Any, Literal

import requests

Provider = Literal["gemini", "openai"]

OPENAI_URL = "https://api.openai.com/v1/chat/completions"
OPENAI_MODEL = "gpt-4o-mini"
GEMINI_MODELS = [
    "gemini-2.5-flash-preview",
    "gemini-2.5-flash",
    "gemini-flash-latest",
    "gemini-1.5-flash",
    "gemini-1.5-flash-8b",
    "gemini-3-flash-preview",
    "gemini-3.5-flash",
    "gemini-2.0-flash",
]

SYSTEM_PROMPT = """You are an expert resume writer preparing bullets for job applications (tech, finance, consulting).

Your job: READ each bullet carefully, then REWRITE it so it is recruiter-ready, ATS-scannable, AND fills ONE LaTeX line edge-to-edge (right margin to right margin).

READ FIRST — before rewriting:
- Read the entire bullet text. Every accomplishment, tool, metric, and noun phrase must survive the rewrite.
- Count characters (including spaces). The rewrite MUST land at 96–100% of MAX_CHARS — not 70%, not 85%.
- If the original is long, compress smartly. If the original is short, expand using details already in that same bullet.

WHAT "STRONG" MEANS (job-submission / ATS quality):
- Lead with a past-tense impact verb (Built, Led, Drove, Architected, Delivered, Scaled).
- Never start with weak openers: Responsible for, Worked on, Helped with, Participated in, Building, Managing.
- Show scope + method + result in one line (what you did, how, and the outcome).
- Keep industry keywords (cloud platforms, tools, domains) — ATS parsers and recruiters scan for these.
- Quantify impact whenever the original has numbers (%, $, users, volume, uptime).
- NEVER drop a number, rank (#3), count (300+), dollar amount, percentage, or date range.
- When space is tight, keep metrics first — cut filler words, not digits.
- Sound confident and specific — not generic or passive.

LINE WIDTH (critical — highest priority):
- Filling the line edge-to-edge is MORE important than keeping the original wording short.
- Each bullet MUST use 96–100% of MAX_CHARS — visually reach the end of the line like a top ATS resume.
- Too-short bullets (under 92% of MAX_CHARS) are rejected — add keywords, stack, or outcome detail.
- If under limit after cutting filler, expand with relevant tools/platforms/outcomes from the original.
- Never return a bullet unchanged if it still has room left on the line.

CRITICAL — NEVER DO THIS:
- Do NOT cut a sentence mid-phrase to fit the limit (e.g. stopping at "artificial intelligence" and dropping the rest).
- Do NOT return a prefix of the original text.
- Do NOT drop metrics, platforms, or accomplishments to save space — rephrase shorter instead.

INSTEAD — REWRITE intelligently:
- Use tighter verbs (Building → Built, Working on → Built, Ensuring → Drove).
- Abbreviate safely (artificial intelligence → AI, documents → docs).
- Remove filler only (successfully, effectively, in order to).
- Pack the line to ~96–100% of MAX_CHARS — bullets should reach the right edge, not stop early.
- Prefer commas or "and" to connect ideas. Use a semicolon only when it clearly separates two related independent clauses — never as a shortcut to cram unrelated phrases together.
- Do NOT end bullets with a period — resume bullets are line-filling phrases, not full sentences.

Example (MAX_CHARS=98):
Before: Working on improving checkout flow and helping the team reduce cart abandonment through A/B testing and user research across web and mobile
After: Improved checkout flow via A/B tests and cut cart abandonment 22% across web and mobile user flows

If the user gives revision feedback, follow it exactly while keeping bullets strong and within MAX_CHARS.

Rules:
1. Hard limit: at most MAX_CHARS characters per bullet. Count every character.
2. Strong past-tense action verb at the start.
3. Keep every number, metric, stack item (cloud platforms, tools), and outcome unless user asks to remove one.
4. Preserve LaTeX escapes: \\$, \\%, \\#
5. Do NOT invent facts. Do NOT drop accomplishments — rephrase them shorter.
6. Return ONLY valid JSON: {"bullets": ["...", "..."]} with the same count as input."""

FEEDBACK_LINE_RULE = """
USER REVISION — LINE LENGTH IS NON-NEGOTIABLE:
Apply what the user asked (add metrics, strengthen verbs, include numbers, etc.) BUT each bullet must STILL fill exactly ONE line edge-to-edge (96–100% of MAX_CHARS).
If you add detail or numbers, compress or cut filler words elsewhere — same line length. Never shorter than 92% of MAX_CHARS. Never exceed MAX_CHARS.
"""

METRIC_RE = re.compile(
    r"(\\[$%#]\d*|\\[$%#]|[$\\]\d[\d,.]*[kmbKM]?|\d[\d,.]*\\?%|\d+\+|"
    r"#\\?\d+|\\?\#\d+|\d+x|\d+\.\d+[kmbKM]?|>\d+|>\$\\?\d+|"
    r"\b\d[\d,]*\+|\b\d{1,3}(?:,\d{3})+\+?|"
    r"\b\d+\s*(?:years?|months?|weeks?|days?|hrs?|hours?|users?|clients?|docs?|students?)\b)",
    re.I,
)


def _friendly_gemini_error(detail: str) -> str:
    low = detail.lower()
    if "quota" in low or "rate limit" in low or "rate-limit" in low:
        return (
            "Gemini free-tier quota is full for now — tightened your bullets with rules "
            "and kept every number. Retry AI in ~1 hour or switch to OpenAI in the sidebar."
        )
    if "high demand" in low or "503" in low:
        return "Gemini is busy — tightened with rules and kept your metrics. Retry AI shortly."
    if "timed out" in low:
        return "Gemini timed out — tightened with rules and kept your metrics."
    if len(detail) > 220:
        return detail[:220].rsplit(" ", 1)[0] + "…"
    return detail


def _parse_retry_seconds(detail: str) -> float:
    m = re.search(r"retry in ([\d.]+)s", detail, re.I)
    return min(float(m.group(1)) + 0.5, 8.0) if m else 2.0


def resolve_api_key(provider: Provider, api_key: str | None) -> str:
    if api_key:
        return api_key.strip()
    if provider == "gemini":
        from config import BYO_KEY_ONLY, env_gemini_key

        if BYO_KEY_ONLY:
            return ""
        return env_gemini_key()
    from config import BYO_KEY_ONLY

    if BYO_KEY_ONLY:
        return ""
    return os.environ.get("OPENAI_API_KEY", "")


def effective_gemini_key(sidebar_key: str = "") -> str:
    """Sidebar key only under Model A; optional .env fallback for local dev."""
    from config import BYO_KEY_ONLY, env_gemini_key, gemini_key_looks_valid, load_env_file

    load_env_file()
    typed = sidebar_key.strip()
    if typed and gemini_key_looks_valid(typed):
        return typed
    if not BYO_KEY_ONLY:
        env = env_gemini_key()
        if env:
            return env
    return typed


def _call_openai(messages: list[dict[str, str]], api_key: str) -> str:
    resp = requests.post(
        OPENAI_URL,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": OPENAI_MODEL,
            "messages": messages,
            "temperature": 0.3,
            "response_format": {"type": "json_object"},
        },
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


GEMINI_CONNECT_TIMEOUT = 15
GEMINI_READ_TIMEOUT = 45
GEMINI_RETRIES = 2


def _gemini_generate(
    prompt: str,
    api_key: str,
    *,
    json_mode: bool = True,
) -> str:
    last_error: Exception | None = None
    last_detail = ""
    headers = {"x-goog-api-key": api_key, "Content-Type": "application/json"}
    payload: dict[str, Any] = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.3},
    }
    if json_mode:
        payload["generationConfig"]["responseMimeType"] = "application/json"

    for model in GEMINI_MODELS:
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{model}:generateContent"
        )
        for attempt in range(GEMINI_RETRIES):
            try:
                resp = requests.post(
                    url,
                    headers=headers,
                    json=payload,
                    timeout=(GEMINI_CONNECT_TIMEOUT, GEMINI_READ_TIMEOUT),
                )
            except (requests.Timeout, requests.ConnectionError) as e:
                last_error = e
                last_detail = "timed out" if isinstance(e, requests.Timeout) else str(e)
                if attempt + 1 < GEMINI_RETRIES:
                    time.sleep(2)
                    continue
                break

            if resp.status_code == 404:
                break
            try:
                resp.raise_for_status()
            except requests.HTTPError as e:
                last_error = e
                try:
                    last_detail = resp.json().get("error", {}).get("message", "")
                except Exception:
                    pass
                if resp.status_code in (401, 403):
                    raise
                if resp.status_code == 429:
                    last_detail = last_detail or "quota exceeded"
                    time.sleep(_parse_retry_seconds(last_detail))
                    break  # try next model
                if resp.status_code == 503:
                    time.sleep(1.5)
                    continue
                break

            data = resp.json()
            return data["candidates"][0]["content"]["parts"][0]["text"]

    if last_error:
        if "timed out" in last_detail.lower() or isinstance(last_error, requests.Timeout):
            raise requests.RequestException(
                "Gemini timed out — try again or use rule-based tightening."
            ) from last_error
        if "high demand" in last_detail.lower():
            raise requests.RequestException(
                "All Gemini models busy — wait a minute and retry."
            ) from last_error
        if isinstance(last_error, requests.HTTPError):
            raise last_error
        raise requests.RequestException(str(last_error)) from last_error
    raise requests.RequestException("No Gemini model available for this API key.")


def _call_gemini(prompt: str, api_key: str) -> str:
    return _gemini_generate(prompt, api_key, json_mode=True)


def _call_gemini_raw(prompt: str, api_key: str) -> str:
    return _gemini_generate(prompt, api_key, json_mode=False)


def _extract_json(raw: str) -> str:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw.strip())
    start = raw.find("{")
    end = raw.rfind("}")
    if start != -1 and end != -1 and end > start:
        return raw[start : end + 1]
    return raw


def _parse_bullets(raw: str, expected: int) -> list[str] | None:
    try:
        parsed: dict[str, Any] = json.loads(_extract_json(raw))
    except json.JSONDecodeError:
        return None
    bullets = parsed.get("bullets")
    if not isinstance(bullets, list) or len(bullets) != expected:
        return None
    return [str(b).strip() for b in bullets]


def _extract_metrics(text: str) -> list[str]:
    return METRIC_RE.findall(text)


def _metrics_preserved(original: str, rewritten: str) -> bool:
    orig = _extract_metrics(original)
    if not orig:
        return True
    return all(m in rewritten for m in orig)


def _clean_bullet(text: str) -> str:
    """Strip LaTeX noise from extracted bullet bodies."""
    t = re.sub(r"\s+", " ", text.strip()).rstrip(".")
    t = re.sub(r"\}+\s*$", "", t)
    t = re.sub(r"^\{+", "", t)
    return t.strip()


def _looks_truncated(original: str, rewritten: str) -> bool:
    """Detect chop-off (prefix of original) vs real rewrite."""
    o = _clean_bullet(original)
    r = _clean_bullet(rewritten)
    if not r:
        return True
    if len(r) >= len(o) * 0.88 and len(r) <= len(o):
        return False
    if o.startswith(r.rstrip(".")) and len(r) < len(o) - 15:
        return True
    o_tail = o[len(r) : len(r) + 20].strip() if len(o) > len(r) else ""
    if o_tail and not o_tail[0] in ".,;:":
        return True
    o_kw = {w.lower() for w in re.findall(r"[A-Za-z]{5,}", o)}
    r_kw = {w.lower() for w in re.findall(r"[A-Za-z]{5,}", r)}
    if o_kw and len(o_kw - r_kw) / max(len(o_kw), 1) > 0.45:
        return True
    return False


def _rewrite_one_bullet(
    original: str,
    *,
    company: str,
    title: str,
    max_chars: int,
    api_key: str,
    provider: Provider,
) -> str:
    """Second pass: rewrite a single bullet that was too long or truncated."""
    orig = _clean_bullet(original)
    target = max(1, int(max_chars * 0.96))
    prompt = (
        f"{SYSTEM_PROMPT}\n\n"
        f"Company: {company}\nTitle: {title}\n"
        f"MAX_CHARS: {max_chars} (aim for {target} — fill the line edge-to-edge)\n\n"
        f"Rewrite ONLY this one bullet. It must reach ~96–100% of MAX_CHARS.\n\n"
        f"Original ({len(orig)} chars):\n{orig}\n\n"
        f'Return JSON: {{"bullets":["your rewrite here"]}}'
    )
    if provider == "gemini":
        raw = _call_gemini(prompt, api_key)
    else:
        raw = _call_openai(
            [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": prompt}],
            api_key,
        )
    parsed = _parse_bullets(raw, 1)
    if not parsed:
        return _finalize_bullet(orig, orig, max_chars)
    return _enforce_edge_to_edge(orig, parsed[0], max_chars)


def _enforce_limit(text: str, max_chars: int, original: str = "") -> str:
    """Only accept text already under limit — never chop mid-sentence."""
    t = _clean_bullet(text)
    if len(t) <= max_chars:
        return t
    if original and _looks_truncated(original, t):
        return t  # caller should retry AI
    return t[:max_chars].rsplit(" ", 1)[0].strip()


def _line_too_short(line: str, max_chars: int) -> bool:
    return bool(line) and len(line) < int(max_chars * 0.92)


def _bullet_unchanged(original: str, rewritten: str) -> bool:
    o = _clean_bullet(original)
    r = _clean_bullet(rewritten)
    if not r:
        return True
    return o == r or o.lower() == r.lower()


WEAK_OPENER_RE = re.compile(
    r"^(Responsible|Was responsible|Worked|Helped|Assisted|Participated|Involved|"
    r"Building|Managing|Ensuring|Serving as|Acted as|Beginning|Starting)\b",
    re.I,
)


def _weak_opener(line: str) -> bool:
    return bool(WEAK_OPENER_RE.search(_clean_bullet(line)))


def _finalize_bullet(original: str, line: str, max_chars: int) -> str:
    from bullet_strong import (
        fill_bullet_line,
        tighten_bullet,
        _is_prefix_truncation,
        _weak_opener_local,
        fit_bullet_to_line,
        bullet_needs_work,
        _expand_toward_limit,
        _append_original_words,
        _trim_from_end,
        _contextual_pad,
        _dedupe_clauses,
    )

    orig = _clean_bullet(original)
    out = _dedupe_clauses(_clean_bullet(line))
    target = int(max_chars * 0.90)

    if _is_prefix_truncation(orig, out):
        out = fill_bullet_line(orig, orig, max_chars)

    if _bullet_unchanged(orig, out) or _weak_opener(out):
        out = tighten_bullet(orig, max_chars)
    elif len(out) < target:
        out = fill_bullet_line(orig, out, max_chars)
        out = _expand_toward_limit(orig, out, max_chars)
        out = _append_original_words(orig, out, max_chars, target)
        if len(out) < target and len(out) < int(max_chars * 0.85):
            out = _contextual_pad(orig, out, max_chars, target)

    out = _dedupe_clauses(out)
    if len(out) > int(max_chars * 0.97):
        out = _trim_from_end(out, int(max_chars * 0.97), target)

    if len(out) < target and bullet_needs_work(out, max_chars):
        fitted = fit_bullet_to_line(orig, max_chars)
        if (
            len(fitted) >= len(out)
            and not _is_prefix_truncation(orig, fitted)
            and not _weak_opener_local(fitted)
        ):
            out = fitted

    if _is_prefix_truncation(orig, out):
        out = fill_bullet_line(orig, out, max_chars)

    return out


def _enforce_edge_to_edge(original: str, line: str, max_chars: int) -> str:
    """Final pass: one full line, whether adding metrics or strengthening."""
    from bullet_strong import fill_bullet_line, _trim_from_end, _dedupe_clauses

    orig = _clean_bullet(original)
    out = _finalize_bullet(orig, _clean_bullet(line), max_chars)
    target = int(max_chars * 0.90)
    hard_max = int(max_chars * 0.97)
    if len(out) > hard_max:
        out = _trim_from_end(out, hard_max, target)
    # Only expand modestly — AI output near the limit should not be padded further
    if len(out) < target and len(out) < int(max_chars * 0.85):
        out = fill_bullet_line(orig, out, max_chars)
    if len(out) > hard_max:
        out = _trim_from_end(out, hard_max, target)
    return _dedupe_clauses(out)


def _build_user_msg(
    company: str,
    title: str,
    dates: str,
    max_chars: int,
    bullets: list[str],
    feedback: str = "",
    indices_to_rewrite: set[int] | None = None,
) -> str:
    target_lo = max(1, int(max_chars * 0.88))
    role_block = (
        f"Company: {company}\nTitle: {title}\nDates: {dates}\n"
        f"Line width: one full line edge-to-edge across the page "
        f"(~{max_chars} chars — each bullet MUST be {target_lo}–{int(max_chars * 0.97)} chars; "
        f"NEVER wrap to a second line)"
    )
    numbered_lines: list[str] = []
    min_len = max(1, int(max_chars * 0.92))
    for i, b in enumerate(bullets):
        metrics = _extract_metrics(b)
        short_flag = f" ({len(b)} chars — TOO SHORT, expand to {target_lo}–{max_chars})" if len(b) < min_len else ""
        line = f"{i + 1}.{short_flag} {b}"
        if metrics:
            line += f"\n   KEEP these numbers/metrics: {', '.join(metrics)}"
        numbered_lines.append(line)
    numbered = "\n".join(numbered_lines)
    rewrite_note = (
        "Rewrite EVERY bullet below for this role — each must be recruiter-strong "
        f"AND reach {target_lo}–{max_chars} chars (edge-to-edge)."
    )
    if indices_to_rewrite is not None and len(indices_to_rewrite) < len(bullets):
        nums = ", ".join(str(i + 1) for i in sorted(indices_to_rewrite))
        rewrite_note = (
            f"Rewrite ONLY bullet(s) {nums} below. "
            f"Return JSON with ALL {len(bullets)} bullets in the same order — "
            f"copy every other bullet verbatim with no changes."
        )
    msg = (
        f"{SYSTEM_PROMPT}\n\n"
        f"{role_block}\n\n"
        f"{rewrite_note} "
        f"Keep ALL metrics and accomplishments — compress filler only.\n\n"
        f"Bullets:\n{numbered}"
    )
    if feedback.strip():
        scope = "selected bullets" if indices_to_rewrite and len(indices_to_rewrite) < len(bullets) else "all bullets"
        msg += (
            f"\n\n{FEEDBACK_LINE_RULE}\n\n"
            f"User chat context and revision request "
            f"(follow this closely; apply to {scope} where relevant):\n{feedback.strip()}"
        )
    return msg


def _postprocess_bullets(
    originals: list[str],
    rewritten: list[str],
    max_chars: int,
    *,
    company: str = "",
    title: str = "",
    api_key: str = "",
    provider: Provider = "gemini",
    indices_to_rewrite: set[int] | None = None,
) -> list[str]:
    from bullet_strong import bullet_needs_work, tighten_bullet

    result: list[str] = []
    for idx, (orig, new) in enumerate(zip(originals, rewritten)):
        orig = _clean_bullet(orig)
        if indices_to_rewrite is not None and idx not in indices_to_rewrite:
            result.append(orig)
            continue
        line = _clean_bullet(new)
        needs_retry = (
            len(line) > max_chars
            or _looks_truncated(orig, line)
            or not _metrics_preserved(orig, line)
            or bullet_needs_work(line, max_chars)
            or _bullet_unchanged(orig, line)
        )
        if needs_retry and api_key:
            try:
                line = _rewrite_one_bullet(
                    orig,
                    company=company,
                    title=title,
                    max_chars=max_chars,
                    api_key=api_key,
                    provider=provider,
                )
                line = _clean_bullet(line)
            except Exception:
                line = tighten_bullet(orig, max_chars)
        line = _enforce_edge_to_edge(orig, line, max_chars)
        result.append(line)
    return result


def rewrite_section_bullets(
    bullets: list[str],
    *,
    company: str,
    title: str,
    dates: str,
    max_chars: int,
    api_key: str | None = None,
    provider: Provider = "gemini",
    feedback: str = "",
    indices_to_rewrite: set[int] | None = None,
) -> tuple[list[str], str | None]:
    """
    Rewrite all bullets in an experience section with full job context.
    Returns (rewritten_bullets, error_message).
    """
    key = resolve_api_key(provider, api_key)
    if not key:
        label = "Gemini" if provider == "gemini" else "OpenAI"
        return bullets, f"No {label} API key — using rule-based tightening instead."

    user_msg = _build_user_msg(
        company,
        title,
        dates,
        max_chars,
        [_clean_bullet(b) for b in bullets],
        feedback,
        indices_to_rewrite=indices_to_rewrite,
    )

    try:
        if provider == "gemini":
            raw = _call_gemini(user_msg, key)
        else:
            raw = _call_openai(
                [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": user_msg}],
                key,
            )
    except requests.HTTPError as e:
        detail = ""
        try:
            body = e.response.json()
            detail = (
                body.get("error", {}).get("message")
                or body.get("error", {}).get("message", "")
                or str(body)
            )
        except Exception:
            pass
        name = "Gemini" if provider == "gemini" else "OpenAI"
        msg = _friendly_gemini_error(detail) if provider == "gemini" else (detail or str(e))
        return bullets, f"{name}: {msg}"
    except requests.RequestException as e:
        return bullets, str(e)

    rewritten = _parse_bullets(raw, len(bullets))
    if not rewritten:
        return bullets, "AI returned an unexpected format — bullets unchanged."

    if indices_to_rewrite is not None and len(indices_to_rewrite) < len(bullets):
        cleaned = [_clean_bullet(b) for b in bullets]
        for i, orig in enumerate(cleaned):
            if i not in indices_to_rewrite and i < len(rewritten):
                rewritten[i] = orig

    return _postprocess_bullets(
        bullets,
        rewritten,
        max_chars,
        company=company,
        title=title,
        api_key=key,
        provider=provider,
        indices_to_rewrite=indices_to_rewrite,
    ), None


def test_gemini_key(api_key: str) -> tuple[bool, str]:
    """Quick sanity check for a Gemini API key."""
    key = api_key.strip()
    if not key:
        return False, "No API key entered."
    if key.startswith("AQ.") and len(key) < 45:
        return False, (
            "Key looks truncated (AQ… keys are ~50 characters). "
            "Paste the full key from AI Studio."
        )
    try:
        _call_gemini('Return JSON: {"bullets":["ok"]}', key)
        return True, "Gemini key works."
    except requests.HTTPError as e:
        detail = ""
        try:
            detail = e.response.json().get("error", {}).get("message", "")
        except Exception:
            pass
        if not detail and str(e):
            detail = str(e)
        if "OAuth 2 access token" in detail:
            return False, (
                "Invalid or truncated key. Paste the full key from AI Studio "
                "(starts with AQ… or AIza…)."
            )
        if "high demand" in detail.lower() or "All Gemini models busy" in detail:
            return True, "Key valid — one model is busy; others will be tried automatically."
        return False, detail or str(e)
    except requests.RequestException as e:
        return False, str(e)
