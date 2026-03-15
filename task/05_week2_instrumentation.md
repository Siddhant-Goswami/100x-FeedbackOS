# Instrumentation + Observability

**Covers Days 9-10. These tasks can run in parallel with analytics dashboard work.**

---

## What We're Measuring

| Metric | How measured | Where stored |
|--------|-------------|--------------|
| Review time | Timer in Streamlit session state | `reviews.review_time_sec` |
| Comprehension rate | Commit tracking (did student edit flagged files?) | `comprehension_events.addressed` |
| TA adoption rate | Count of reviews via system vs expected | Derived from `reviews` table |
| Rubric consistency | Score variance per dimension across TAs | Derived query on `review_scores` |
| Dialogue/follow-up count | Discord thread capture | `dialogue_logs` |
| Action item source | TA-written vs AI-accepted vs AI-edited | `review_scores.action_item_source` |

---

## Tasks

### Review Timer (already in Day 3 — verify)
- [ ] `st.session_state.review_start_time` set on page load
- [ ] `review_time_sec` calculated on submit: `time.time() - start_time`
- [ ] Stored in `reviews` table on submit

### Dialogue Logging
- [ ] `POST /dialogue` endpoint implemented (Day 9)
- [ ] Discord bot captures all messages in feedback threads
- [ ] author_role correctly tagged (student vs ta based on Discord role)
- [ ] review_id correctly parsed from thread metadata

### Comprehension Event Logging
- [ ] `scripts/track_commits.py` cron job implemented (Day 9)
- [ ] Correctly matches files_changed to action items (fuzzy match acceptable for v1)
- [ ] `comprehension_events` records written with `addressed=true/false`
- [ ] `hours_after_feedback` calculated from `reviews.delivered_at`

### GitHub Actions Cron Setup
- [ ] Create `.github/workflows/track_commits.yml`
  ```yaml
  on:
    schedule:
      - cron: '0 6 * * *'  # daily at 6am UTC
  ```
- [ ] Workflow: checkout repo → install deps → run `scripts/track_commits.py`
- [ ] Env vars from GitHub Secrets: `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `GITHUB_TOKEN`

### Action Item Source Tracking
- [ ] When TA clicks [Accept] on AI suggestion → `action_item_source = ai_suggested_accepted`
- [ ] When TA clicks [Edit] and submits → `action_item_source = ai_suggested_edited`
- [ ] When TA types from scratch → `action_item_source = ta_written`
- [ ] Store in `review_scores.action_item_source`

### Analytics Derived Queries
- [ ] `rubric_consistency_score`: for each dimension, calculate stddev of score distribution across TAs — normalize to 0-100%
- [ ] `ta_adoption_rate`: TAs who have submitted ≥1 review this cohort / total TAs in cohort
- [ ] `comprehension_rate`: reviews where ≥1 red/yellow was `addressed=true` / total reviews delivered
- [ ] `avg_followup_questions`: count of `dialogue_logs` where `author_role=student` / review count

---

## Observability Notes

- No external monitoring needed for v1 (Streamlit Cloud + Render have basic metrics)
- Render dashboard shows API latency, error rates
- Supabase dashboard shows query volume + slow queries
- Log all Claude API calls with token counts in application logs (not in DB — too noisy)
