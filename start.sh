#!/bin/bash
# Start FitLine
cd "$(dirname "$0")"

# Ensure LaTeX compilers are on PATH (Homebrew tectonic + BasicTeX)
export PATH="/opt/homebrew/bin:/usr/local/bin:/Library/TeX/texbin:$PATH"

echo "Tip: paste your free Gemini key in the sidebar (Model A)."
echo "      Local .env auto-load: add FITLINE_BYO_KEY=0 to .env"
echo ""

streamlit run chat_app.py
