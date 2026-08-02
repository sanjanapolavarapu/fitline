"""
FitLine — paste LaTeX, preview PDF, fix specific experiences.

Run:  streamlit run chat_app.py
"""

from __future__ import annotations

import base64
import re

import streamlit as st

import importlib

import ai_rewriter
import fit_resume
from fit_resume import list_section_bullet_texts
from brand import APP_NAME, APP_TAGLINE, EXPORT_FILENAME
from landing import render_landing
from bullet_strong import bullet_status_display, render_bullet_status_legend
from line_width import effective_line_chars, line_width_hint
from pdf_to_latex import flatten_resume_bullets, pdf_to_jakes_latex, strip_fitline_package
from ai_rewriter import effective_gemini_key, resolve_api_key, test_gemini_key
from config import gemini_key_looks_valid, load_env_file
from sections import (
    diagnose_tex,
    list_itemize_blocks,
    parse_experiences,
    resolve_selection,
)
from chat_intent import help_message, parse_chat_intent, resolve_bullet_indices, active_section

EDITOR_CSS = """
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
  #MainMenu, footer, header[data-testid="stHeader"],
  div[data-testid="stToolbar"],
  div[data-testid="stToolbarActions"],
  div[data-testid="stDecoration"],
  [data-testid="stToolbarActionButton"],
  [data-testid="stToolbarActionButtonIcon"],
  .viewerBadge_container__1QSob,
  .styles_viewerBadge__1yB5_ {
    visibility: hidden !important;
    display: none !important;
    height: 0 !important;
    min-height: 0 !important;
    overflow: hidden !important;
  }
  .stApp {
    font-family: 'Inter', system-ui, sans-serif !important;
    background: #eef2f7 !important;
  }
  section.main > div.block-container,
  .block-container {
    padding-top: 1.5rem !important;
    padding-left: 2.5rem !important;
    padding-right: 2.5rem !important;
    padding-bottom: 2rem !important;
    max-width: 100% !important;
  }
  section[data-testid="stMain"] > div {
    max-width: 100% !important;
  }
  div[data-testid="stHorizontalBlock"] {
    gap: 1rem !important;
    align-items: stretch !important;
  }
  div[data-testid="column"] {
    min-width: auto !important;
  }
  div[data-testid="stVerticalBlockBorderWrapper"] {
    border-radius: 18px !important;
    border-color: #e2e8f0 !important;
    background: #ffffff !important;
    box-shadow: 0 8px 32px rgba(15, 23, 42, 0.07) !important;
    padding: 1.35rem 1.5rem 1.65rem !important;
    margin-top: 0.25rem !important;
  }
  div[data-testid="stExpander"] {
    margin-bottom: 1.25rem !important;
    border-radius: 14px !important;
    border: 1px solid #e2e8f0 !important;
    background: #ffffff !important;
  }
  div[data-testid="stExpander"] details {
    border: none !important;
  }
  div[data-testid="stExpander"] div[data-testid="stHorizontalBlock"] {
    gap: 0.75rem !important;
  }
  div[data-testid="stExpander"] div[data-testid="stButton"] > button {
    white-space: nowrap !important;
  }
  div[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #f8fafc 0%, #ffffff 100%) !important;
    border-right: 1px solid #e2e8f0 !important;
  }
  div[data-testid="stSidebar"] .stMarkdown h1, div[data-testid="stSidebar"] .stMarkdown h2,
  div[data-testid="stSidebar"] .stMarkdown h3 { letter-spacing: -0.02em; }
  div[data-testid="stChatMessage"] {
    background: #f8fafc !important;
    border: 1px solid #e2e8f0 !important;
    border-radius: 12px !important;
    padding: 0.65rem 0.85rem !important;
  }
  div[data-testid="stChatMessage"][data-testid="user"] {
    background: #eef2ff !important;
    border-color: #c7d2fe !important;
  }
  div[data-testid="stButton"] > button[kind="primary"] {
    background: linear-gradient(135deg, #6366f1 0%, #7c3aed 100%) !important;
    border: none !important;
    border-radius: 10px !important;
    font-weight: 600 !important;
  }
  .fl-app-header {
    margin-bottom: 1.25rem !important;
    padding-top: 0.5rem !important;
    line-height: 1.3 !important;
  }
  .fl-app-header span {
    display: inline-block;
    line-height: 1.2 !important;
  }
  .fl-panel-banner {
    margin-bottom: 1.15rem !important;
  }
  .fl-legend {
    font-size: 0.8rem;
    color: #64748b;
    margin: 0 0 1.1rem;
    line-height: 1.65;
    padding: 0.65rem 0.85rem;
    background: #f8fafc;
    border-radius: 12px;
    border: 1px solid #eef2f7;
  }
  .fl-empty-state {
    background: #f8fafc;
    border: 2px dashed #cbd5e1;
    border-radius: 16px;
    padding: 2.75rem 2rem;
    text-align: center;
    color: #64748b;
    font-size: 0.92rem;
    line-height: 1.7;
    margin-bottom: 1rem;
  }
  .fl-empty-preview {
    min-height: calc(100vh - 15rem);
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    background: #f8fafc;
    border: 2px dashed #cbd5e1;
    border-radius: 16px;
    padding: 3rem 2.5rem;
    text-align: center;
    color: #64748b;
    font-size: 0.95rem;
    line-height: 1.7;
  }
  .fl-chat-wrap {
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 16px;
    padding: 1rem 1.1rem 0.75rem;
    margin-bottom: 1rem;
    min-height: 180px;
    max-height: calc(100vh - 28rem);
    overflow-y: auto;
  }
  .fl-chat-wrap::-webkit-scrollbar { width: 6px; }
  .fl-chat-wrap::-webkit-scrollbar-thumb { background: #cbd5e1; border-radius: 999px; }
  .fl-msg { display: flex; gap: 0.65rem; margin-bottom: 0.9rem; align-items: flex-start; }
  .fl-msg-user { justify-content: flex-end; }
  .fl-avatar {
    width: 1.85rem; height: 1.85rem; border-radius: 999px; flex-shrink: 0;
    background: linear-gradient(135deg, #6366f1, #8b5cf6);
    color: #fff; font-size: 0.72rem; font-weight: 700;
    display: flex; align-items: center; justify-content: center;
    box-shadow: 0 2px 8px rgba(99,102,241,0.35);
  }
  .fl-bubble {
    max-width: 88%; padding: 0.85rem 1rem; border-radius: 14px;
    font-size: 0.9rem; line-height: 1.6; font-family: 'Inter', system-ui, sans-serif;
  }
  .fl-bubble-user {
    background: linear-gradient(135deg, #6366f1 0%, #7c3aed 100%);
    color: #ffffff; border-bottom-right-radius: 4px;
    box-shadow: 0 4px 14px rgba(99,102,241,0.28);
  }
  .fl-bubble-ai {
    background: #ffffff; color: #1e293b; border: 1px solid #e2e8f0;
    border-bottom-left-radius: 4px; box-shadow: 0 2px 8px rgba(15,23,42,0.05);
  }
  .fl-bubble-ai strong { color: #4338ca; }
  .fl-section-chip {
    display: inline-flex; align-items: center; gap: 0.35rem;
    background: linear-gradient(135deg, #eef2ff, #f5f3ff);
    border: 1px solid #c7d2fe; color: #4338ca;
    font-size: 0.78rem; font-weight: 600; padding: 0.35rem 0.75rem;
    border-radius: 999px; margin-bottom: 0.65rem;
  }
  .fl-pdf-wrap iframe {
    width: 100% !important;
    height: calc(100vh - 14rem) !important;
    min-height: 560px;
    border: none;
    border-radius: 12px;
  }
  div[data-testid="stChatInput"] {
    margin-top: 1.25rem !important;
    margin-bottom: 0.75rem !important;
    padding: 1rem 0 0.85rem !important;
    border-top: 1px solid #eef2f7;
  }
  div[data-testid="stChatInput"] > div {
    align-items: center !important;
    min-height: 3.75rem !important;
    padding: 0.15rem 0 !important;
  }
  div[data-testid="stChatInput"] textarea {
    border-radius: 16px !important;
    border: 1px solid #c7d2fe !important;
    background: #ffffff !important;
    padding: 1.05rem 3.25rem 1.05rem 1.2rem !important;
    min-height: 3.75rem !important;
    line-height: 1.55 !important;
    font-size: 0.92rem !important;
  }
  div[data-testid="stChatInput"] button {
    margin-bottom: 0.15rem !important;
  }
  div[data-testid="stAlert"] {
    margin-bottom: 1rem !important;
    border-radius: 12px !important;
  }
</style>
"""


