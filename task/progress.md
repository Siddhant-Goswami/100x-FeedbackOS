# Build Progress

Last updated: 2026-03-15

## Status

| Phase | Status |
|-------|--------|
| Day 0 — Quickstart checklist | ✅ (DB migrations run by user) |
| Day 1 — Foundation (scaffold, schema, FastAPI, Streamlit auth, rubric seed) | ✅ |
| Days 2-5 — Core review flow (P0 screens) | ✅ |
| Days 6-7 — Tests + example seeding | ✅ |
| Days 8-10 — P1 screens (calibration, examples, analytics) | ✅ |
| Days 9-10 — Instrumentation (dialogue, comprehension, cron) | ✅ |
| Deployment config (GitHub Actions, Render, Streamlit Cloud) | ✅ |
| Deployment files (render.yaml, Procfile, .streamlit/config.toml, env parity) | ✅ |

## What's built and verified
- 16/16 Python modules import cleanly
- 45/45 tests pass
- 24 API routes registered correctly
- Supabase SQL migration file written and run
- All Streamlit pages (8) implemented
- All FastAPI routers (8) + services (6) implemented
- Rubric JSON files (4) with stable UUIDs
- Seed scripts: seed_rubrics.py, seed_examples.py, seed_test_data.py, create_auth_users.py
- GitHub Actions CI/CD + daily commit-tracking cron

## Next steps for user

### Local run
1. `cp .env.example .env` — fill in all keys
2. `python scripts/seed_rubrics.py`
3. `python scripts/seed_examples.py`
4. `python scripts/seed_test_data.py`
5. `python scripts/create_auth_users.py`
6. `cd api && uvicorn main:app --reload`   → http://localhost:8000/docs
7. `streamlit run app.py`                  → http://localhost:8501
8. Login: ta1@100x.test / feedbackos-dev-2026

### Deploy to production
1. Push repo to GitHub
2. **Render** — "New Blueprint" → connect repo → render.yaml auto-configures both services
   - Set all env vars (marked `sync: false`) in Render dashboard
   - Note the API URL, update FASTAPI_URL in Streamlit secrets
3. **Streamlit Cloud** — connect repo, main file = app.py, add secrets
4. **GitHub Actions** — add secrets: SUPABASE_URL, SUPABASE_SERVICE_KEY, GH_PAT (GitHub PAT), DISCORD_BOT_TOKEN, DISCORD_GUILD_ID, FASTAPI_URL, ANTHROPIC_API_KEY, SUPABASE_KEY
5. **GitHub Webhook** — add to student org repos: URL = https://{render-api-url}/webhooks/github, events = push only
6. Run smoke tests (see task/06_deployment.md)

## Key paths
- API: http://localhost:8000/docs
- Streamlit: http://localhost:8501
- DB migration: supabase/migrations/001_initial_schema.sql (already run)
