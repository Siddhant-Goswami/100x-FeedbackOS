# Backlog + Phase 2

---

## Phase 2 Ideas (post-MVP)

### Full AI Review Generation
- [ ] Claude generates a complete first-draft review (all dimensions scored + commented)
- [ ] TA reviews, edits, and approves the AI draft
- [ ] Track: what % of AI suggestions are accepted unchanged vs edited

### Rubric Admin Screen (P2)
- [ ] Instructor UI to create/edit rubric dimensions
- [ ] Create new overlays for new tech stacks
- [ ] Activate/deactivate dimensions per cohort
- [ ] Currently: rubrics are seeded via JSON + scripts

### Student Resubmission Flow
- [ ] Student can mark action items as "done" in feedback view
- [ ] Triggers TA notification for re-review
- [ ] Track revision cycles per student

### TA Onboarding Flow
- [ ] Calibration exercise: score 3 example submissions before going live
- [ ] See "correct" scores and reasoning after
- [ ] Reduces cold-start inconsistency

### Rubric Version History
- [ ] Track changes to rubric dimensions over time
- [ ] Old reviews linked to rubric version used
- [ ] Diff view for instructor

### Discord Embed Feedback
- [ ] Render student feedback as Discord embed (not just DM link)
- [ ] Student can react with ✅ on each action item as they complete it
- [ ] Reactions captured as comprehension signals

---

## Known Tech Debt (log as you go)

- None yet

---

## Project File Structure (reference)

```
feedbackos/
├── .env.example
├── .gitignore
├── requirements.txt
├── README.md
├── app.py                          # Streamlit entry point + auth
├── pages/
│   ├── 1_Review_Queue.py
│   ├── 2_Review.py
│   ├── 3_Feedback.py
│   ├── 4_Calibration.py
│   ├── 5_Examples.py
│   ├── 6_TA_Profile.py
│   └── 7_Instructor.py
├── api/
│   ├── main.py
│   ├── config.py
│   ├── routers/
│   │   ├── submissions.py
│   │   ├── reviews.py
│   │   ├── examples.py
│   │   ├── calibration.py
│   │   ├── analytics.py
│   │   ├── webhooks.py
│   │   └── dialogue.py
│   ├── services/
│   │   ├── github_service.py
│   │   ├── llm_service.py
│   │   ├── rubric_service.py
│   │   ├── review_service.py
│   │   ├── notification_service.py
│   │   └── comprehension_service.py
│   └── models/
│       ├── schemas.py
│       └── database.py
├── discord_bot/
│   ├── bot.py
│   └── handlers.py
├── scripts/
│   ├── seed_rubrics.py
│   ├── seed_examples.py
│   └── track_commits.py
├── rubrics/
│   ├── universal_base.json
│   ├── overlay_streamlit_llm.json
│   ├── overlay_gradio_llm.json
│   └── overlay_flask_js_llm.json
├── tests/
│   ├── test_rubric_service.py
│   ├── test_review_service.py
│   └── test_llm_service.py
└── .github/
    └── workflows/
        ├── deploy.yml
        └── track_commits.yml
```

---

## LLM Cost Estimate (reference)

| Use case | Input tokens | Output tokens | Cost per call | Volume estimate |
|----------|-------------|---------------|--------------|-----------------|
| Stack detection | ~2K | ~200 | ~$0.004 | 1 per submission |
| Action item suggestion | ~3K | ~200 | ~$0.01 | ~3 per review |
| Per cohort (750 students) | — | — | ~$22.50 | — |
