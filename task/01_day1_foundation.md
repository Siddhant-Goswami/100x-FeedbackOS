# Day 1 — Foundation

**Goal:** Full project scaffold, DB schema, FastAPI skeleton, Streamlit auth shell, rubric seed data.

---

## File Scaffold

- [ ] Create all directories: `api/routers/`, `api/services/`, `api/models/`, `pages/`, `discord_bot/`, `scripts/`, `rubrics/`, `tests/`
- [ ] Create placeholder files for all modules (empty with docstring is fine)
- [ ] Add `.gitignore` (Python, `.env`, `__pycache__`, `.streamlit/secrets.toml`)
- [ ] Write `requirements.txt` with all dependencies
- [ ] Write `README.md` skeleton

## Database Schema (Supabase)

Create all tables:

- [ ] `users` — id, email, name, role (enum: student/ta/instructor), cohort_id FK, github_username, discord_id, created_at
- [ ] `cohorts` — id, name, start_date, end_date, status
- [ ] `assignments` — id, cohort_id FK, title, description, rubric_id FK, due_date
- [ ] `rubrics` — id, name, version, type (enum: universal/overlay), stack_filter (nullable), created_by FK, created_at, is_active
- [ ] `rubric_dimensions` — id, rubric_id FK, name, description, category (enum), sort_order, is_required
- [ ] `submissions` — id, student_id FK, assignment_id FK, github_repo_url, github_commit_sha, detected_stack (JSONB), status (enum), submitted_at, deployed_url
- [ ] `submission_files` — id, submission_id FK, filepath, language, content_hash, size_bytes
- [ ] `reviews` — id, submission_id FK, ta_id FK, status (enum: draft/submitted/delivered), review_time_sec, created_at, submitted_at, delivered_at, action_items (JSONB)
- [ ] `review_scores` — id, review_id FK, dimension_id FK, score (enum: green/yellow/red/not_applicable/flagged_for_help), comment (nullable), action_item (nullable), action_item_source (enum)
- [ ] `example_feedback` — id, dimension_id FK, stack_context (JSONB nullable), example_comment, example_action_item, source_review_id FK, curated_by FK, quality_score, is_active
- [ ] `dialogue_logs` — id, review_id FK, dimension_id FK (nullable), message_text, author_role (enum: student/ta), discord_message_id, created_at
- [ ] `comprehension_events` — id, review_id FK, review_score_id FK, commit_sha, commit_timestamp, files_changed (JSONB), addressed (boolean), hours_after_feedback
- [ ] Enable Row Level Security on all tables
- [ ] Configure RLS policies: TAs see their own reviews + all submissions; instructors see everything; students see only their own data

## FastAPI Skeleton (`api/`)

- [ ] `api/config.py` — load all env vars, define constants
- [ ] `api/models/database.py` — Supabase client init + query helpers
- [ ] `api/models/schemas.py` — Pydantic models for User, Submission, Review, ReviewScore, RubricDimension
- [ ] `api/main.py` — FastAPI app init, CORS config, include all routers, startup event
- [ ] `GET /health` endpoint returning `{"status": "ok"}`
- [ ] Stub all router files (empty routers with TODO comments): submissions, reviews, examples, calibration, analytics, webhooks, dialogue

## Streamlit Entry Point (`app.py`)

- [ ] Multi-page app config (title, icon, layout)
- [ ] Supabase auth integration (email/password login)
- [ ] Role-based routing after login:
  - `ta` → redirect to Review Queue
  - `instructor` → redirect to Instructor Dashboard
  - `student` → redirect to Feedback View
- [ ] Session state: store `user`, `role`, `token`

## Rubric Seed Data

- [ ] Write `rubrics/universal_base.json` with dimensions:
  - Code Quality
  - Error Handling
  - Architecture
  - LLM Usage
  - Deployment
  - Documentation
  - Prompt Engineering
- [ ] Write `rubrics/overlay_streamlit_llm.json` (stack-specific additions for Streamlit + LLM)
- [ ] Write `rubrics/overlay_gradio_llm.json`
- [ ] Write `rubrics/overlay_flask_js_llm.json`
- [ ] Write `scripts/seed_rubrics.py` — reads JSON files, upserts into Supabase
- [ ] Run and verify in Supabase dashboard
