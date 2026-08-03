"""FitLine marketing landing page."""

from __future__ import annotations

import streamlit as st

from brand import APP_DESCRIPTION, APP_NAME, APP_TAGLINE

LANDING_CSS = """
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
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
    background: linear-gradient(180deg, #eef2ff 0%, #f8fafc 35%, #ffffff 100%) !important;
  }
  .block-container {
    padding-top: 1.25rem !important;
    padding-bottom: 3rem !important;
    max-width: 960px !important;
  }
  .fl-font { font-family: 'Inter', system-ui, -apple-system, sans-serif; }
  div[data-testid="stButton"] > button[kind="primary"] {
    background: linear-gradient(135deg, #6366f1 0%, #7c3aed 100%) !important;
    border: none !important;
    border-radius: 12px !important;
    font-weight: 600 !important;
    font-size: 0.95rem !important;
    padding: 0.7rem 1.5rem !important;
    box-shadow: 0 8px 28px rgba(99, 102, 241, 0.32) !important;
    transition: transform 0.15s ease, box-shadow 0.15s ease !important;
  }
  div[data-testid="stButton"] > button[kind="primary"]:hover {
    transform: translateY(-2px) !important;
    box-shadow: 0 14px 32px rgba(99, 102, 241, 0.42) !important;
  }
  div[data-testid="stButton"] > button[kind="secondary"] {
    border-radius: 12px !important;
    font-weight: 600 !important;
    border: 1px solid #c7d2fe !important;
    color: #4338ca !important;
    background: #ffffff !important;
  }
  .fl-features-grid {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 1.25rem;
    max-width: 820px;
    margin: 0 auto;
  }
  .fl-feature-card {
    transition: transform 0.2s ease, box-shadow 0.2s ease;
  }
  .fl-feature-card:hover {
    transform: translateY(-4px);
    box-shadow: 0 14px 36px rgba(15, 23, 42, 0.1) !important;
  }
  @media (max-width: 640px) {
    .fl-features-grid { grid-template-columns: 1fr !important; }
  }
</style>
"""

PATHS = [
    (
        "📝",
        "I have LaTeX",
        "Paste your Overleaf main.tex",
        "Best if you already use Jake's Resume or a similar LaTeX template on Overleaf.",
    ),
    (
        "📄",
        "I only have a PDF",
        "Upload Word or PDF → get LaTeX",
        "We'll convert your PDF to editable LaTeX, then tighten every bullet line.",
    ),
]

FEATURES = [
    ("📏", "#6366f1", "Edge-to-edge lines", "Each bullet fills one full line — no awkward gaps at the margin."),
    ("🎯", "#8b5cf6", "ATS-ready", "Strong verbs, bold dates, and every metric kept."),
    ("💬", "#ec4899", "Chat to revise", "Say what to change in plain English — one job at a time."),
    ("⚡", "#14b8a6", "Live PDF preview", "See before & after instantly while you edit."),
]

STEPS = [
    ("1", "Open the editor", "Click Get started — no sign-up required."),
    ("2", "Load your resume", "Paste LaTeX or upload a PDF — we detect your jobs automatically."),
    ("3", "Pick one role", "Choose an experience in the sidebar. Fix all bullets or just one."),
    ("4", "Review & export", "Preview the PDF, chat tweaks, then download updated .tex for Overleaf."),
]


def _enter_app() -> None:
    st.session_state.page = "editor"
    st.rerun()


def _open_feedback() -> None:
    st.session_state.page = "feedback"
    st.rerun()


