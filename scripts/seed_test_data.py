"""
Seed test data for local development.

Creates:
  - 1 cohort ("Cohort 12 — March 2026")
  - 1 assignment ("Mid-Capstone Project")
  - 3 test users: 1 instructor, 2 TAs, 3 students
  - 3 sample submissions (one per student)

Run AFTER seed_rubrics.py.

Usage:
    python scripts/seed_test_data.py
"""

from __future__ import annotations

import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from api.models.database import get_service_client

# ---------------------------------------------------------------------------
# Stable test IDs — fixed so re-running is idempotent
# ---------------------------------------------------------------------------

COHORT_ID     = "c0000000-0000-0000-0000-000000000001"
ASSIGNMENT_ID = "a0000000-0000-0000-0000-000000000001"
RUBRIC_ID     = "e0000000-0000-0000-0000-000000000001"  # from universal_base.json

INSTRUCTOR_ID = "f0000000-0000-0000-0000-000000000001"
TA1_ID        = "f0000000-0000-0000-0000-000000000002"
TA2_ID        = "f0000000-0000-0000-0000-000000000003"
STUDENT1_ID   = "f0000000-0000-0000-0000-000000000004"
STUDENT2_ID   = "f0000000-0000-0000-0000-000000000005"
STUDENT3_ID   = "f0000000-0000-0000-0000-000000000006"

SUB1_ID = "b0000000-0000-0000-0000-000000000001"
SUB2_ID = "b0000000-0000-0000-0000-000000000002"
SUB3_ID = "b0000000-0000-0000-0000-000000000003"


def upsert(client, table: str, payload: dict, conflict_col: str = "id") -> bool:
    resp = client.table(table).upsert(payload, on_conflict=conflict_col).execute()
    ok = bool(resp.data)
    status = "OK" if ok else "WARN (no data returned)"
    print(f"  [{status}] {table}: {payload.get('name') or payload.get('email') or payload.get('id')}")
    return ok


