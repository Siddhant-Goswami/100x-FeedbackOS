# Week 2 — P1 Screens: Calibration, Examples, Analytics

**Days 8-10. Goal:** TAs can calibrate against peers, browse example library, see their impact metrics. Instructor sees aggregate data.

---

## Day 8 — Calibration View + Example Library (P1)

### Calibration Router (`api/routers/calibration.py`)
- [ ] `GET /calibration/{assignment_id}` — return anonymized peer scores
  - Query params: `?dimension_id={id}` (optional filter), `?stack_filter={stack}` (optional)
  - Response: per-dimension score distribution (green/yellow/red/skipped %), common feedback themes
  - Anonymized: no TA names in response
- [ ] `GET /calibration/{assignment_id}/my-vs-peers` — compare current TA's scores vs cohort avg
  - Auth required — uses `ta_id` from session
  - Response: dimensions where TA scores significantly different from peers + insight text

### Calibration View (`pages/4_Calibration.py`)
- [ ] Auth check (TA role)
- [ ] Load calibration data via `GET /calibration/{assignment_id}`
- [ ] Dimension score distribution table: dimension name | 🟢% | 🟡% | 🔴% | Skipped%
- [ ] "Your scores vs peers" section — highlight dimensions where TA is an outlier
- [ ] Common feedback themes per dimension (top 3 text snippets)
- [ ] Filter: dimension dropdown + stack filter dropdown

### Example Library Router (add to `api/routers/examples.py`)
- [ ] Already done: `GET /examples/{dimension_id}`
- [ ] Add `GET /examples` — list all, grouped by dimension (for standalone browse)
- [ ] Add "acted on" badge data: join with comprehension_events to show which examples led to student action

### Example Library Screen (`pages/5_Examples.py`)
- [ ] Dimension dropdown filter
- [ ] Stack filter dropdown (All / Streamlit / Gradio / Flask+JS)
- [ ] Example cards showing: score, comment, action item, stack context, "Student acted on this ✅" badge
- [ ] Sorted by quality_score desc
- [ ] Note: also available inline via `st.expander()` on Review Screen (already built in Day 3)

---

## Day 9 — Dialogue Capture + Comprehension Tracking (Instrumentation)

### Dialogue Router (`api/routers/dialogue.py`)
- [ ] `POST /dialogue` — log a dialogue message (review_id, dimension_id, message_text, author_role, discord_message_id)

### Dialogue Capture in Discord Bot (`discord_bot/handlers.py`)
- [ ] `on_message` handler — detect messages in feedback threads
- [ ] Parse thread metadata: extract review_id from thread name/topic
- [ ] Call `POST /dialogue` for each message, tagging author_role (student or ta)
- [ ] Only capture in feedback threads (not general channels)

### Comprehension Service (`api/services/comprehension_service.py`)
- [ ] `track_commit(student_id, commit_sha, commit_timestamp, files_changed)` — check if changed files correspond to feedback action items
- [ ] `match_commit_to_feedback(files_changed, review_id)` — fuzzy match: did student edit the files mentioned in feedback?
- [ ] `calculate_comprehension_rate(ta_id)` — % of student submissions where at least 1 red/yellow action item was addressed
- [ ] `log_comprehension_event(review_id, review_score_id, commit_sha, addressed)` — write to comprehension_events

### Commit Tracking Script (`scripts/track_commits.py`)
- [ ] Cron job (GitHub Actions, every 24h)
- [ ] For each review delivered in last 7 days:
  - [ ] Check student's GitHub repo for new commits after feedback delivery
  - [ ] If commits found: call `match_commit_to_feedback()`
  - [ ] Write comprehension_events records
- [ ] GitHub Actions workflow: `.github/workflows/track_commits.yml` — runs daily

---

## Day 10 — Analytics Dashboards (P1)

### Analytics Router (`api/routers/analytics.py`)
- [ ] `GET /analytics/instructor` — aggregate cohort metrics
  - Query params: `?cohort_id={id}&date_from={date}&date_to={date}`
  - Response:
    - comprehension_rate (% students who addressed red/yellow feedback)
    - ta_adoption_rate (% TAs using system vs manual)
    - rubric_consistency_score (score variance across TAs for same dimension type)
    - dimensions_needing_attention (high follow-up Q count, high skip rate)
    - most_common_issues (top issues across all submissions)
- [ ] `GET /analytics/ta/{ta_id}` — TA personal impact metrics
  - Response:
    - reviews_completed, avg_review_time_minutes
    - comprehension_rate (their students vs cohort avg)
    - avg_followup_questions (their students vs cohort avg)
    - most_impactful_feedback (top action items that led to student improvement)

### TA Profile Screen (`pages/6_TA_Profile.py`)
- [ ] Auth check (TA role — only see own data)
- [ ] Load via `GET /analytics/ta/{ta_id}`
- [ ] Metrics: reviews completed, avg review time
- [ ] "Your Feedback Impact" card: comprehension rate vs cohort avg, avg follow-up Qs vs cohort avg
- [ ] Insight text: "Your feedback tends to be clear — students need less clarification"
- [ ] "Most Impactful Feedback" section: top action items with count of students who improved
- [ ] Framing: personal growth tool, not ranking/surveillance

### Instructor Dashboard (`pages/7_Instructor.py`)
- [ ] Auth check (instructor role only)
- [ ] Load via `GET /analytics/instructor`
- [ ] Header: cohort name, review count / total students
- [ ] 3 KPI metric cards: Comprehension Rate | TA Adoption Rate | Rubric Consistency
  - Each shows value + target + green/yellow/red status
- [ ] "Dimensions Needing Attention" section — actionable insights
- [ ] "Most Common Issues" ranked list (top 5 across all submissions)