def _hero_html() -> str:
    return f"""
<div class="fl-font" style="
  background: linear-gradient(145deg, #0f172a 0%, #1e1b4b 45%, #3730a3 100%);
  border-radius: 28px;
  padding: 3.25rem 2rem 4rem;
  text-align: center;
  box-shadow: 0 28px 56px rgba(15, 23, 42, 0.28);
  position: relative;
  overflow: hidden;
">
  <div style="
    position:absolute; top:-40%; right:-15%; width:420px; height:420px;
    background:radial-gradient(circle, rgba(99,102,241,0.35) 0%, transparent 70%);
    pointer-events:none;
  "></div>
  <div style="
    display: inline-flex; align-items:center; gap:0.4rem;
    color: #c7d2fe;
    font-size: 0.72rem;
    font-weight: 600;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    background: rgba(255,255,255,0.07);
    border: 1px solid rgba(255,255,255,0.14);
    border-radius: 999px;
    padding: 0.4rem 1rem;
    margin-bottom: 1.35rem;
  ">
    <span style="font-size:0.85rem;">📄</span> {APP_NAME}
  </div>
  <h1 style="
    color: #ffffff;
    font-size: clamp(2rem, 5vw, 3rem);
    font-weight: 800;
    letter-spacing: -0.035em;
    line-height: 1.1;
    margin: 0 0 1rem 0;
    max-width: 640px;
    margin-left: auto;
    margin-right: auto;
  ">
    Resume bullets that<br>
    <span style="background:linear-gradient(90deg,#34d399,#6ee7b7); -webkit-background-clip:text; -webkit-text-fill-color:transparent;">fill the line</span>
  </h1>
  <p style="
    color: #cbd5e1;
    font-size: 1.05rem;
    line-height: 1.7;
    max-width: 540px;
    margin: 0 auto 0.5rem;
  ">{APP_DESCRIPTION}</p>
</div>
"""


def _demo_html() -> str:
    return """
<div class="fl-font" style="
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 18px;
  padding: 1.5rem 1.5rem 1.35rem;
  margin: 0 auto 2rem;
  max-width: 680px;
  box-shadow: 0 20px 48px rgba(15, 23, 42, 0.12);
  position: relative;
">
  <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:0.5rem; margin-bottom:0.5rem;">
    <span style="font-size:0.7rem; font-weight:700; letter-spacing:0.07em; text-transform:uppercase; color:#64748b;">
      Example rewrite
    </span>
    <span style="font-size:0.72rem; font-weight:600; background:#eef2ff; color:#4338ca; padding:0.25rem 0.7rem; border-radius:999px; border:1px solid #c7d2fe;">
      Northwind Labs — Software Intern
    </span>
  </div>
  <p style="font-size:0.78rem; color:#94a3b8; margin:0 0 1rem; line-height:1.45;">
    One bullet, one line — strengthened and expanded to the right margin.
  </p>

  <div style="margin-bottom:0.85rem;">
    <div style="font-size:0.68rem; font-weight:700; color:#94a3b8; text-transform:uppercase; letter-spacing:0.05em; margin-bottom:0.35rem;">Before</div>
    <div style="font-size:0.84rem; line-height:1.55; color:#64748b; background:#fff7ed; border-left:3px solid #fb923c; padding:0.65rem 0.85rem; border-radius:0 10px 10px 0;">
      Was responsible for helping the team build a dashboard that showed sales data for managers.
    </div>
    <div style="margin-top:0.4rem; height:4px; background:#ffedd5; border-radius:999px;">
      <div style="height:100%; width:55%; background:#fb923c; border-radius:999px;"></div>
    </div>
    <div style="font-size:0.68rem; color:#ea580c; margin-top:0.25rem;">🟠 Weak opener · 🟡 Too short</div>
  </div>

  <div style="text-align:center; color:#cbd5e1; font-size:1.1rem; margin:0.35rem 0;">↓</div>

  <div>
    <div style="font-size:0.68rem; font-weight:700; color:#94a3b8; text-transform:uppercase; letter-spacing:0.05em; margin-bottom:0.35rem;">After</div>
    <div style="font-size:0.84rem; line-height:1.55; color:#065f46; background:#ecfdf5; border-left:3px solid #34d399; padding:0.65rem 0.85rem; border-radius:0 10px 10px 0; font-weight:500;">
      Built a React sales dashboard surfacing 12 KPIs for 40+ managers, cutting weekly report prep 35%
    </div>
    <div style="margin-top:0.4rem; height:4px; background:#d1fae5; border-radius:999px;">
      <div style="height:100%; width:97%; background:linear-gradient(90deg,#6366f1,#34d399); border-radius:999px;"></div>
    </div>
    <div style="font-size:0.68rem; color:#059669; margin-top:0.25rem; font-weight:600;">🟢 Good — fills the line · metrics kept</div>
  </div>
</div>
"""


