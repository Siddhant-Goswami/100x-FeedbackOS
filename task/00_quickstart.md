# Hour Zero Quickstart Checklist

**Goal:** Working skeleton with auth, DB, and one Claude API call before writing any feature code.

## Setup

- [ ] Create GitHub repo with the full file structure (see `07_backlog.md` for structure)
- [ ] Copy `.env.example` → `.env`, fill in:
  - `ANTHROPIC_API_KEY`
  - `SUPABASE_URL` + `SUPABASE_KEY` + `SUPABASE_SERVICE_KEY`
  - `GITHUB_TOKEN` + `GITHUB_WEBHOOK_SECRET`
  - `DISCORD_BOT_TOKEN` + `DISCORD_GUILD_ID`
  - `FASTAPI_URL=http://localhost:8000`
  - `ENV=development`
- [ ] `pip install -r requirements.txt`

## Database

- [ ] Create Supabase project
- [ ] Create initial tables (start with these 4 only):
  - `users` (id, email, name, role, cohort_id, github_username, discord_id, created_at)
  - `cohorts` (id, name, start_date, end_date, status)
  - `rubrics` (id, name, version, type, stack_filter, created_by, created_at, is_active)
  - `rubric_dimensions` (id, rubric_id, name, description, category, sort_order, is_required)
- [ ] Run `python scripts/seed_rubrics.py` — confirm rubric dimensions appear in Supabase

## Backend

- [ ] Run `cd api && uvicorn main:app --reload`
- [ ] Hit `GET /health` — confirm 200 OK

## Frontend

- [ ] Run `streamlit run app.py`
- [ ] Confirm login page renders

## Smoke Tests

- [ ] Make one hardcoded Claude API call:
  ```python
  # Prompt: "Given this file list: [app.py, requirements.txt, README.md],
  # identify the tech stack. Return JSON."
  # Expected: structured JSON response
  ```
- [ ] Connect Streamlit to Supabase — read rubric dimensions, display on test page

## Deploy Skeleton

- [ ] Deploy frontend to Streamlit Cloud (connect GitHub repo)
- [ ] Deploy backend to Render (FastAPI as always-on service)
- [ ] Confirm both are reachable
- [ ] Commit and push to GitHub
