# Days 6-7 — Tests + Example Library Seed

**Goal:** Test coverage for core services + seed example feedback library.

---

## Day 6 — Tests

### Rubric Service Tests (`tests/test_rubric_service.py`)
- [ ] `test_load_universal_rubric` — loads base JSON correctly
- [ ] `test_detect_overlay_streamlit` — maps Streamlit stack to correct overlay
- [ ] `test_detect_overlay_gradio` — maps Gradio stack to correct overlay
- [ ] `test_detect_overlay_unknown` — falls back to universal only
- [ ] `test_merge_rubric` — merged result has correct dimensions, sorted by sort_order
- [ ] `test_merge_rubric_no_overlay` — works when no overlay exists

### Review Service Tests (`tests/test_review_service.py`)
- [ ] `test_create_review` — creates draft record in DB
- [ ] `test_update_score_new` — inserts new review_score
- [ ] `test_update_score_existing` — upserts (doesn't duplicate)
- [ ] `test_check_completeness_complete` — returns empty list when all required dims scored
- [ ] `test_check_completeness_missing` — returns list of unscored required dims
- [ ] `test_submit_review_valid` — sets status=submitted, records submitted_at
- [ ] `test_submit_review_incomplete` — raises error when required dims unscored

### LLM Service Tests (`tests/test_llm_service.py`)
- [ ] Mock Claude API client (don't call real API in tests)
- [ ] `test_detect_stack_returns_json` — parses Claude response into expected schema
- [ ] `test_detect_stack_handles_malformed_response` — graceful fallback when Claude returns non-JSON
- [ ] `test_suggest_action_item_returns_json` — parses suggestion response
- [ ] `test_suggest_action_item_token_budget` — input stays under ~3K tokens

### Webhook Tests
- [ ] `test_webhook_valid_signature` — accepts valid HMAC signature
- [ ] `test_webhook_invalid_signature` — rejects invalid signature with 401
- [ ] `test_webhook_creates_submission` — valid push event creates submission record

---

## Day 7 — Example Library Seed

### Examples Router (`api/routers/examples.py`)
- [ ] `GET /examples/{dimension_id}` — list examples for dimension, optional `?stack_filter={stack}`
- [ ] Order by quality_score desc

### Example Seeding Script (`scripts/seed_examples.py`)
- [ ] Write 2-3 example feedback entries per dimension × 3 stacks (Streamlit, Gradio, Flask+JS)
- [ ] Minimum: 14 dimensions × 2 examples = 28 example entries

**Example entries to write (per dimension):**

**Code Quality:**
- [ ] 🟢 example: clean separation of concerns, good naming
- [ ] 🔴 example: 200-line main function, no separation

**Error Handling:**
- [ ] 🔴 example: no try/except around API call (Streamlit + Claude)
- [ ] 🟡 example: catches errors but swallows them silently

**Architecture:**
- [ ] 🟢 example: api.py + app.py separation
- [ ] 🔴 example: everything in one file

**LLM Usage:**
- [ ] 🟡 example: no system message, bare user prompt
- [ ] 🔴 example: API key hardcoded in prompt string

**Deployment:**
- [ ] 🟢 example: proper .env.example, deployed and live
- [ ] 🔴 example: app not deployed, just local

**Documentation:**
- [ ] 🟡 example: no README, no setup instructions
- [ ] 🟢 example: clear README with setup + demo

**Prompt Engineering:**
- [ ] 🟡 example: working but no output format specified
- [ ] 🔴 example: prompt leaks system instructions to user

- [ ] Run `python scripts/seed_examples.py` — verify in Supabase
- [ ] Test `GET /examples/1` (Code Quality dimension) — confirm returns seeded examples
