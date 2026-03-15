"""
TA Profile page — personal impact metrics for the logged-in TA.
"""

from __future__ import annotations

import os

import httpx
import streamlit as st

def _st_secret(k, d=""):
    try:
        import streamlit as _st
        return _st.secrets[k]
    except Exception:
        import os as _os
        return _os.environ.get(k, d)
FASTAPI_URL = _st_secret("FASTAPI_URL", "http://localhost:8000")

st.set_page_config(page_title="TA Profile — FeedbackOS", layout="wide")

# ---------------------------------------------------------------------------
# Auth check
# ---------------------------------------------------------------------------

user = st.session_state.get("user")
if not user:
    st.warning("Please log in.")
    st.page_link("app.py", label="Go to Login")
    st.stop()

if user.get("role") not in ("ta", "instructor"):
    st.error("This page is only accessible to TAs.")
    st.stop()

ta_id = user["id"]
ta_name = user.get("name", "TA")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def api_get(path: str) -> dict | None:
    try:
        resp = httpx.get(f"{FASTAPI_URL}{path}", timeout=15.0)
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:
        st.error(f"API error: {exc}")
        return None


# ---------------------------------------------------------------------------
# Page
# ---------------------------------------------------------------------------

st.title(f"TA Profile: {ta_name}")
st.divider()

with st.spinner("Loading your impact metrics..."):
    metrics = api_get(f"/analytics/ta/{ta_id}")

if not metrics:
    st.error("Could not load metrics.")
    st.stop()

reviews_submitted = metrics.get("reviews_submitted", 0)
comp_rate = metrics.get("comprehension_rate", 0.0)
cohort_comp_rate = metrics.get("cohort_comprehension_rate", 0.0)
score_dist = metrics.get("score_distribution", {})
impactful = metrics.get("most_impactful_items", [])

# ---------------------------------------------------------------------------
# KPI row
# ---------------------------------------------------------------------------

kpi1, kpi2, kpi3, kpi4 = st.columns(4)

kpi1.metric("Reviews Submitted", reviews_submitted)
kpi2.metric(
    "Your Comprehension Rate",
    f"{comp_rate:.1f}%",
    delta=f"{comp_rate - cohort_comp_rate:+.1f}% vs cohort",
    delta_color="normal",
)
kpi3.metric("Cohort Avg Comprehension", f"{cohort_comp_rate:.1f}%")

total_scores = sum(score_dist.values()) or 1
green_pct = round(score_dist.get("green", 0) / total_scores * 100)
kpi4.metric("Green Rate", f"{green_pct}%", help="% of your scores that are green")

st.divider()

# ---------------------------------------------------------------------------
# Score distribution
# ---------------------------------------------------------------------------

st.subheader("Your Score Distribution")

if score_dist:
    dist_cols = st.columns(len(score_dist))
    icons = {"green": "🟢", "yellow": "🟡", "red": "🔴", "not_applicable": "⚪", "flagged_for_help": "🚩"}
    for i, (score, count) in enumerate(sorted(score_dist.items())):
        pct = round(count / total_scores * 100)
        icon = icons.get(score, "⬜")
        dist_cols[i].metric(f"{icon} {score.replace('_', ' ').title()}", count, delta=f"{pct}%")
else:
    st.info("No scoring data yet.")

st.divider()

# ---------------------------------------------------------------------------
# Most impactful feedback items
# ---------------------------------------------------------------------------

st.subheader("Most Impactful Feedback Items")
st.caption("Action items your students most frequently acted on after receiving feedback.")

if impactful:
    for i, item in enumerate(impactful, 1):
        action = item.get("action_item", "")
        count = item.get("count", 0)
        with st.container(border=True):
            c1, c2 = st.columns([5, 1])
            c1.write(f"**{i}.** {action}")
            c2.metric("Times acted on", count)
else:
    st.info(
        "No comprehension data yet. This will populate as students make commits "
        "after receiving feedback."
    )

st.divider()

# ---------------------------------------------------------------------------
# Comprehension rate explanation
# ---------------------------------------------------------------------------

with st.expander("What is Comprehension Rate?"):
    st.write(
        """
        **Comprehension Rate** measures how often students act on the specific feedback
        you give them.

        It's calculated by tracking student GitHub commits after a review is delivered.
        If a commit modifies files mentioned in your red/yellow feedback, it counts as
        the student having addressed that feedback.

        **Higher = more actionable feedback** that students can immediately apply.
        If your rate is low, consider making action items more specific and concrete.
        """
    )
