"""
Instructor dashboard — aggregate cohort metrics.

Role-gated: only accessible to users with role=instructor.
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

st.set_page_config(page_title="Instructor Dashboard — FeedbackOS", layout="wide")

# ---------------------------------------------------------------------------
# Auth + role check
# ---------------------------------------------------------------------------

user = st.session_state.get("user")
if not user:
    st.warning("Please log in.")
    st.page_link("app.py", label="Go to Login")
    st.stop()

if user.get("role") != "instructor":
    st.error("This page is only accessible to instructors.")
    st.stop()

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def api_get(path: str) -> dict | None:
    try:
        resp = httpx.get(f"{FASTAPI_URL}{path}", timeout=20.0)
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:
        st.error(f"API error: {exc}")
        return None


# ---------------------------------------------------------------------------
# Page
# ---------------------------------------------------------------------------

st.title("Instructor Dashboard")
st.caption("Cohort-level feedback quality metrics.")
st.divider()

with st.spinner("Loading cohort metrics..."):
    data = api_get("/analytics/instructor")

if not data:
    st.error("Could not load instructor metrics.")
    st.stop()

comp_rate = data.get("comprehension_rate", 0.0)
ta_adoption = data.get("ta_adoption_rate", 0.0)
rubric_consistency = data.get("rubric_consistency", 0.0)
attention_dims = data.get("dimensions_needing_attention", [])
top_issues = data.get("top_issues", [])
total_reviews = data.get("total_reviews", 0)

# ---------------------------------------------------------------------------
# KPI cards
# ---------------------------------------------------------------------------

st.subheader("Key Performance Indicators")

kpi1, kpi2, kpi3, kpi4 = st.columns(4)

kpi1.metric(
    "Comprehension Rate",
    f"{comp_rate:.1f}%",
    help="% of feedback items students acted on (via commit tracking)",
)
kpi2.metric(
    "TA Adoption Rate",
    f"{ta_adoption:.1f}%",
    help="% of TAs who have submitted at least one review",
)
kpi3.metric(
    "Rubric Consistency",
    f"{rubric_consistency:.1f}%",
    help="% agreement across TAs on same-dimension scores (higher = more consistent)",
)
kpi4.metric(
    "Total Reviews",
    total_reviews,
)

# Traffic light for each KPI
def _traffic_light(value: float, thresholds: tuple[float, float]) -> str:
    if value >= thresholds[1]:
        return "🟢 On track"
    if value >= thresholds[0]:
        return "🟡 Needs attention"
    return "🔴 Critical"

st.caption(
    f"Comprehension: {_traffic_light(comp_rate, (40, 70))} · "
    f"TA Adoption: {_traffic_light(ta_adoption, (60, 90))} · "
    f"Consistency: {_traffic_light(rubric_consistency, (60, 80))}"
)

st.divider()

# ---------------------------------------------------------------------------
# Dimensions needing attention
# ---------------------------------------------------------------------------

col_left, col_right = st.columns(2)

with col_left:
    st.subheader("Dimensions Needing Attention")
    st.caption("Ranked by red/yellow rate — highest concern first.")

    if attention_dims:
        for dim in attention_dims:
            name = dim.get("name", "Unknown")
            rate = dim.get("red_yellow_rate", 0)
            color = "#EF4444" if rate > 60 else "#F59E0B" if rate > 30 else "#10B981"
            st.markdown(
                f"""
                <div style="border-left:4px solid {color};padding:8px 12px;margin-bottom:8px;
                            background:#F8FAFC;border-radius:4px">
                    <strong>{name}</strong><br>
                    <span style="color:{color}">{rate:.0f}% red/yellow scores</span>
                </div>
                """,
                unsafe_allow_html=True,
            )
    else:
        st.info("No dimension data available yet.")

# ---------------------------------------------------------------------------
# Top issues
# ---------------------------------------------------------------------------

with col_right:
    st.subheader("Most Common Issues")
    st.caption("Top action items given across all reviews.")

    if top_issues:
        for i, issue in enumerate(top_issues, 1):
            action = issue.get("action_item", "")
            count = issue.get("count", 0)
            with st.container(border=True):
                c1, c2 = st.columns([5, 1])
                c1.write(f"**{i}.** {action[:100]}{'...' if len(action) > 100 else ''}")
                c2.metric("Count", count)
    else:
        st.info("No action item data available yet.")

st.divider()

# ---------------------------------------------------------------------------
# Guidance section
# ---------------------------------------------------------------------------

with st.expander("How to interpret these metrics"):
    st.markdown(
        """
        ### Comprehension Rate
        Tracks how often students commit changes to files mentioned in red/yellow feedback
        within 7 days of delivery. **Target: >70%.**

        Low rates suggest:
        - Action items are too vague (fix with the Examples library)
        - Students need more structured follow-up

        ### TA Adoption Rate
        % of TAs who have submitted at least one review using FeedbackOS.
        **Target: 100%.** If low, run a TA onboarding session.

        ### Rubric Consistency
        Measures whether TAs agree on the same score for similar code.
        **Target: >80%.** Use the Calibration page to run alignment sessions.
        """
    )
