"""FitLine feedback page."""

from __future__ import annotations

import json
import os
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

import requests
import streamlit as st

from brand import APP_NAME

FEEDBACK_CSS = """
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
    background: linear-gradient(180deg, #eef2ff 0%, #f8fafc 40%, #ffffff 100%) !important;
  }
  .block-container {
    padding-top: 1.5rem !important;
    padding-bottom: 3rem !important;
    max-width: 720px !important;
  }
  div[data-testid="stButton"] > button[kind="primary"] {
    background: linear-gradient(135deg, #6366f1 0%, #7c3aed 100%) !important;
    border: none !important;
    border-radius: 12px !important;
    font-weight: 600 !important;
  }
  div[data-testid="stButton"] > button[kind="secondary"] {
    border-radius: 12px !important;
    font-weight: 600 !important;
    border: 1px solid #c7d2fe !important;
    color: #4338ca !important;
    background: #ffffff !important;
  }
</style>
"""

GITHUB_REPO = os.environ.get("FITLINE_GITHUB_REPO", "sanjanapolavarapu/fitline")
FEEDBACK_DIR = Path(__file__).parent / "feedback"
SUBMISSIONS_FILE = FEEDBACK_DIR / "submissions.jsonl"


def _feedback_webhook_url() -> str | None:
    url = os.environ.get("FEEDBACK_WEBHOOK_URL", "").strip()
    return url or None


def _header_html() -> str:
    return f"""
<div style="font-family:'Inter',system-ui,sans-serif;text-align:center;margin-bottom:1.75rem;">
  <div style="
    display:inline-flex;align-items:center;gap:0.45rem;
    background:#eef2ff;color:#4338ca;
    border:1px solid #c7d2fe;border-radius:999px;
    padding:0.35rem 0.85rem;font-size:0.72rem;font-weight:700;
    letter-spacing:0.06em;text-transform:uppercase;margin-bottom:1rem;
  ">Feedback</div>
  <h1 style="font-size:1.85rem;font-weight:800;color:#0f172a;margin:0 0 0.5rem;letter-spacing:-0.03em;">
    Help us improve {APP_NAME}
  </h1>
  <p style="font-size:0.95rem;color:#64748b;margin:0;line-height:1.6;max-width:34rem;margin-left:auto;margin-right:auto;">
    Report a bug, request a feature, or tell us what worked. Your resume is never included unless you paste it below.
  </p>
</div>
"""


def _github_issue_url(category: str, message: str, email: str, rating: int | None) -> str:
    title = f"[{category}] FitLine feedback"
    body_lines = [message.strip(), "", f"Category: {category}"]
    if rating:
        body_lines.append(f"Rating: {rating}/5")
    if email.strip():
        body_lines.append(f"Contact: {email.strip()}")
    body_lines.append("")
    body_lines.append("_Sent from the FitLine feedback page_")
    params = urllib.parse.urlencode({"title": title, "body": "\n".join(body_lines)})
    return f"https://github.com/{GITHUB_REPO}/issues/new?{params}"


def _save_submission(payload: dict) -> bool:
    try:
        FEEDBACK_DIR.mkdir(parents=True, exist_ok=True)
        with SUBMISSIONS_FILE.open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")
        return True
    except OSError:
        return False


def _post_webhook(payload: dict) -> tuple[bool, str]:
    url = _feedback_webhook_url()
    if not url:
        return False, ""
    try:
        resp = requests.post(url, json=payload, timeout=12)
        if resp.ok:
            return True, ""
        return False, f"Webhook returned {resp.status_code}"
    except requests.RequestException as exc:
        return False, str(exc)


def _submit_feedback(
    category: str,
    message: str,
    email: str,
    rating: int | None,
    include_context: bool,
) -> tuple[bool, str, str | None]:
    message = message.strip()
    if len(message) < 8:
        return False, "Please write at least a sentence so we know what to fix.", None

    payload = {
        "app": APP_NAME,
        "category": category,
        "message": message,
        "email": email.strip() or None,
        "rating": rating,
        "submitted_at": datetime.now(timezone.utc).isoformat(),
    }
    if include_context:
        payload["context"] = {
            "page": st.session_state.get("page", "feedback"),
            "had_resume_loaded": bool(st.session_state.get("source_tex")),
            "sections_found": len(st.session_state.get("experiences") or []),
        }

    saved = _save_submission(payload)
    webhook_ok, webhook_err = _post_webhook(payload)
    issue_url = _github_issue_url(category, message, email, rating)

    if webhook_ok:
        return True, "Thanks — we got your feedback.", None
    if saved:
        return True, "Thanks — your feedback was saved.", None

    if _feedback_webhook_url() and webhook_err:
        return (
            False,
            f"Could not deliver feedback ({webhook_err}). Use GitHub below instead.",
            issue_url,
        )

    return (
        True,
        "Thanks! On the hosted app we can't store feedback on the server — one quick step left:",
        issue_url,
    )


def render_feedback() -> None:
    st.markdown(FEEDBACK_CSS, unsafe_allow_html=True)
    st.markdown(_header_html(), unsafe_allow_html=True)

    nav1, nav2, nav3 = st.columns(3)
    with nav1:
        if st.button("← Home", use_container_width=True):
            st.session_state.page = "landing"
            st.rerun()
    with nav2:
        if st.button("Open editor", use_container_width=True):
            st.session_state.page = "editor"
            st.rerun()
    with nav3:
        st.link_button("GitHub repo ↗", f"https://github.com/{GITHUB_REPO}", use_container_width=True)

    st.markdown("<div style='height:0.75rem'></div>", unsafe_allow_html=True)

    with st.form("fitline_feedback", clear_on_submit=True):
        category = st.selectbox(
            "What is this about?",
            options=["Bug", "Feature idea", "Something confusing", "General"],
        )
        rating = st.slider("How is FitLine working for you?", 1, 5, 3)
        message = st.text_area(
            "Your feedback",
            placeholder="e.g. Fix selected section says 0 bullets updated but the sidebar still shows yellow…",
            height=140,
        )
        email = st.text_input(
            "Email (optional)",
            placeholder="you@email.com — only if you want a reply",
        )
        include_context = st.checkbox(
            "Include anonymous session context (whether a resume was loaded, section count — no resume text)",
            value=True,
        )
        submitted = st.form_submit_button("Send feedback", type="primary", use_container_width=True)

    if submitted:
        ok, note, issue_url = _submit_feedback(category, message, email, rating, include_context)
        if ok:
            st.success(note)
            if issue_url:
                st.link_button("Submit on GitHub →", issue_url, type="primary", use_container_width=True)
                st.caption("Opens a pre-filled issue — click **Create issue** on GitHub to finish.")
        else:
            st.error(note)
            if issue_url:
                st.link_button("Submit on GitHub instead →", issue_url, use_container_width=True)

    st.markdown(
        """
<div style="
  font-family:'Inter',system-ui,sans-serif;
  background:#f8fafc;border:1px solid #e2e8f0;border-radius:14px;
  padding:1rem 1.15rem;margin-top:1.5rem;
">
  <div style="font-size:0.82rem;font-weight:700;color:#334155;margin-bottom:0.35rem;">Privacy</div>
  <div style="font-size:0.82rem;line-height:1.6;color:#64748b;">
    We don't attach your resume unless you paste it in the message.
    Optional email is only used if we need to follow up.
  </div>
</div>
""",
        unsafe_allow_html=True,
    )
