"""
FeedbackOS — Streamlit multi-page app entry point.

Handles authentication and role-based routing.

Run with:
    streamlit run app.py
"""

import os
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

# Support both os.environ (local / Render) and st.secrets (Streamlit Cloud)
def _secret(key: str, default: str = "") -> str:
    try:
        return st.secrets[key]
    except Exception:
        return os.environ.get(key, default)

SUPABASE_URL = _secret("SUPABASE_URL")
SUPABASE_KEY = _secret("SUPABASE_KEY")

# ---------------------------------------------------------------------------
# Page config (must be the first Streamlit call)
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="FeedbackOS — 100xEngineers",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Supabase auth helpers
# ---------------------------------------------------------------------------


def _get_supabase_client():
    """Return a Supabase client using the anon key."""
    try:
        from supabase import create_client
        return create_client(SUPABASE_URL, SUPABASE_KEY)
    except Exception as exc:
        st.error(f"Could not connect to Supabase: {exc}")
        return None


def _login(email: str, password: str) -> bool:
    """
    Attempt to sign in via Supabase auth.

    On success, stores user data + role in st.session_state and returns True.
    On failure, shows an error message and returns False.
    """
    client = _get_supabase_client()
    if not client:
        return False

    try:
        auth_resp = client.auth.sign_in_with_password(
            {"email": email, "password": password}
        )
        supabase_user = auth_resp.user
        if not supabase_user:
            st.error("Invalid email or password.")
            return False

        # Fetch extended profile (role, name, etc.) from the users table
        profile_resp = (
            client.table("users")
            .select("*")
            .eq("email", email)
            .maybe_single()
            .execute()
        )
        profile = profile_resp.data or {}

        st.session_state["user"] = {
            "id": str(supabase_user.id),
            "email": email,
            "name": profile.get("name", email.split("@")[0]),
            "role": profile.get("role", "student"),
            "discord_id": profile.get("discord_id"),
            "cohort_id": profile.get("cohort_id"),
        }
        st.session_state["token"] = auth_resp.session.access_token if auth_resp.session else ""
        st.session_state["supabase_client"] = client
        return True

    except Exception as exc:
        error_msg = str(exc)
        if "Invalid login credentials" in error_msg:
            st.error("Invalid email or password.")
        else:
            st.error(f"Login failed: {error_msg}")
        return False


def _logout() -> None:
    """Clear session state and rerun to show login screen."""
    client = st.session_state.get("supabase_client")
    if client:
        try:
            client.auth.sign_out()
        except Exception:
            pass

    for key in ["user", "token", "supabase_client", "selected_submission_id"]:
        st.session_state.pop(key, None)
    st.rerun()


# ---------------------------------------------------------------------------
# Sidebar — logout button (shown when logged in)
# ---------------------------------------------------------------------------

user = st.session_state.get("user")

if user:
    with st.sidebar:
        st.markdown(f"**{user['name']}**")
        st.caption(f"Role: {user['role'].upper()}")
        st.divider()
        if st.button("Logout", use_container_width=True):
            _logout()

# ---------------------------------------------------------------------------
# Login form (shown when NOT logged in)
# ---------------------------------------------------------------------------

if not user:
    st.title("FeedbackOS")
    st.subheader("100xEngineers Capstone Review Platform")
    st.divider()

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("### Sign in")
        with st.form("login_form"):
            email = st.text_input("Email", placeholder="you@100xengineers.com")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Sign In", use_container_width=True)

        if submitted:
            if not email or not password:
                st.warning("Please enter both email and password.")
            elif not SUPABASE_URL or not SUPABASE_KEY:
                st.error(
                    "Supabase is not configured. "
                    "Set SUPABASE_URL and SUPABASE_KEY in your .env file."
                )
            else:
                with st.spinner("Signing in..."):
                    if _login(email, password):
                        st.success("Logged in!")
                        st.rerun()

    st.stop()  # Do not render anything else for unauthenticated users

# ---------------------------------------------------------------------------
# Role-based landing page redirect hint
# ---------------------------------------------------------------------------

role = user.get("role", "student")
name = user.get("name", "")

st.title(f"Welcome back, {name}!")
st.write("Use the sidebar to navigate.")

if role == "ta":
    st.info("Head to **Review Queue** to start reviewing submissions.")
    st.page_link("pages/1_Review_Queue.py", label="Go to Review Queue", icon="📋")
elif role == "instructor":
    st.info("Head to **Instructor Dashboard** for cohort analytics.")
    st.page_link("pages/7_Instructor.py", label="Go to Instructor Dashboard", icon="📊")
else:
    st.info("Check your **Feedback** when your review is ready.")
    st.page_link("pages/3_Feedback.py", label="View My Feedback", icon="📝")
