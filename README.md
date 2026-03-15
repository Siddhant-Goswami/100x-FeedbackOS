# FeedbackOS

Rubric-based feedback standardization system for 100xEngineers mid-capstone reviews.

## What it does

- **TAs** review student submissions using a modular rubric with a quick-score interface (one click per dimension)
- **Claude API** detects the student's tech stack and suggests concrete action items for red/yellow scores
- **Example library** shows TAs how peers have phrased similar feedback
- **Peer calibration** lets TAs see score distributions across the cohort
- **Discord bot** notifies students when their review is ready and captures follow-up dialogue
- **Comprehension tracking** measures whether students act on feedback by monitoring GitHub commits
- **Analytics dashboards** give TAs their personal impact metrics and instructors cohort-wide visibility

## Architecture

```
Interface:     Streamlit (TA Dashboard + Student Feedback View + Analytics)
               Discord Bot (notifications + dialogue capture)
Backend:       FastAPI (all business logic, GitHub + Discord + Claude integrations)
Intelligence:  Claude API — stack detection + action item suggestions
Database:      Supabase (PostgreSQL) — all persistent state
Deployment:    Streamlit Cloud (frontend) | Render (FastAPI + Discord bot) | GitHub Actions (CI/CD)
```

## Setup

### Prerequisites
- Python 3.11+
- A [Supabase](https://supabase.com) project
- An [Anthropic API key](https://console.anthropic.com)
- A GitHub personal access token
- A Discord bot token

### 1. Clone and install

```bash
git clone https://github.com/your-org/feedbackos
cd feedbackos
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
# Fill in all values in .env
```

### 3. Set up the database

Open your Supabase project → SQL Editor → paste and run:

```
supabase/migrations/001_initial_schema.sql
```

### 4. Seed rubric data

```bash
python scripts/seed_rubrics.py
python scripts/seed_examples.py
```

### 5. Run locally

```bash
# Terminal 1 — FastAPI backend
cd api && uvicorn main:app --reload

# Terminal 2 — Streamlit frontend
streamlit run app.py

# Terminal 3 — Discord bot (optional for local dev)
cd discord_bot && python bot.py
```

Visit `http://localhost:8501` to see the app.
Hit `http://localhost:8000/docs` for the FastAPI interactive docs.

## Project Structure

```
feedbackos/
├── app.py                    # Streamlit entry point + auth
├── pages/
│   ├── 1_Review_Queue.py     # TA review queue
│   ├── 2_Review.py           # Core review screen (P0 — critical path)
│   ├── 3_Feedback.py         # Student feedback view
│   ├── 4_Calibration.py      # Peer calibration
│   ├── 5_Examples.py         # Example feedback library
│   ├── 6_TA_Profile.py       # TA impact metrics
│   └── 7_Instructor.py       # Instructor analytics dashboard
├── api/
│   ├── main.py               # FastAPI app
│   ├── config.py             # Env vars
│   ├── models/               # Pydantic schemas + Supabase client
│   ├── routers/              # API endpoints (submissions, reviews, webhooks, ...)
│   └── services/             # Business logic (github, llm, rubric, review, ...)
├── discord_bot/              # Discord bot + thread capture
├── scripts/                  # Seed scripts + commit tracking cron
├── rubrics/                  # Rubric JSON definitions
├── supabase/migrations/      # SQL schema
├── tests/                    # Pytest test suite
└── .github/workflows/        # CI/CD + cron jobs
```

## GitHub Webhook Setup

To automatically ingest student submissions when they push code:

1. Go to the student org or repo → Settings → Webhooks → Add webhook
2. Payload URL: `https://{your-render-url}/webhooks/github`
3. Content type: `application/json`
4. Secret: your `GITHUB_WEBHOOK_SECRET` value
5. Events: Push only

## Deployment

### Streamlit Cloud
1. Connect this GitHub repo
2. Main file: `app.py`
3. Add secrets (mirror your `.env` values) in the Streamlit Cloud dashboard

### Render (FastAPI)
1. New Web Service → connect repo
2. Build: `pip install -r requirements.txt`
3. Start: `cd api && uvicorn main:app --host 0.0.0.0 --port $PORT`
4. Add all env vars from `.env`

### Render (Discord Bot)
1. New Background Worker → connect same repo
2. Start: `cd discord_bot && python bot.py`
3. Add `DISCORD_BOT_TOKEN`, `DISCORD_GUILD_ID`, `FASTAPI_URL`

## LLM Cost Estimate

| Use case | Est. cost per call | Volume (750 students) |
|----------|-------------------|-----------------------|
| Stack detection | ~$0.004 | $3 per cohort |
| Action item suggestion | ~$0.01 | ~$22.50 per cohort |

Uses `claude-haiku-4-5-20251001` for both tasks (fast + cheap).
