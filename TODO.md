# Sentra AI — Migrasi Gemini → Claude API

## Tasks

- [x] **Task 1**: Rewrite `ai_recommendation.py` — Replace Gemini SDK with Claude API (Anthropic)
  - Replaced `google.genai` imports with `requests`
  - All 3 functions (`generate_ai_insight`, `generate_compare_insight`, `generate_local_insight`) now call `https://api.anthropic.com/v1/messages`
  - Model: `claude-haiku-4-5-20251001`
  - Headers: `x-api-key`, `anthropic-version: 2023-06-01`
  - Timeout: 45s
  - All prompts (`_build_prompt`, `_build_compare_prompt`, `_build_local_prompt`) preserved exactly
  - All helper functions preserved (`_format_seasonality`)

- [x] **Task 2**: Update `app.py`
  - PDF footer: "Gemini AI" → "Claude AI"
  - Comments: "Gemini" → "Claude"
  - `/api/health` endpoint: `"gemini"` → `"claude": bool(os.environ.get("ANTHROPIC_API_KEY"))`

- [x] **Task 3**: Update `index.html`
  - "Analisis mendalam dari Gemini AI" → "Analisis mendalam dari Claude AI"
  - "Membutuhkan koneksi ke Gemini AI" → "Membutuhkan koneksi ke Claude AI"

- [x] **Task 4**: Update `requirements.txt`
  - Removed: `google-genai>=0.8.0`
  - Added: `requests>=2.31.0`

## Verification
- [x] No remaining "Gemini" references in `.py` files
- [x] No remaining "Gemini" references in `.html` files
- [x] No `google-genai` in `requirements.txt`
