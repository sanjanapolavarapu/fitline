## Before you push to GitHub

Run this checklist so nothing personal or billable leaks:

```bash
cd "resume line fitter"
git status          # .env must NOT appear
git check-ignore -v .env .fitline_users.json
git diff            # scan for keys, emails, resume text
```

| Never commit | Why |
|--------------|-----|
| `.env` | Your Gemini API key |
| `.fitline_users.json` | Login emails/password hashes |
| `.streamlit/secrets.toml` | Deploy secrets |
| Your real resume `.tex` | Personal work history |

**Safe to commit:** code, `DEPLOY.md`, `Dockerfile`, fictional **Northwind Labs** demo on landing page.

**Deploy without charges:** use [Streamlit Community Cloud](https://share.streamlit.io) only — **do not** add `GEMINI_API_KEY` to Streamlit secrets (Model A). Avoid Railway paid tiers unless you opt in manually.

---

## Share FitLine for free (Model A)

FitLine is **free for everyone** — you never charge users, and hosting is **$0** on Streamlit Community Cloud.

**Model A:** Each person pastes their **own free Gemini key** in the sidebar. You do **not** put your key on the server.

| Who | Cost |
|-----|------|
| You (hosting) | $0 — Streamlit Community Cloud |
| Your friends (AI) | $0 — each gets a free key from Google |
| Rule-based fixes | $0 — no key needed |

---

## Deploy on Streamlit (free)

1. Push this repo to GitHub.
2. Go to [share.streamlit.io](https://share.streamlit.io) → sign in with GitHub.
3. **New app** → repo `fitline` → main file **`chat_app.py`** → Deploy.
4. **Do not add `GEMINI_API_KEY` to Secrets** — Model A uses sidebar keys only.
5. Wait for build (~5 min — `packages.txt` installs LaTeX for PDF preview).
6. Share the `.streamlit.app` URL.

---

## What friends do

1. Open your link → **Create account** or log in
2. **Sidebar → paste free Gemini key** ([aistudio.google.com/apikey](https://aistudio.google.com/apikey)) — for AI
3. Paste LaTeX → **Load resume** (auto-saves to their account)
4. Pick a job → **Fix selected section**
5. Download `.tex` → Overleaf

---

## Privacy & accounts

Login is **on** (`AUTH_REQUIRED = True`). We store per user:

| Stored | Purpose |
|--------|---------|
| Email + hashed password | Login |
| Saved resume + chat | Pick up where they left off |
| Login count / last login | Usage stats |

**Not stored:** Gemini API keys (sidebar only, browser session).

**Your user count:** Set `FITLINE_ADMIN_EMAIL=your@email.com` in Streamlit Secrets or local `.env`. Only that email sees **"N registered users"** in the sidebar.

Add to Streamlit Secrets (optional):
```toml
FITLINE_ADMIN_EMAIL = "your@email.com"
```

**Legal note:** Collecting emails/resumes means you should add a short privacy line on signup (already in the app). For a school project / friends-only tool this is usually fine; don't use it commercially without proper policies.

---

## Your local setup (optional)

Model A is on by default. For **solo local dev** with `.env` auto-loading your key, add to `.env`:

```
FITLINE_BYO_KEY=0
GEMINI_API_KEY=your_key_here
```

Never commit `.env` or set `GEMINI_API_KEY` in Streamlit Cloud secrets.

---

## Alternatives (still Model A)

**Render free tier** — Docker, may sleep when idle. Do **not** set `GEMINI_API_KEY` env var.

**Hugging Face Spaces** — Docker SDK. No server key in Space secrets.

---

## Local Docker test

```bash
docker build -t fitline .
docker run --rm -p 8501:8501 fitline
```

Friends create an account and paste keys in the sidebar after opening localhost.

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| AI not working | Friend must paste their own Gemini key in sidebar |
| PDF preview fails | Check Streamlit build logs; confirm `packages.txt` is in repo |
| App slow (Render free) | Normal — wakes from sleep on first visit |
| Account gone after redeploy | Streamlit may reset files — friends re-create account; saved resumes may be lost |