def _panel_banner(title: str, subtitle: str = "", accent: str = "#6366f1") -> None:
    st.markdown(
        f"""
<div class="fl-panel-banner" style="
  font-family: 'Inter', system-ui, sans-serif;
  background: linear-gradient(135deg, #ffffff 0%, #f8fafc 100%);
  border: 1px solid #e2e8f0;
  border-left: 4px solid {accent};
  border-radius: 16px;
  padding: 1.1rem 1.35rem;
  margin-bottom: 1.15rem;
  box-shadow: 0 2px 10px rgba(15, 23, 42, 0.04);
">
  <div style="font-size: 1.12rem; font-weight: 700; color: #0f172a; letter-spacing: -0.02em;">{title}</div>
  {f'<div style="font-size: 0.88rem; color: #64748b; margin-top: 0.35rem; line-height: 1.5;">{subtitle}</div>' if subtitle else ''}
</div>
""",
        unsafe_allow_html=True,
    )


def show_pdf(pdf_bytes: bytes, height: int = 720) -> None:
    """Embed PDF — works on Streamlit versions without st.pdf."""
    b64 = base64.b64encode(pdf_bytes).decode()
    st.markdown(
        f'<div class="fl-pdf-wrap"><iframe src="data:application/pdf;base64,{b64}" '
        f'width="100%" height="{height}" style="border:none;"></iframe></div>',
        unsafe_allow_html=True,
    )


def looks_like_tex(text: str) -> bool:
    t = text.strip()
    return len(t) > 20 and bool(
        t.startswith("\\documentclass")
        or "\\begin{document}" in t
        or "\\role" in t
        or "\\rolefit" in t
        or "\\resumeSubheading" in t
        or "\\resumeItem" in t
        or "\\begin{tightemize}" in t
        or ("\\item" in t and "\\begin{itemize}" in t)
        or ("\\item" in t and "\\begin{tightemize}" in t)
        or ("\\item" in t and "\\" in t)
    )


