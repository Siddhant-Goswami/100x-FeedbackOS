"""
Calibration page — TA view.

Score distribution table per dimension and individual "my scores vs peers"
comparison to help TAs stay consistent with each other.
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

st.set_page_config(page_title="Calibration — FeedbackOS", layout="wide")

# ---------------------------------------------------------------------------
# Auth check
# ---------------------------------------------------------------------------

user = st.session_state.get("user")
if not user:
    st.warning("Please log in.")
    st.page_link("app.py", label="Go to Login")
    st.stop()

if user.get("role") not in ("ta", "instructor"):
    st.error("Calibration is only available to TAs and instructors.")
    st.stop()

ta_id = user["id"]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def api_get(path: str, params: dict | None = None) -> dict | list | None:
    try:
        resp = httpx.get(f"{FASTAPI_URL}{path}", params=params, timeout=15.0)
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:
        st.error(f"API error: {exc}")
        return None


def _score_bar(dist: dict) -> str:
    """Simple ASCII-style bar as HTML colored spans."""
    total = sum(dist.values()) or 1
    colors = {"green": "#10B981", "yellow": "#F59E0B", "red": "#EF4444"}
    parts = []
    for key in ("green", "yellow", "red"):
        count = dist.get(key, 0)
        pct = int(count / total * 100)
        if pct > 0:
            color = colors.get(key, "#64748B")
            parts.append(
                f'<span style="background:{color};display:inline-block;'
                f'width:{pct}%;height:16px;border-radius:3px"></span>'
            )
    return "".join(parts)


# ---------------------------------------------------------------------------
# Assignment selector (placeholder: use assignment_id from URL or dropdown)
# ---------------------------------------------------------------------------

st.title("Calibration")
st.caption("Compare your scoring patterns with the rest of the TA cohort.")

# TODO: populate from API
assignment_id = st.text_input(
    "Assignment ID",
    placeholder="Paste an assignment UUID to load calibration data",
)

if not assignment_id:
    st.info("Enter an assignment ID above to view calibration data.")
    st.stop()

# ---------------------------------------------------------------------------
# Load calibration data
# ---------------------------------------------------------------------------

with st.spinner("Loading calibration data..."):
    calib = api_get(f"/calibration/{assignment_id}")
    my_vs = api_get(
        f"/calibration/{assignment_id}/my-vs-peers", params={"ta_id": ta_id}
    )

if not calib:
    st.error("Could not load calibration data.")
    st.stop()

dimensions = calib.get("dimensions", [])
total_reviews = calib.get("total_reviews", 0)

st.caption(f"Based on {total_reviews} scored review(s) for this assignment.")
st.divider()

# ---------------------------------------------------------------------------
# Score distribution table
# ---------------------------------------------------------------------------

st.subheader("Score Distribution — All TAs")

if not dimensions:
    st.info("No scoring data yet for this assignment.")
else:
    for dim in dimensions:
        dim_name = dim.get("name", "Unknown")
        dist = dim.get("distribution", {})
        themes = dim.get("themes", [])

        total = sum(dist.values()) or 1
        green_pct = round(dist.get("green", 0) / total * 100)
        yellow_pct = round(dist.get("yellow", 0) / total * 100)
        red_pct = round(dist.get("red", 0) / total * 100)

        with st.container(border=True):
            title_col, stats_col = st.columns([2, 3])
            with title_col:
                st.markdown(f"**{dim_name}**")
                if themes:
                    with st.expander("Common themes"):
                        for t in themes:
                            st.caption(f"• {t}")

            with stats_col:
                bar_html = _score_bar(dist)
                st.markdown(bar_html, unsafe_allow_html=True)
                stat_c1, stat_c2, stat_c3 = st.columns(3)
                stat_c1.metric("🟢 Green", f"{green_pct}%")
                stat_c2.metric("🟡 Yellow", f"{yellow_pct}%")
                stat_c3.metric("🔴 Red", f"{red_pct}%")

st.divider()

# ---------------------------------------------------------------------------
# My scores vs peers
# ---------------------------------------------------------------------------

st.subheader("My Scores vs Cohort Average")

if not my_vs:
    st.warning("Could not load comparison data.")
else:
    peer_dims = my_vs.get("dimensions", [])
    if not peer_dims:
        st.info("No comparison data yet.")
    else:
        for dim in peer_dims:
            dim_name = dim.get("name", "Unknown")
            my_dist = dim.get("my_distribution", {})
            cohort_dist = dim.get("cohort_distribution", {})

            with st.expander(f"**{dim_name}**"):
                my_col, cohort_col = st.columns(2)
                with my_col:
                    st.markdown("**My scores**")
                    for score_key in ("green", "yellow", "red"):
                        count = my_dist.get(score_key, 0)
                        icon = {"green": "🟢", "yellow": "🟡", "red": "🔴"}[score_key]
                        st.write(f"{icon} {score_key.title()}: **{count}**")

                with cohort_col:
                    st.markdown("**Cohort average**")
                    for score_key in ("green", "yellow", "red"):
                        avg = cohort_dist.get(score_key, 0)
                        icon = {"green": "🟢", "yellow": "🟡", "red": "🔴"}[score_key]
                        st.write(f"{icon} {score_key.title()}: **{avg:.1f} avg**")