def _paths_html() -> str:
    cards = ""
    for icon, title, subtitle, body in PATHS:
        cards += f"""
<div style="
  background:#fff;
  border:1px solid #e2e8f0;
  border-radius:16px;
  padding:1.35rem 1.25rem;
  box-shadow:0 4px 20px rgba(15,23,42,0.05);
  height:100%;
">
  <div style="font-size:1.5rem; margin-bottom:0.65rem;">{icon}</div>
  <div style="font-size:1rem; font-weight:700; color:#0f172a; margin-bottom:0.2rem;">{title}</div>
  <div style="font-size:0.82rem; font-weight:600; color:#6366f1; margin-bottom:0.45rem;">{subtitle}</div>
  <div style="font-size:0.82rem; line-height:1.55; color:#64748b;">{body}</div>
</div>"""
    return f"""
<div class="fl-font" style="margin-bottom:2.25rem;">
  <h2 style="text-align:center; font-size:1.35rem; font-weight:800; color:#0f172a; margin:0 0 0.35rem; letter-spacing:-0.025em;">
    Start here
  </h2>
  <p style="text-align:center; font-size:0.88rem; color:#64748b; margin:0 0 1.25rem; max-width:480px; margin-left:auto; margin-right:auto;">
    Pick the path that matches what you have today — both end at a polished, one-line-per-bullet resume.
  </p>
  <div style="display:grid; grid-template-columns:repeat(auto-fit, minmax(260px, 1fr)); gap:1rem;">{cards}</div>
</div>
"""


def _steps_html() -> str:
    steps = ""
    for i, (num, title, body) in enumerate(STEPS):
        border = "" if i == len(STEPS) - 1 else "border-right:1px solid #e2e8f0;"
        steps += f"""
<div style="flex:1 1 200px; padding:1.25rem 1.1rem; text-align:center; {border}">
  <div style="
    width:2rem; height:2rem; margin:0 auto 0.65rem;
    background:linear-gradient(135deg,#6366f1,#8b5cf6);
    color:#fff; font-size:0.85rem; font-weight:800;
    border-radius:999px; display:flex; align-items:center; justify-content:center;
  ">{num}</div>
  <div style="font-size:0.92rem; font-weight:700; color:#0f172a; margin-bottom:0.3rem;">{title}</div>
  <div style="font-size:0.8rem; color:#64748b; line-height:1.5;">{body}</div>
</div>"""
    return f"""
<div class="fl-font" style="margin-bottom:2.25rem;">
  <h2 style="text-align:center; font-size:1.35rem; font-weight:800; color:#0f172a; margin:0 0 1.15rem; letter-spacing:-0.025em;">
    How it works
  </h2>
  <div style="display:flex; flex-wrap:wrap; background:#fff; border:1px solid #e2e8f0; border-radius:16px; overflow:hidden; box-shadow:0 4px 20px rgba(15,23,42,0.05);">{steps}</div>
</div>
"""


def _features_html() -> str:
    cards = ""
    for icon, color, title, body in FEATURES:
        cards += f"""
<div class="fl-feature-card" style="
  background:#fff;
  border:1px solid #e2e8f0;
  border-radius:18px;
  padding:1.55rem 1.45rem 1.5rem;
  box-shadow:0 4px 24px rgba(15,23,42,0.06);
  height:100%;
  position:relative;
  overflow:hidden;
">
  <div style="
    position:absolute; top:0; left:0; right:0; height:3px;
    background:linear-gradient(90deg, {color}, {color}55);
  "></div>
  <div style="
    width:2.85rem; height:2.85rem;
    background:linear-gradient(145deg, {color}20, {color}08);
    border:1px solid {color}25;
    border-radius:14px;
    display:flex; align-items:center; justify-content:center;
    font-size:1.25rem;
    margin-bottom:1.05rem;
  ">{icon}</div>
  <div style="font-size:1.02rem; font-weight:700; color:#0f172a; margin-bottom:0.45rem; letter-spacing:-0.02em;">{title}</div>
  <div style="font-size:0.88rem; line-height:1.65; color:#64748b;">{body}</div>
</div>"""
    return f"""
<div class="fl-font" style="margin-bottom:2.75rem; padding-top:0.5rem;">
  <h2 style="text-align:center; font-size:1.45rem; font-weight:800; color:#0f172a; margin:0 0 0.45rem; letter-spacing:-0.025em;">
    Why FitLine
  </h2>
  <p style="text-align:center; font-size:0.9rem; color:#64748b; margin:0 0 1.65rem; max-width:520px; margin-left:auto; margin-right:auto; line-height:1.6;">
    Built for Overleaf resumes — every bullet earns its place on the line.
  </p>
  <div class="fl-features-grid">{cards}</div>
</div>
"""


