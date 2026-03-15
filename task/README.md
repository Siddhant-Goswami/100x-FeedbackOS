# FeedbackOS — Task Board

Rubric-based feedback standardization system for 100xEngineers mid-capstone reviews.

## Task Files

| File | Phase | Status |
|------|-------|--------|
| [00_quickstart.md](00_quickstart.md) | Hour Zero Checklist | TODO |
| [01_day1_foundation.md](01_day1_foundation.md) | Day 1 — Project scaffold + DB + API skeleton | TODO |
| [02_week1_core.md](02_week1_core.md) | Days 2-5 — Core review flow (P0 screens) | TODO |
| [03_week1_tests.md](03_week1_tests.md) | Days 6-7 — Tests + example seeding | TODO |
| [04_week2_features.md](04_week2_features.md) | Days 8-10 — P1 screens (calibration, examples, analytics) | TODO |
| [05_week2_instrumentation.md](05_week2_instrumentation.md) | Days 9-10 — Dialogue capture + comprehension tracking | TODO |
| [06_deployment.md](06_deployment.md) | Deployment + CI/CD | TODO |
| [07_backlog.md](07_backlog.md) | Backlog / Phase 2 ideas | TODO |

## Architecture Summary

```
Interface:    Streamlit (TA Dashboard + Analytics)  |  Discord Bot (Student notifications)
Logic:        FastAPI backend
Intelligence: Claude API (stack detection + action item suggestions)
Data:         Supabase (PostgreSQL)  |  GitHub API  |  Discord API
Deploy:       Streamlit Cloud (frontend)  |  Render (FastAPI)  |  GitHub Actions (CI/CD)
```

## Roles
- **TA** — Reviews submissions via Streamlit dashboard
- **Student** — Receives feedback via Discord + reads structured feedback view
- **Instructor** — Sees aggregate analytics dashboard