def format_changes(
    changes: list[tuple[str, str]],
    line_chars: int,
    *,
    short_count: int = 0,
) -> str:
    if not changes:
        if short_count:
            return (
                f"**{short_count} bullet(s) in this section still need work.** "
                "Click **Fix selected section** again, "
                "or say *make every line edge-to-edge* in chat."
            )
        return "Bullets already fit — all numbers and metrics kept as-is."
    from ai_rewriter import _extract_metrics, _looks_truncated

    parts = []
    for i, (before, after) in enumerate(changes, 1):
        _, after_label = bullet_status_display(after, line_chars)
        if _looks_truncated(before, after):
            fill_note = "**cut off mid-sentence** — needs another pass"
        else:
            fill_note = after_label
        metrics = _extract_metrics(before)
        metric_note = f" · **{len(metrics)} metrics kept**" if metrics else ""
        parts.append(f"**Bullet {i}** — {fill_note}{metric_note}\n")
        parts.append(f"- **Before:** {before}\n")
        parts.append(f"- **After:** {after}\n")
    return "\n".join(parts)


def line_chars_for(tex: str | None) -> int:
    if not tex:
        return 98
    return effective_line_chars(tex)


def count_short_bullets(tex: str, line_chars: int, section_label: str | None = None) -> int:
    """Bullets that still need work — optionally scoped to one section."""
    from bullet_strong import bullet_needs_work

    if section_label:
        block = resolve_selection(tex, section_label)
        if block:
            return sum(
                1
                for bullet in list_section_bullet_texts(tex[block.start : block.end])
                if bullet_needs_work(bullet, line_chars)
            )
    total = 0
    for exp in parse_experiences(tex) or list_itemize_blocks(tex):
        for bullet in list_section_bullet_texts(tex[exp.start : exp.end]):
            if bullet_needs_work(bullet, line_chars):
                total += 1
    return total


def _sanitize_stored_tex(tex: str) -> str:
    """Repair known LaTeX corruption before storing (see compile_tex.sanitize_tex)."""
    try:
        from compile_tex import sanitize_tex

        return sanitize_tex(tex)
    except ImportError:
        return tex


def _compile_tex_to_pdf(tex: str) -> tuple[bytes | None, str | None, str | None, str | None]:
    """Compile with auto-fix; reload compile_tex so Streamlit picks up latest code."""
    import compile_tex as ct

    importlib.reload(ct)
    result = ct.compile_tex_to_pdf(tex)
    if len(result) == 4:
        return result
    pdf, err = result  # type: ignore[misc]
    return pdf, err, None, None


def compile_and_store(tex: str, *, which: str) -> str | None:
    pdf, err, repaired, notice = _compile_tex_to_pdf(tex)
    if repaired and pdf:
        if which == "source":
            st.session_state.source_tex = repaired
            st.session_state.working_tex = repaired
        else:
            st.session_state.fixed_tex = repaired
            st.session_state.working_tex = repaired
    if which == "source":
        st.session_state.source_pdf = pdf
        st.session_state.source_compile_error = err
        if notice and pdf:
            st.session_state.source_preview_notice = notice
        elif err:
            st.session_state.source_preview_notice = None
    else:
        st.session_state.fixed_pdf = pdf
        st.session_state.fixed_compile_error = err
        if notice and pdf:
            st.session_state.fixed_preview_notice = notice
        elif err:
            st.session_state.fixed_preview_notice = None
    return notice if pdf and notice else None


def load_resume(tex: str, label: str = "pasted resume") -> None:
    tex = flatten_resume_bullets(_sanitize_stored_tex(tex))
    st.session_state.source_tex = tex
    st.session_state.working_tex = tex
    st.session_state.fixed_tex = None
    st.session_state.fixed_pdf = None
    st.session_state.source_label = label
    st.session_state.experiences = parse_experiences(tex)
    if not st.session_state.experiences:
        st.session_state.experiences = list_itemize_blocks(tex)
    if st.session_state.experiences:
        st.session_state.selected_section = st.session_state.experiences[0].label
    st.session_state.line_chars = effective_line_chars(tex)
    with st.spinner("Compiling PDF preview…"):
        compile_and_store(tex, which="source")


def active_api_key(provider: str) -> str | None:
    if provider == "gemini":
        key = effective_gemini_key(st.session_state.gemini_api_key)
    else:
        raw = st.session_state.openai_api_key.strip()
        key = resolve_api_key(provider, raw or None)  # type: ignore[arg-type]
    return key or None


def _bullet_preview(text: str, limit: int = 68) -> str:
    flat = re.sub(r"\s+", " ", text.strip())
    if len(flat) <= limit:
        return flat
    return flat[: limit - 1].rstrip() + "…"


def render_bullet_line_analysis(bullets: list[str], line_chars: int) -> None:
    """Color-coded line fill status without exposing char counts."""
    if not bullets or not line_chars:
        return
    st.caption(render_bullet_status_legend())
    for i, text in enumerate(bullets):
        icon, label = bullet_status_display(text, line_chars)
        st.caption(f"{icon} **{i + 1}.** {label}")


def bullets_for_section(section_label: str | None) -> list[str]:
    if not section_label or section_label in ("All sections", "— type company above —"):
        return []
    base = st.session_state.working_tex or st.session_state.source_tex
    if not base:
        return []
    block = resolve_selection(base, section_label)
    if not block:
        return []
    return list_section_bullet_texts(base[block.start : block.end])


