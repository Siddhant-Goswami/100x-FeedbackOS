# Week 1 — Core Review Flow (P0 Screens)

**Days 2-5. Goal:** End-to-end review flow: submission ingestion → TA reviews → student sees feedback.

---

## Day 2 — Submission Ingestion + Review Queue (P0)

### GitHub Service (`api/services/github_service.py`)
- [ ] `fetch_repo_files(repo_url, commit_sha)` — clone/pull repo, return file tree
- [ ] `get_file_content(repo_url, filepath)` — fetch single file content
- [ ] `parse_key_files(repo_url)` — extract requirements.txt, package.json, main entry point (first 50 lines)

### Rubric Service (`api/services/rubric_service.py`)
- [ ] `get_rubric_for_assignment(assignment_id)` — load universal base rubric
- [ ] `detect_overlay(detected_stack)` — map stack JSON to correct overlay file
- [ ] `merge_rubric(base, overlay)` — combine universal + overlay dimensions, sorted by sort_order

### Submissions Router (`api/routers/submissions.py`)
- [ ] `GET /submissions` — list submissions with query filters: `ta_id`, `status`, `assignment_id`
- [ ] `GET /submissions/{id}` — submission detail + files + detected stack

### Review Queue Screen (`pages/1_Review_Queue.py`)
- [ ] Auth check — redirect to login if no session
- [ ] Fetch pending submissions via `GET /submissions?ta_id={id}&status=pending`
- [ ] Display submission cards with: student name, project title, tech stack badges, submitted_at, status dot
- [ ] Status dot logic: 🟡 new, 🔴 flagged, 🟢 standard
- [ ] Flagged submissions show which dimension is flagged, float to top
- [ ] Filter dropdown: All / New / Flagged / In Progress
- [ ] Sort dropdown: Newest / Oldest
- [ ] Click card → navigate to Review Screen (`?submission_id={id}`)

---

## Day 3 — Review Screen Core (P0) — CRITICAL PATH

### LLM Service (`api/services/llm_service.py`)
- [ ] `detect_stack(file_tree, key_file_snippets)` — call Claude Sonnet, return `{frontend, backend, llm_api, deployment_platform, confidence}`
- [ ] Prompt: file tree + key file snippets, structured output JSON
- [ ] `suggest_action_item(dimension_name, dimension_desc, score, code_snippet, examples)` — call Claude Sonnet, return `{suggested_action_item, reasoning}`
- [ ] Token budget guardrail: ~3K input max for action item suggestion

### Review Service (`api/services/review_service.py`)
- [ ] `create_review(submission_id, ta_id)` — create draft review in DB
- [ ] `update_score(review_id, dimension_id, score, comment, action_item, source)` — upsert review_score
- [ ] `check_completeness(review_id, rubric_dimensions)` — return list of unscored required dimensions
- [ ] `submit_review(review_id)` — validate completeness, set status=submitted, record submitted_at

### Reviews Router (`api/routers/reviews.py`)
- [ ] `POST /reviews` — create draft review
- [ ] `PUT /reviews/{id}` — update review metadata
- [ ] `GET /reviews/{id}/scores` — get all dimension scores
- [ ] `POST /reviews/{id}/scores` — add/update a dimension score
- [ ] `POST /reviews/{id}/suggest-action` — get AI action item suggestion
- [ ] `POST /reviews/{id}/flag-for-help` — flag a dimension
- [ ] `POST /reviews/{id}/submit` — submit completed review
- [ ] `GET /rubrics/{assignment_id}` — get merged rubric for assignment

### Submissions Router (add)
- [ ] `POST /submissions/{id}/detect-stack` — trigger Claude stack detection, store result

### Review Screen (`pages/2_Review.py`)
- [ ] Auth check
- [ ] Parse `submission_id` from query params
- [ ] Load submission detail + files + detected stack
- [ ] Load merged rubric dimensions for assignment
- [ ] Create/resume draft review via `POST /reviews` (idempotent)
- [ ] **Layout:** `st.columns([1, 1])` — left: code, right: rubric

**Left column — Code viewer:**
- [ ] File browser: `st.selectbox()` with all repo files
- [ ] Code viewer: `st.code(content, language=detected_language)`
- [ ] Show live app link if `deployed_url` exists

**Right column — Rubric:**
- [ ] Progress bar: `{scored} of {total} scored`
- [ ] Per dimension card (loop over rubric_dimensions):
  - [ ] Dimension name + description
  - [ ] Quick-score buttons: 🟢 Green / 🟡 Yellow / 🔴 Red
  - [ ] Comment `st.text_area()` — appears after yellow/red (optional for green)
  - [ ] After red score: call `POST /reviews/{id}/suggest-action`, show suggestion with [Accept] / [Edit] buttons
  - [ ] `st.expander("Show examples ▼")` — calls `GET /examples/{dimension_id}` inline
  - [ ] [Skip] button — sets score to `not_applicable`
  - [ ] [Flag for help] button — calls `POST /reviews/{id}/flag-for-help`
- [ ] Review timer in bottom corner (st.session_state timer, records review_time_sec)
- [ ] Unscored dimension warning bar at bottom
- [ ] [Submit Review] button — calls `POST /reviews/{id}/submit`

**Session state:**
- [ ] `st.session_state.current_review_id`
- [ ] `st.session_state.scores` — dict of dimension_id → score
- [ ] `st.session_state.review_start_time`

---

## Day 4 — GitHub Webhook + Submission Ingestion

### Webhook Router (`api/routers/webhooks.py`)
- [ ] `POST /webhooks/github` — receive GitHub push event
- [ ] Validate HMAC signature using `GITHUB_WEBHOOK_SECRET`
- [ ] Parse payload: extract repo URL, commit SHA, pusher username
- [ ] Look up student by github_username in users table
- [ ] Create submission record with status=submitted
- [ ] Trigger async: `detect-stack` call to LLM service
- [ ] Return 200 immediately (async processing)

### GitHub App / Webhook Setup
- [ ] Configure GitHub webhook on student org repos (or per-repo)
- [ ] Point to `https://{render-url}/webhooks/github`
- [ ] Set secret, select push events only

---

## Day 5 — Student Feedback View + Discord Notification (P0)

### Notification Service (`api/services/notification_service.py`)
- [ ] `send_feedback_notification(student_discord_id, review_id, feedback_url)` — send Discord DM with feedback link
- [ ] `create_feedback_thread(channel_id, student_discord_id, review_id)` — create Discord thread for Q&A

### Discord Bot (`discord_bot/bot.py`)
- [ ] Bot setup with `discord.py`
- [ ] `on_ready` event — confirm bot is connected
- [ ] `send_dm(user_id, message)` helper
- [ ] Called by notification_service after review submission

### Notification Trigger (add to reviews router)
- [ ] After `POST /reviews/{id}/submit` → call notification_service
- [ ] Build feedback URL: `https://{streamlit-url}/Feedback?review_id={id}`
- [ ] Send Discord DM to student

### Student Feedback View (`pages/3_Feedback.py`)
- [ ] No auth required (URL-based access via Discord link) — OR student login
- [ ] Parse `review_id` from query params
- [ ] Load review scores via `GET /reviews/{id}/scores`
- [ ] **"What to do next" section:** action items sorted by severity (red first, then yellow)
- [ ] **Detailed review section:** per-dimension cards with score + comment + action item
- [ ] Green dimensions: show positive reinforcement, no action item
- [ ] Red dimensions: show comment + action item with → arrow prefix
- [ ] Yellow dimensions: show comment + action item
- [ ] "Have questions? Reply in your Discord thread." link at bottom
- [ ] Read-only — no interactive elements