def seed() -> None:
    client = get_service_client()

    print("\n── Cohort ──")
    upsert(client, "cohorts", {
        "id": COHORT_ID,
        "name": "Cohort 12 — March 2026",
        "start_date": "2026-03-01",
        "end_date": "2026-04-30",
    })

    print("\n── Assignment ──")
    upsert(client, "assignments", {
        "id": ASSIGNMENT_ID,
        "cohort_id": COHORT_ID,
        "title": "Mid-Capstone Project",
        "description": "Build an AI-powered application using Claude API, deployed publicly.",
        "rubric_id": RUBRIC_ID,
        "due_date": "2026-03-25T23:59:00Z",
    })

    print("\n── Users ──")
    users = [
        {
            "id": INSTRUCTOR_ID,
            "email": "instructor@100x.test",
            "name": "Siddhant (Instructor)",
            "role": "instructor",
            "cohort_id": COHORT_ID,
            "github_username": "instructor-100x",
            "discord_id": "instructor_discord_001",
        },
        {
            "id": TA1_ID,
            "email": "ta1@100x.test",
            "name": "Rohan (TA)",
            "role": "ta",
            "cohort_id": COHORT_ID,
            "github_username": "rohan-ta",
            "discord_id": "ta1_discord_001",
        },
        {
            "id": TA2_ID,
            "email": "ta2@100x.test",
            "name": "Ananya (TA)",
            "role": "ta",
            "cohort_id": COHORT_ID,
            "github_username": "ananya-ta",
            "discord_id": "ta2_discord_001",
        },
        {
            "id": STUDENT1_ID,
            "email": "priya@100x.test",
            "name": "Priya Sharma",
            "role": "student",
            "cohort_id": COHORT_ID,
            "github_username": "priya-sharma",
            "discord_id": "student1_discord_001",
        },
        {
            "id": STUDENT2_ID,
            "email": "arjun@100x.test",
            "name": "Arjun Mehta",
            "role": "student",
            "cohort_id": COHORT_ID,
            "github_username": "arjun-mehta",
            "discord_id": "student2_discord_001",
        },
        {
            "id": STUDENT3_ID,
            "email": "kavitha@100x.test",
            "name": "Kavitha Rao",
            "role": "student",
            "cohort_id": COHORT_ID,
            "github_username": "kavitha-rao",
            "discord_id": "student3_discord_001",
        },
    ]
    for u in users:
        upsert(client, "users", u)

    print("\n── Submissions ──")
    submissions = [
        {
            "id": SUB1_ID,
            "assignment_id": ASSIGNMENT_ID,
            "student_id": STUDENT1_ID,
            "ta_id": TA1_ID,
            "github_repo_url": "https://github.com/priya-sharma/research-summarizer",
            "commit_sha": "abc1234",
            "status": "submitted",
        },
        {
            "id": SUB2_ID,
            "assignment_id": ASSIGNMENT_ID,
            "student_id": STUDENT2_ID,
            "ta_id": TA1_ID,
            "github_repo_url": "https://github.com/arjun-mehta/legal-faq-chatbot",
            "commit_sha": "def5678",
            "status": "submitted",
            "is_flagged": True,
            "flag_note": "Deployment dimension unclear — Gradio on HF Spaces, not sure if overlay applies",
        },
        {
            "id": SUB3_ID,
            "assignment_id": ASSIGNMENT_ID,
            "student_id": STUDENT3_ID,
            "ta_id": TA2_ID,
            "github_repo_url": "https://github.com/kavitha-rao/workout-generator",
            "commit_sha": "ghi9012",
            "status": "submitted",
        },
    ]
    for s in submissions:
        upsert(client, "submissions", s, conflict_col="github_repo_url,commit_sha")

    print("\n── Detected Stacks ──")
    stacks = [
        {
            "submission_id": SUB1_ID,
            "frontend": "streamlit",
            "backend": "none",
            "llm_api": "anthropic",
            "deployment_platform": "streamlit_cloud",
            "confidence": 0.92,
            "raw_tags": ["supabase"],
        },
        {
            "submission_id": SUB2_ID,
            "frontend": "gradio",
            "backend": "none",
            "llm_api": "openai",
            "deployment_platform": "huggingface",
            "confidence": 0.85,
            "raw_tags": [],
        },
        {
            "submission_id": SUB3_ID,
            "frontend": "streamlit",
            "backend": "fastapi",
            "llm_api": "anthropic",
            "deployment_platform": "render",
            "confidence": 0.88,
            "raw_tags": ["sqlite"],
        },
    ]
    for stack in stacks:
        upsert(client, "detected_stacks", stack, conflict_col="submission_id")

    print("\n── Submission Files (previews) ──")
    files = [
        # Priya's summarizer
        {
            "id": str(uuid.uuid4()),
            "submission_id": SUB1_ID,
            "filepath": "app.py",
            "content_preview": "import streamlit as st\nimport anthropic\n\nst.title('Research Paper Summarizer')\n\nuploaded = st.file_uploader('Upload a PDF or paste text')\n\nif uploaded:\n    text = uploaded.read().decode()\n    client = anthropic.Anthropic()\n    response = client.messages.create(\n        model='claude-haiku-4-5-20251001',\n        max_tokens=1024,\n        messages=[{'role': 'user', 'content': f'Summarize this: {text}'}]\n    )\n    st.write(response.content[0].text)\n# NO ERROR HANDLING\n",
        },
        {
            "id": str(uuid.uuid4()),
            "submission_id": SUB1_ID,
            "filepath": "requirements.txt",
            "content_preview": "streamlit>=1.32.0\nanthropicPy>=0.18.0\n",
        },
        {
            "id": str(uuid.uuid4()),
            "submission_id": SUB1_ID,
            "filepath": "README.md",
            "content_preview": "# Research Paper Summarizer\nAI-powered tool to summarize research papers.\n",
        },
        # Arjun's chatbot
        {
            "id": str(uuid.uuid4()),
            "submission_id": SUB2_ID,
            "filepath": "app.py",
            "content_preview": "import gradio as gr\nimport openai\n\nopenai.api_key = 'sk-HARDCODED_KEY_HERE'  # TODO: fix\n\ndef chat(message, history):\n    response = openai.ChatCompletion.create(\n        model='gpt-4',\n        messages=[{'role': 'user', 'content': message}]\n    )\n    return response.choices[0].message.content\n\ndemo = gr.ChatInterface(chat)\ndemo.launch()\n",
        },
        # Kavitha's workout generator
        {
            "id": str(uuid.uuid4()),
            "submission_id": SUB3_ID,
            "filepath": "app.py",
            "content_preview": "import streamlit as st\nfrom api import generate_workout\n\nst.title('Workout Plan Generator')\n\ngoal = st.selectbox('Goal', ['Lose weight', 'Build muscle', 'Stay fit'])\ndays = st.slider('Days per week', 1, 7, 4)\n\nif st.button('Generate Plan'):\n    try:\n        plan = generate_workout(goal, days)\n        st.markdown(plan)\n    except Exception as e:\n        st.error(f'Could not generate plan: {e}')\n",
        },
        {
            "id": str(uuid.uuid4()),
            "submission_id": SUB3_ID,
            "filepath": "api.py",
            "content_preview": "import anthropic\nimport os\n\nclient = anthropic.Anthropic(api_key=os.environ['ANTHROPIC_API_KEY'])\n\ndef generate_workout(goal: str, days: int) -> str:\n    try:\n        response = client.messages.create(\n            model='claude-haiku-4-5-20251001',\n            max_tokens=1024,\n            system='You are a certified fitness coach. Create structured workout plans.',\n            messages=[{\n                'role': 'user',\n                'content': f'Create a {days}-day/week workout plan for goal: {goal}'\n            }]\n        )\n        return response.content[0].text\n    except anthropic.APIError as e:\n        raise RuntimeError(f'API error: {e}') from e\n",
        },
    ]
    for f in files:
        resp = client.table("submission_files").upsert(f, on_conflict="submission_id,filepath").execute()
        status = "OK" if resp.data else "WARN"
        print(f"  [{status}] submission_files: {f['filepath']} (sub {f['submission_id'][-4:]})")

    print("\n" + "=" * 50)
    print("Test data seeded successfully!")
    print()
    print("Test accounts (no password — create via Supabase Auth dashboard):")
    print("  instructor@100x.test  → role: instructor")
    print("  ta1@100x.test         → role: ta  (Rohan)")
    print("  ta2@100x.test         → role: ta  (Ananya)")
    print("  priya@100x.test       → role: student")
    print()
    print("Next: Create these users in Supabase Auth (Authentication → Users → Invite)")
    print("      The user IDs in auth.users must match the IDs seeded above.")
    print("      OR use the Supabase service key to sign up via the API.")


if __name__ == "__main__":
    seed()
