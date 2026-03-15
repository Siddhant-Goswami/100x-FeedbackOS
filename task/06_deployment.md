# Deployment + CI/CD

---

## Streamlit Cloud (Frontend)

- [ ] Connect GitHub repo to Streamlit Cloud
- [ ] Set `Main file path`: `app.py`
- [ ] Set secrets in Streamlit Cloud dashboard (mirror `.env` vars):
  - `SUPABASE_URL`, `SUPABASE_KEY`, `FASTAPI_URL`
- [ ] Auto-deploys on push to `main` branch
- [ ] Confirm production URL works + login page renders

## Render (FastAPI Backend)

- [ ] Create new Web Service on Render
- [ ] Connect GitHub repo
- [ ] Build command: `pip install -r requirements.txt`
- [ ] Start command: `cd api && uvicorn main:app --host 0.0.0.0 --port $PORT`
- [ ] Set environment variables from `.env` (all keys)
- [ ] Set to "always on" (not free tier spin-down for webhook reliability)
- [ ] Confirm `GET https://{render-url}/health` returns 200

## Discord Bot Deployment

- [ ] Add Discord bot to Render as a separate "Background Worker" service
- [ ] Start command: `cd discord_bot && python bot.py`
- [ ] Set env vars: `DISCORD_BOT_TOKEN`, `DISCORD_GUILD_ID`, `FASTAPI_URL`
- [ ] Confirm bot shows as online in Discord server

## GitHub Actions CI/CD

### Auto-deploy workflow (`.github/workflows/deploy.yml`)
- [ ] Trigger: push to `main`
- [ ] Jobs:
  - Run tests: `pytest tests/`
  - If tests pass: Render auto-deploy handles it (Render watches the branch)
- [ ] Add `RENDER_DEPLOY_HOOK_URL` secret to GitHub (Render provides this)

### Commit tracking cron (`.github/workflows/track_commits.yml`)
- [ ] Trigger: daily schedule `0 6 * * *`
- [ ] Job: `python scripts/track_commits.py`
- [ ] Required secrets: `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `GITHUB_TOKEN`

## GitHub Webhook (Student Repos)

- [ ] Configure webhook on student org or individual repos
- [ ] URL: `https://{render-url}/webhooks/github`
- [ ] Content type: `application/json`
- [ ] Secret: `GITHUB_WEBHOOK_SECRET` value
- [ ] Events: Push only
- [ ] Verify first delivery in GitHub webhook delivery log

## Environment Parity Checklist

- [ ] `.env.example` matches all env vars used in code
- [ ] Streamlit Cloud secrets match backend `.env` vars
- [ ] Render env vars match `.env`
- [ ] GitHub Actions secrets match required scripts

## Post-Deploy Smoke Test

- [ ] Login as TA → lands on Review Queue
- [ ] Login as instructor → lands on Instructor Dashboard
- [ ] Login as student → lands on Feedback View
- [ ] Push a test commit to a student repo → webhook fires → submission appears in queue
- [ ] Complete a test review → student receives Discord DM with feedback link
- [ ] Visit feedback URL → student view renders correctly