def _setup_html() -> str:
    return """
<div class="fl-font" style="
  background: linear-gradient(135deg, #f5f3ff 0%, #eef2ff 100%);
  border: 2px solid #a5b4fc;
  border-radius: 18px;
  padding: 1.5rem 1.6rem 1.6rem;
  margin-bottom: 2rem;
">
  <div style="display:flex; align-items:center; gap:0.6rem; margin-bottom:1rem;">
    <span style="font-size:1.5rem;">🔒</span>
    <div style="font-size:1.1rem; font-weight:800; color:#312e81; letter-spacing:-0.02em;">
      Private by default
    </div>
  </div>
  <p style="font-size:0.88rem; line-height:1.65; color:#4338ca; margin:0 0 1.15rem;">
    No account required. Your resume stays in this browser session only — nothing is saved on our server.
    Paste your free Gemini key in the sidebar for AI; we never store that either.
  </p>

  <div style="background:#fff; border:1px solid #c7d2fe; border-radius:14px; padding:1.2rem 1.3rem;">
    <div style="font-size:0.72rem; font-weight:800; letter-spacing:0.08em; text-transform:uppercase; color:#6366f1; margin-bottom:0.55rem;">
      Quick start
    </div>
    <ol style="margin:0; padding-left:1.2rem; font-size:0.88rem; line-height:1.75; color:#334155;">
      <li>Click <strong>Get started</strong> → open the editor</li>
      <li>Paste your free <a href="https://aistudio.google.com/apikey" target="_blank" style="color:#4f46e5; font-weight:600;">Gemini key</a> in the sidebar (for AI)</li>
      <li>Load your resume → <strong>Fix selected section</strong></li>
    </ol>
  </div>
</div>
"""


def _cta_html() -> str:
    return f"""
<div class="fl-font" style="
  text-align:center;
  background:linear-gradient(145deg,#0f172a,#312e81);
  border-radius:20px;
  padding:2.25rem 1.5rem;
  margin-bottom:1rem;
  box-shadow:0 16px 40px rgba(49,46,129,0.25);
">
  <p style="font-size:1.2rem; font-weight:700; color:#ffffff; margin:0 0 0.4rem; letter-spacing:-0.02em;">
    Ready to fix your resume?
  </p>
  <p style="font-size:0.88rem; color:#c7d2fe; margin:0 0 0.25rem; line-height:1.5;">
    Open the editor — paste LaTeX or upload a PDF to get started.
  </p>
</div>
"""


def render_landing() -> None:
    st.markdown(LANDING_CSS, unsafe_allow_html=True)

    st.markdown(_hero_html(), unsafe_allow_html=True)
    st.markdown(_demo_html(), unsafe_allow_html=True)

    c1, c2, c3 = st.columns([1, 1.4, 1])
    with c2:
        if st.button("Get started →", type="primary", use_container_width=True):
            _enter_app()

    st.markdown(_paths_html(), unsafe_allow_html=True)
    st.markdown(_setup_html(), unsafe_allow_html=True)
    st.markdown(_steps_html(), unsafe_allow_html=True)
    st.markdown(_features_html(), unsafe_allow_html=True)
    st.markdown(_cta_html(), unsafe_allow_html=True)

    c1, c2, c3 = st.columns([1, 1.4, 1])
    with c2:
        if st.button("Open editor →", type="primary", use_container_width=True):
            _enter_app()

    c1, c2, c3 = st.columns([1, 1.4, 1])
    with c2:
        if st.button("Send feedback 💬", use_container_width=True):
            _open_feedback()

    st.markdown(
        f'<p class="fl-font" style="text-align:center; font-size:0.75rem; color:#94a3b8; margin-top:1rem;">'
        f"{APP_NAME} · LaTeX resume bullets · PDF import · ATS formatting</p>",
        unsafe_allow_html=True,
    )