def apply_fix(
    strong: bool,
    company: str | None,
    api_key: str | None,
    use_ai: bool,
    provider: str,
    feedback: str = "",
    bullet_indices: set[int] | None = None,
) -> str:
    base = st.session_state.working_tex or st.session_state.source_tex
    if not base:
        return "Paste your LaTeX above and click **Load resume** first."

    line_chars = line_chars_for(base)
    st.session_state.line_chars = line_chars

    company_arg = None if not company or company == "All sections" else company
    block = resolve_selection(base, company_arg) if company_arg else None
    if block:
        company_arg = block.label

    resolved_key = active_api_key(provider) if api_key is None else resolve_api_key(provider, api_key)  # type: ignore[arg-type]
    resolved_key = resolved_key or None

    use_ai_for_fix = use_ai and bool(resolved_key)
    if use_ai and not resolved_key:
        rules_fallback_note = (
            "No Gemini key in sidebar — used **rule-based** line fill. "
            "Paste a free key for smarter rewrites."
        )
    else:
        rules_fallback_note = ""

    if use_ai_for_fix and not company_arg:
        return (
            "⚠️ Pick a **specific section** in the sidebar (not “All sections”) — "
            "AI rewrite runs one section at a time."
        )

    if bullet_indices is not None and not bullet_indices:
        return "⚠️ Pick at least **one bullet** to fix in the sidebar."

    spinner_msg = "Rewriting bullets with AI…" if use_ai_for_fix else "Tightening bullets…"

    with st.spinner(spinner_msg):
        importlib.reload(ai_rewriter)
        importlib.reload(fit_resume)
        result, stats = fit_resume.process(
            base,
            strong=strong,
            max_chars=line_chars,
            company=company_arg,
            api_key=resolved_key,
            use_ai=use_ai_for_fix,
            provider=provider,
            feedback=feedback,
            bullet_indices=bullet_indices,
        )

    if stats.get("error"):
        return f"⚠️ {stats['error']}"

    st.session_state.working_tex = _sanitize_stored_tex(result)
    st.session_state.fixed_tex = st.session_state.working_tex
    st.session_state.last_stats = stats
    st.session_state.experiences = parse_experiences(result)
    st.session_state.preview_tab = "Fixed"
    st.session_state.pending_review = {
        "section": stats.get("section", company_arg or "resume"),
        "changes": stats.get("changes", []),
        "company": company_arg,
        "bullet_indices": sorted(bullet_indices) if bullet_indices is not None else None,
    }

    with st.spinner("Updating PDF preview…"):
        compile_and_store(result, which="fixed")

    section = stats.get("section", "resume")
    mode = stats.get("mode", "rules")
    ai_note = stats.get("ai_note") or ""
    mode_label = "**AI rewrite** (context-aware)" if mode == "ai" else (
        "**rule-based** (kept your numbers)" if mode == "rules" and ai_note else "**rule-based** trim"
    )
    parts: list[str] = []

    if rules_fallback_note:
        parts.append(f"ℹ️ {rules_fallback_note}\n\n")

    if ai_note and mode != "ai":
        low = ai_note.lower()
        if "quota" in low or "rate limit" in low or "rate-limit" in low:
            parts.append(f"⚠️ {ai_note}\n\n")
        elif "timed out" in low or "busy" in low or "high demand" in low:
            parts.append(f"⚠️ {ai_note}\n\n")
        elif mode == "rules":
            parts.append(f"ℹ️ {ai_note}\n\n")
        else:
            parts.append(f"⚠️ **AI rewrite failed** — {ai_note}\n\n")

    parts.append(
        f"Fixed **{section}** — {stats['rewritten']} of {stats['items']} bullets updated ({mode_label})."
    )
    if stats.get("fallback_note"):
        parts.append(f"\n> {stats['fallback_note']}")
    if ai_note and mode == "ai":
        parts.append(f"\n> {ai_note}")
    short_after = count_short_bullets(
        st.session_state.working_tex or result,
        line_chars,
        section_label=company_arg,
    )
    short_resume = count_short_bullets(st.session_state.working_tex or result, line_chars)
    parts.append("\n\n" + format_changes(stats["changes"], line_chars, short_count=short_after))
    if stats["rewritten"] == 0 and not stats["changes"]:
        parts.append(
            "\n\n⚠️ **No bullets changed** — the rewriter could not improve the selected lines. "
            "Check your API key, or try chat: *make every line edge-to-edge*."
        )
    elif short_after:
        parts.append(
            f"\n\n💡 **{short_after} bullet(s) in this section still need work** — "
            "click **Fix selected section** again or ask in chat to expand them."
        )
    elif short_resume > 0 and company_arg:
        parts.append(
            f"\n\nℹ️ This section looks good. **{short_resume} bullet(s) elsewhere** in your resume "
            "still need fixing — pick another job in the sidebar."
        )
    parts.append(
        "\n\n**Review the Fixed PDF** on the right. "
        "Are these bullets accurate and strong enough?\n"
        "- Say **looks good** in chat, or click **Accept**\n"
        "- Or chat what to change — e.g. *keep the 32% metric* or *make the first bullet stronger*"
    )
    return "".join(parts)


