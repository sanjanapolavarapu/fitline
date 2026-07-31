# FitLine

**Resume bullets that fill the line** — edge-to-edge, ATS-friendly, metrics kept.

FitLine rewrites LaTeX resume bullets so each one fills a full line without shrinking font size. Paste from Overleaf, upload a PDF, pick a job, and fix bullets with rules or AI.

## Run the app

```bash
pip install -r requirements.txt
./start.sh
# or: streamlit run chat_app.py
```

Open http://localhost:8501

**AI rewrites** need a free [Gemini API key](https://aistudio.google.com/apikey) — paste it in the sidebar when the app opens. Rule-based fixes work without a key.

## Share with others (free)

See **[DEPLOY.md](DEPLOY.md)** — free on Streamlit Community Cloud. **Model A:** each friend pastes their own free Gemini key (don't put yours in server secrets).

```bash
# Optional local Docker test before deploying
docker build -t fitline .
docker run --rm -p 8501:8501 fitline
```

## CLI (no UI)

```bash
python3 fit_resume.py my-resume.tex -o my-resume-fit.tex --show-changes
```

Upload the output `.tex` to Overleaf — no extra files needed.

## Features

- Character-based line fill (edge-to-edge, not font shrinking)
- Fix one experience at a time with live PDF preview
- Chat to revise bullets (“keep the 32% metric”, “strengthen bullet 1”)
- PDF → LaTeX import (Jake's Resume style)
- Rule-based tightening + optional Gemini/OpenAI rewrite

## Flags (CLI)

| Flag | Effect |
|------|--------|
| (default) | Tighten bullets for strength + one line |
| `--no-strong` | Only wrap `\item` → `\resumeitem`, no rewriting |
| `--show-changes` | Print before/after for each bullet |
| `--max-chars 98` | Target line length for your template |
| `--watch` | Re-run on every save |

## Requirements

- Python 3.9+
- See `requirements.txt` (`streamlit`, `pymupdf`, `requests`)