def render_review_panel(strong: bool, use_ai: bool, provider: str) -> None:
    """Accept or request revisions — PDF stays in the side panel."""
    review = st.session_state.get("pending_review")
    if not review:
        return

    st.markdown(
        """
<div style="
  background: linear-gradient(135deg, #ecfdf5 0%, #f0fdf4 100%);
  border: 1px solid #a7f3d0;
  border-radius: 14px;
  padding: 1rem 1.15rem;
  margin: 0.75rem 0 0.5rem;
">
  <div style="font-weight: 700; color: #065f46; font-size: 0.95rem; margin-bottom: 0.35rem;">
    Review your changes
  </div>
  <div style="font-size: 0.82rem; color: #047857; line-height: 1.5;">
    Check the <strong>Fixed</strong> preview on the right. Accept or describe what to tweak.
  </div>
</div>
""",
        unsafe_allow_html=True,
    )
    st.caption(
        f"Editing **{review['section']}** — chat below applies to this section only."
    )

    col_ok, col_rev = st.columns(2)
    with col_ok:
        if st.button("✓ Accept — looks good", type="primary", use_container_width=True):
            st.session_state.pending_review = None
            st.session_state.messages.append({
                "role": "assistant",
                "content": "Great — download the updated `.tex` from the sidebar when ready.",
            })
            st.rerun()
    with col_rev:
        revision_note = st.text_input(
            "What should change?",
            placeholder='e.g. "Keep the 32% metric and lead with impact"',
            key="revision_feedback",
            label_visibility="collapsed",
        )
        if st.button("↻ Revise bullets", use_container_width=True):
            if not revision_note.strip():
                st.warning("Describe what to keep or change.")
            else:
                rev_indices = review.get("bullet_indices")
                reply = apply_fix(
                    strong,
                    review.get("company") or review["section"],
                    None,
                    use_ai,
                    provider,
                    feedback=revision_note.strip(),
                    bullet_indices=set(rev_indices) if rev_indices is not None else None,
                )
                st.session_state.messages.append({"role": "assistant", "content": reply})
                st.session_state.preview_tab = "Fixed"
                st.rerun()


def init_state() -> None:
    defaults = {
        "source_tex": None,
        "working_tex": None,
        "source_pdf": None,
        "source_compile_error": None,
        "source_preview_notice": None,
        "source_label": None,
        "fixed_tex": None,
        "fixed_pdf": None,
        "fixed_compile_error": None,
        "fixed_preview_notice": None,
        "last_stats": None,
        "experiences": [],
        "paste_buffer": "",
        "selected_section": "All sections",
        "last_upload_id": None,
        "messages": [],
        "openai_api_key": "",
        "gemini_api_key": "",
        "ai_provider": "gemini",
        "use_ai": True,
        "manual_company": "",
        "line_chars": 98,
        "preview_tab": "Original",
        "pending_review": None,
        "converted_pdf_latex": None,
        "converted_pdf_name": None,
        "converted_pdf_error": None,
        "in_app": False,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

    load_env_file()


def render_pdf_panel(*, height: int = 780) -> None:
    if not st.session_state.source_tex:
        st.markdown(
            """
<div class="fl-empty-preview">
  <div style="font-size: 2.5rem; margin-bottom: 0.75rem;">📄</div>
  <strong style="color: #334155; font-size: 1.05rem;">PDF preview</strong>
  <div style="margin-top: 0.5rem; max-width: 22rem;">
    Paste your resume on the left and click <strong>Load resume</strong>
  </div>
</div>
""",
            unsafe_allow_html=True,
        )
        return

    options = ["Original", "Fixed"]
    default = st.session_state.get("preview_tab", "Original")
    if default not in options:
        default = "Original"
    if st.session_state.fixed_pdf and st.session_state.get("pending_review"):
        default = "Fixed"

    tab_choice = st.radio(
        "Show",
        options,
        index=options.index(default),
        horizontal=True,
        label_visibility="collapsed",
    )
    st.session_state.preview_tab = tab_choice

    if tab_choice == "Original":
        if st.session_state.source_pdf:
            if st.session_state.get("source_preview_notice"):
                st.success(st.session_state.source_preview_notice)
            show_pdf(st.session_state.source_pdf, height=height)
        elif st.session_state.source_compile_error:
            st.warning(f"Preview error: {st.session_state.source_compile_error}")
            st.caption("LaTeX is still loaded — fix bullets and export to Overleaf.")
        else:
            st.caption("Compiling preview…")
    else:
        if st.session_state.fixed_pdf:
            if st.session_state.get("fixed_preview_notice"):
                st.success(st.session_state.fixed_preview_notice)
            show_pdf(st.session_state.fixed_pdf, height=height)
        elif st.session_state.fixed_tex and st.session_state.fixed_compile_error:
            st.warning(f"Preview error: {st.session_state.fixed_compile_error}")
            with st.expander("View fixed LaTeX"):
                st.code(st.session_state.fixed_tex, language="latex")
        else:
            st.info("Pick a section in the sidebar and click **Fix selected section**.")


def render_api_key_sidebar(provider: str, use_ai: bool) -> None:
    """Model A — each user pastes their own free Gemini key."""
    st.subheader("Your free API key")
    st.caption(
        "Get one in ~30 seconds at [Google AI Studio](https://aistudio.google.com/apikey) "
        "(no credit card). Paste below — **your key, your quota**, stays in this session."
    )

    if provider == "gemini":
        key = active_api_key("gemini")
        has_key = bool(key)

        if has_key:
            st.success("Key saved — ready for AI rewrites")
        else:
            st.warning("Paste your Gemini key below to enable AI rewrites.")

        st.text_input(
            "Gemini API key",
            type="password",
            key="gemini_api_key",
            placeholder="Paste key from aistudio.google.com (starts with AIza… or AQ…)",
            help="Each person uses their own free key. Never share it publicly.",
        )

        if st.button("Test key", use_container_width=True, disabled=not active_api_key("gemini")):
            ok, msg = test_gemini_key(active_api_key("gemini") or "")
            if ok:
                st.success(msg)
            else:
                st.error(msg)

        if key and not gemini_key_looks_valid(key):
            st.warning("Key format looks unusual — paste the full key from AI Studio.")

        if key and st.session_state.get("_gemini_key_checked") != key:
            ok, msg = test_gemini_key(key)
            st.session_state["_gemini_key_checked"] = key
            st.session_state["_gemini_key_ok"] = ok
            st.session_state["_gemini_key_msg"] = msg
        if key and st.session_state.get("_gemini_key_ok") is False:
            st.error(f"Key problem: {st.session_state.get('_gemini_key_msg', '')}")
    else:
        st.text_input(
            "OpenAI API key",
            type="password",
            key="openai_api_key",
            placeholder="sk-… (paid API)",
        )
        if use_ai and not active_api_key("openai"):
            st.warning("OpenAI requires a paid API key.")


def render_sidebar_controls() -> tuple[str, bool, bool]:
    """Sidebar: API key, settings, fix controls. Returns (provider, use_ai, strong)."""
    provider = st.radio(
        "AI provider",
        options=["gemini", "openai"],
        format_func=lambda p: "Google Gemini (free)" if p == "gemini" else "OpenAI (paid)",
        index=0 if st.session_state.ai_provider == "gemini" else 1,
        horizontal=True,
    )
    st.session_state.ai_provider = provider

    render_api_key_sidebar(provider, st.session_state.use_ai)

    use_ai = st.checkbox(
        "Use AI to rewrite bullets",
        value=st.session_state.use_ai,
        help="Understands your role context and rewrites based on what you actually did",
    )
    st.session_state.use_ai = use_ai

    if use_ai and provider == "gemini" and not active_api_key("gemini"):
        st.warning("Paste your Gemini key above to enable AI. Rule-based fixes still work.")
    elif use_ai and not active_api_key(provider):
        st.info("Rule-based fixes still work without a key.")

    st.divider()
    st.header("Settings")
    strong = st.checkbox("Keep bullets strong", value=True)

    st.divider()
    st.header("Fix a section")

    exp_labels = [e.label for e in st.session_state.experiences]
    if not exp_labels and st.session_state.source_tex:
        exp_labels = [e.label for e in parse_experiences(st.session_state.source_tex) or list_itemize_blocks(st.session_state.source_tex)]
        st.session_state.experiences = parse_experiences(st.session_state.source_tex) or list_itemize_blocks(st.session_state.source_tex)

    diag = diagnose_tex(st.session_state.source_tex or "")

    if not exp_labels and st.session_state.source_tex:
        st.error("No sections detected in your paste.")
        if diag["company_hints"]:
            st.caption("Companies found near bullets: " + ", ".join(diag["company_hints"][:6]))
        manual = st.text_input(
            "Type company to fix",
            key="manual_company",
            placeholder="e.g. Acme Corp",
        )
        exp_labels = [manual.strip()] if manual.strip() else ["— type company above —"]
    elif not exp_labels:
        exp_labels = ["All sections"]

    itemize_only = (
        st.session_state.source_tex
        and diag["role_commands"] == 0
        and diag["itemize_blocks"] >= 1
    )
    if itemize_only:
        st.warning("Bullet list only — use **Fix pasted bullets** or paste full `main.tex`.")

    if st.session_state.selected_section not in exp_labels:
        st.session_state.selected_section = exp_labels[0]

    selected = st.selectbox(
        "Section / role",
        options=exp_labels,
        index=exp_labels.index(st.session_state.selected_section)
        if st.session_state.selected_section in exp_labels
        else 0,
    )
    st.session_state.selected_section = selected

    section_bullets = bullets_for_section(selected)
    picked_bullet_indices: set[int] | None = None
    if section_bullets:
        line_chars = line_chars_for(st.session_state.working_tex or st.session_state.source_tex)
        st.session_state.line_chars = line_chars
        render_bullet_line_analysis(section_bullets, line_chars)
        st.caption("Which bullets should we fix?")
        bullet_options = list(range(len(section_bullets)))
        picked = st.multiselect(
            "Bullets to fix",
            options=bullet_options,
            default=bullet_options,
            format_func=lambda i: f"{i + 1}. {_bullet_preview(section_bullets[i])}",
            label_visibility="collapsed",
            key=f"bullet_pick_{selected}",
        )
        if not picked:
            st.warning("Select at least one bullet.")
        picked_bullet_indices = set(picked)

    fix_disabled = (
        st.session_state.source_tex is None
        or selected in ("All sections", "— type company above —")
        or (section_bullets and not picked_bullet_indices)
    )
    if st.button("Fix selected section", type="primary", disabled=fix_disabled, use_container_width=True):
        reply = apply_fix(
            strong,
            selected,
            None,
            use_ai,
            provider,
            bullet_indices=picked_bullet_indices,
        )
        st.session_state.messages.append({"role": "assistant", "content": reply})
        st.session_state.preview_tab = "Fixed"
        st.rerun()

    if itemize_only and st.session_state.source_tex:
        if st.button("Fix pasted bullets", use_container_width=True):
            blocks = list_itemize_blocks(st.session_state.source_tex)
            target = blocks[0].company if blocks else "Pasted bullets"
            pasted_bullets = bullets_for_section(target) if blocks else []
            pasted_indices = set(range(len(pasted_bullets))) if pasted_bullets else None
            reply = apply_fix(
                strong,
                target,
                None,
                use_ai,
                provider,
                bullet_indices=pasted_indices,
            )
            st.session_state.messages.append({"role": "assistant", "content": reply})
            st.session_state.preview_tab = "Fixed"
            st.rerun()

    if st.session_state.fixed_tex:
        st.download_button(
            "Download updated .tex",
            data=strip_fitline_package(st.session_state.fixed_tex),
            file_name=EXPORT_FILENAME,
            use_container_width=True,
        )

    if st.session_state.source_tex:
        st.caption(f"Loaded: {st.session_state.source_label}")
        st.caption(f"{len(st.session_state.experiences)} sections found")

    return provider, use_ai, strong


def render_resume_section() -> None:
    """Resume paste/upload — compact expander once loaded."""
    loaded = bool(st.session_state.source_tex)
    label = (
        f"Resume loaded · {st.session_state.source_label or 'pasted'}"
        if loaded
        else "Add your resume"
    )

    with st.expander(label, expanded=not loaded):
        if loaded:
            st.caption(
                f"**{len(st.session_state.experiences)}** sections detected · "
                "Edit below and click **Reload** to refresh the preview."
            )
        else:
            st.caption("Paste LaTeX from Overleaf, upload a file, or convert a PDF")

        pasted = st.text_area(
            "LaTeX source",
            value=st.session_state.paste_buffer,
            height=140 if loaded else 200,
            placeholder="\\documentclass...\n\\begin{document}\n...",
            label_visibility="collapsed",
        )
        st.session_state.paste_buffer = pasted

        c1, c2 = st.columns(2, gap="small")
        with c1:
            load_label = "Reload resume" if loaded else "Load resume"
            load_clicked = st.button(load_label, type="primary", use_container_width=True)
        with c2:
            if st.button("Clear", use_container_width=True):
                st.session_state.paste_buffer = ""
                st.session_state.source_tex = None
                st.session_state.working_tex = None
                st.session_state.fixed_tex = None
                st.session_state.messages = []
                st.rerun()

        if load_clicked:
            if looks_like_tex(pasted):
                load_resume(pasted)
                n = len(st.session_state.experiences)
                if n:
                    load_msg = (
                        f"Loaded! Found **{n}** jobs: "
                        + ", ".join(e.company for e in st.session_state.experiences[:4])
                        + ". Pick one in the sidebar, then click **Fix selected section**."
                    )
                else:
                    hints = diagnose_tex(pasted)["company_hints"]
                    load_msg = (
                        "Loaded, but jobs weren't fully parsed. "
                        f"Try fixing: **{', '.join(hints[:4])}** in the sidebar."
                        if hints
                        else "Loaded, but **0 jobs** detected. Paste full `main.tex` from Overleaf **Source** view."
                    )
                st.session_state.messages = [{"role": "assistant", "content": load_msg}]
                st.rerun()
            else:
                st.error("That doesn't look like LaTeX. Paste your full `main.tex` from Overleaf.")

        uploaded = st.file_uploader("Upload .tex", type=["tex"], key="tex_upload")
        if uploaded is not None:
            file_id = f"{uploaded.name}:{uploaded.size}"
            if st.session_state.last_upload_id != file_id:
                content = uploaded.read().decode("utf-8")
                st.session_state.last_upload_id = file_id
                st.session_state.paste_buffer = content
                load_resume(content, uploaded.name)
                st.session_state.messages = [
                    {"role": "assistant", "content": f"Loaded `{uploaded.name}`. Pick a section in the sidebar."}
                ]
                st.rerun()

        pdf_up = st.file_uploader("Upload PDF", type=["pdf"], key="pdf_upload")
        if pdf_up is not None and st.button("Convert PDF → LaTeX", key="pdf_convert", use_container_width=True):
            key = active_api_key(st.session_state.ai_provider)
            if not key:
                st.session_state.converted_pdf_error = "Add a Gemini API key first (sidebar)."
            else:
                with st.spinner("Converting PDF…"):
                    importlib.reload(ai_rewriter)
                    import pdf_to_latex as pdf_mod

                    importlib.reload(pdf_mod)
                    latex, err = pdf_mod.pdf_to_jakes_latex(pdf_up.read(), api_key=key)
                if err:
                    st.session_state.converted_pdf_error = err
                else:
                    st.session_state.converted_pdf_error = None
                    st.session_state.paste_buffer = latex
                    load_resume(latex, label=f"from {pdf_up.name}")
                    n = len(st.session_state.experiences)
                    short_n = count_short_bullets(
                        st.session_state.source_tex or latex,
                        st.session_state.line_chars,
                    )
                    msg = (
                        f"Converted **{pdf_up.name}** to {APP_NAME} LaTeX"
                        + (f" — found **{n}** jobs." if n else ".")
                    )
                    if short_n:
                        msg += (
                            f"\n\n⚠️ **{short_n} bullet(s) look too short.** "
                            "Pick a section in the sidebar and click **Fix selected section**."
                        )
                    st.session_state.messages = [{"role": "assistant", "content": msg}]
            st.rerun()

        if st.session_state.get("converted_pdf_error"):
            st.error(st.session_state.converted_pdf_error)


def _format_chat_html(text: str) -> str:
    """Minimal markdown → HTML for chat bubbles."""
    import html

    safe = html.escape(text)
    safe = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", safe)
    safe = re.sub(r"\*(.+?)\*", r"<em>\1</em>", safe)
    safe = safe.replace("\n", "<br>")
    return safe


def render_chat_thread(messages: list[dict]) -> None:
    """Styled chat bubbles instead of default Streamlit chat widgets."""
    import html

    if not messages:
        return

    review = st.session_state.get("pending_review")
    if review:
        st.markdown(
            f'<div class="fl-section-chip">✦ Editing <span>{html.escape(review["section"])}</span></div>',
            unsafe_allow_html=True,
        )

    parts = ['<div class="fl-chat-wrap">']
    for msg in messages[-12:]:
        body = _format_chat_html(msg["content"])
        if msg["role"] == "user":
            parts.append(
                f'<div class="fl-msg fl-msg-user">'
                f'<div class="fl-bubble fl-bubble-user">{body}</div></div>'
            )
        else:
            parts.append(
                f'<div class="fl-msg">'
                f'<div class="fl-avatar">F</div>'
                f'<div class="fl-bubble fl-bubble-ai">{body}</div></div>'
            )
    parts.append("</div>")
    st.markdown("".join(parts), unsafe_allow_html=True)


def render_chat_column(strong: bool, use_ai: bool, provider: str) -> None:
    """Chat + results — sits beside the live PDF preview."""
    _panel_banner(
        "Chat",
        "Ask FitLine to fix bullets, revise wording, or accept changes.",
        accent="#8b5cf6",
    )

    st.markdown(
        f'<p class="fl-legend">{render_bullet_status_legend()}</p>',
        unsafe_allow_html=True,
    )

    if not st.session_state.messages:
        st.markdown(
            """
<div class="fl-empty-state">
  Load your resume above, pick a job in the sidebar, then click <strong>Fix selected section</strong>.<br><br>
  Or type <em>"fix Northwind Labs"</em> or <em>"make every line edge-to-edge"</em>.
</div>
""",
            unsafe_allow_html=True,
        )

    render_chat_thread(st.session_state.messages)

    render_review_panel(strong, use_ai, provider)

    if st.session_state.fixed_tex:
        with st.expander("View updated LaTeX"):
            st.code(st.session_state.fixed_tex, language="latex")

    if prompt := st.chat_input('Revise bullets… e.g. "keep the 32% metric"'):
        st.session_state.messages.append({"role": "user", "content": prompt})

        recent_user = [
            m["content"]
            for m in st.session_state.messages
            if m["role"] == "user"
        ][-4:-1]

        if looks_like_tex(prompt):
            st.session_state.paste_buffer = prompt
            load_resume(prompt)
            reply = (
                f"Loaded! **{len(st.session_state.experiences)}** sections found. Pick one in the sidebar."
                if st.session_state.experiences
                else "Loaded! Pick a company in the sidebar after adding your Gemini key."
            )
        else:
            intent = parse_chat_intent(
                prompt,
                st.session_state.experiences,
                pending_review=st.session_state.get("pending_review"),
                selected_section=st.session_state.selected_section,
                source_tex=st.session_state.source_tex or "",
                recent_user_messages=recent_user,
            )

            if intent["action"] == "accept":
                st.session_state.pending_review = None
                reply = "Great — download the updated `.tex` from the sidebar when ready."
            elif intent["action"] == "fix":
                key = active_api_key(st.session_state.ai_provider)
                target = intent["target"] or active_section(
                    st.session_state.get("pending_review"),
                    st.session_state.selected_section,
                )
                if not target:
                    reply = "Which job should I fix? Pick one in the sidebar, or say **fix Acme Corp**."
                else:
                    chat_bullets = bullets_for_section(target)
                    chat_indices = resolve_bullet_indices(prompt, len(chat_bullets))
                    review = st.session_state.get("pending_review") or {}
                    if (
                        chat_indices is None
                        and (review.get("company") == target or review.get("section") == target)
                        and review.get("bullet_indices")
                    ):
                        chat_indices = set(review["bullet_indices"])
                    if chat_indices is None and chat_bullets:
                        chat_indices = set(range(len(chat_bullets)))
                    reply = apply_fix(
                        strong,
                        target,
                        key,
                        st.session_state.use_ai,
                        st.session_state.ai_provider,
                        feedback=intent.get("feedback") or prompt.strip(),
                        bullet_indices=chat_indices,
                    )
            elif st.session_state.experiences:
                ctx = active_section(
                    st.session_state.get("pending_review"),
                    st.session_state.selected_section,
                )
                reply = help_message(st.session_state.experiences, active_section=ctx)
            else:
                reply = "Paste your LaTeX above and click **Load resume** first."

        st.session_state.messages.append({"role": "assistant", "content": reply})
        st.session_state.preview_tab = "Fixed"
        st.rerun()


def render_app() -> None:
    st.markdown(EDITOR_CSS, unsafe_allow_html=True)

    if not st.session_state.source_tex:
        st.info(
            "**Get started:** Paste your LaTeX below and click **Load resume**. "
            "Pick a section in the sidebar and click **Fix selected section** — preview updates live on the right."
        )
        if st.session_state.use_ai and not active_api_key(st.session_state.ai_provider):
            st.warning(
                "**Step 1:** Paste your free Gemini key in the sidebar "
                "([get one here](https://aistudio.google.com/apikey)). "
                "Rule-based fixes work without a key."
            )

    with st.sidebar:
        st.markdown(
            f'<p style="font-size:0.82rem;color:#64748b;margin:0 0 0.65rem;line-height:1.45;">'
            f'<strong style="color:#0f172a;font-size:0.95rem;">{APP_NAME}</strong><br>{APP_TAGLINE}</p>',
            unsafe_allow_html=True,
        )
        if st.button("← Home", use_container_width=True):
            st.session_state.in_app = False
            st.rerun()
        st.divider()
        provider, use_ai, strong = render_sidebar_controls()

    chat_col, preview_col = st.columns(2, gap="large")

    with chat_col:
        with st.container(border=True):
            render_resume_section()
            st.markdown("<div style='height:0.5rem'></div>", unsafe_allow_html=True)
            render_chat_column(strong, use_ai, provider)

    with preview_col:
        with st.container(border=True):
            _panel_banner(
                "Live preview",
                "Toggle Original vs Fixed after you run a fix.",
                accent="#14b8a6",
            )
            render_pdf_panel(height=900)


if __name__ == "__main__":
    st.set_page_config(page_title=APP_NAME, page_icon="📄", layout="wide")
    init_state()
    if st.session_state.in_app:
        render_app()
    else:
        render_landing()
