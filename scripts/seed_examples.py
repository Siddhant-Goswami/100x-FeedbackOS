"""
Seed script: upsert example feedback entries into Supabase.

Usage:
    python scripts/seed_examples.py

Requires SUPABASE_URL and SUPABASE_SERVICE_KEY to be set in .env.
The dimension UUIDs below must match what was seeded by seed_rubrics.py.
"""

from __future__ import annotations

import sys
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from api.models.database import get_service_client


# ---------------------------------------------------------------------------
# Example data
# These dimension IDs must match universal_base.json
# ---------------------------------------------------------------------------

EXAMPLES: list[dict] = [
    # ---- Code Quality ----
    {
        "id": str(uuid4()),
        "dimension_id": "d1000000-0000-0000-0000-000000000001",
        "stack_tag": None,
        "score": "green",
        "comment": "Great separation of concerns — API calls are isolated in a dedicated module, and the Streamlit UI layer only handles display logic.",
        "action_item": None,
        "was_acted_on": True,
    },
    {
        "id": str(uuid4()),
        "dimension_id": "d1000000-0000-0000-0000-000000000001",
        "stack_tag": None,
        "score": "yellow",
        "comment": "Functions are doing too much — the main() function handles both UI rendering and API calls.",
        "action_item": "Refactor main() by extracting a separate `call_llm(prompt)` function and a `render_results(response)` function. Each function should do one thing.",
        "was_acted_on": True,
    },
    {
        "id": str(uuid4()),
        "dimension_id": "d1000000-0000-0000-0000-000000000001",
        "stack_tag": None,
        "score": "red",
        "comment": "All logic is in a single 300-line app.py with no functions. Variable names like `x`, `temp`, `data2` make the code very hard to follow.",
        "action_item": "Break app.py into at least 3 files: `app.py` (UI only), `llm_client.py` (API calls), `config.py` (constants/env vars). Rename variables to describe what they hold (e.g. `user_query`, `llm_response`, `chat_history`).",
        "was_acted_on": False,
    },

    # ---- Error Handling ----
    {
        "id": str(uuid4()),
        "dimension_id": "d1000000-0000-0000-0000-000000000002",
        "stack_tag": None,
        "score": "green",
        "comment": "All API calls are wrapped in try/except with specific exception types. Users see friendly error messages, not raw stack traces.",
        "action_item": None,
        "was_acted_on": True,
    },
    {
        "id": str(uuid4()),
        "dimension_id": "d1000000-0000-0000-0000-000000000002",
        "stack_tag": None,
        "score": "yellow",
        "comment": "LLM API call has no error handling — if the API is down or returns an error, the app crashes with an unhandled exception.",
        "action_item": "Wrap your `client.messages.create()` call in a try/except block. Catch `anthropic.APIError` and display `st.error('Could not reach the AI service. Please try again.')` to the user.",
        "was_acted_on": True,
    },
    {
        "id": str(uuid4()),
        "dimension_id": "d1000000-0000-0000-0000-000000000002",
        "stack_tag": None,
        "score": "red",
        "comment": "No error handling anywhere. A bare `except: pass` was found on line 47, silently swallowing all errors.",
        "action_item": "Remove all bare `except: pass` blocks. Add specific exception handling for: (1) API failures with st.error(), (2) empty user input with st.warning(), (3) network timeouts with a retry message. At minimum, log errors with `print()` so you can debug in production.",
        "was_acted_on": False,
    },

    # ---- Architecture ----
    {
        "id": str(uuid4()),
        "dimension_id": "d1000000-0000-0000-0000-000000000003",
        "stack_tag": None,
        "score": "green",
        "comment": "Clean structure: app/, config.py, requirements.txt, README.md all at the right level. No business logic in the UI layer.",
        "action_item": None,
        "was_acted_on": True,
    },
    {
        "id": str(uuid4()),
        "dimension_id": "d1000000-0000-0000-0000-000000000003",
        "stack_tag": None,
        "score": "yellow",
        "comment": "Config values (API URL, model name) are hardcoded directly in the function that uses them instead of being centralized.",
        "action_item": "Create a `config.py` file at the project root. Move all constants (API_URL, MODEL_NAME, MAX_TOKENS) there. Import them where needed: `from config import MODEL_NAME`.",
        "was_acted_on": True,
    },
    {
        "id": str(uuid4()),
        "dimension_id": "d1000000-0000-0000-0000-000000000003",
        "stack_tag": None,
        "score": "red",
        "comment": "Everything is in a single file — no meaningful project structure. Impossible to navigate or extend.",
        "action_item": "Reorganize into: `app.py` (Streamlit entry), `services/llm.py` (AI calls), `services/db.py` (data access), `config.py` (env vars and constants). Add `__init__.py` to service directories.",
        "was_acted_on": False,
    },

    # ---- LLM Usage ----
    {
        "id": str(uuid4()),
        "dimension_id": "d1000000-0000-0000-0000-000000000004",
        "stack_tag": None,
        "score": "green",
        "comment": "API key loaded from environment variable, response parsing handles both text and tool_use content blocks, token usage is logged.",
        "action_item": None,
        "was_acted_on": True,
    },
    {
        "id": str(uuid4()),
        "dimension_id": "d1000000-0000-0000-0000-000000000004",
        "stack_tag": None,
        "score": "yellow",
        "comment": "API key is loaded from env (good!) but the response is accessed as `response.content` without checking if it's a text block first.",
        "action_item": "Access LLM response text safely: `response.content[0].text` can fail if the model returned a tool_use block. Use: `next(b.text for b in response.content if b.type == 'text', '')` or check `response.content[0].type == 'text'` first.",
        "was_acted_on": True,
    },
    {
        "id": str(uuid4()),
        "dimension_id": "d1000000-0000-0000-0000-000000000004",
        "stack_tag": None,
        "score": "red",
        "comment": "API key is hardcoded as a string literal on line 12. This is a critical security issue — anyone with repo access has your key.",
        "action_item": "1. Immediately rotate your API key at console.anthropic.com. 2. Remove the key from your code. 3. Add it to a `.env` file: `ANTHROPIC_API_KEY=sk-...`. 4. Load it with `os.environ.get('ANTHROPIC_API_KEY')`. 5. Add `.env` to `.gitignore` NOW.",
        "was_acted_on": False,
    },

    # ---- Deployment ----
    {
        "id": str(uuid4()),
        "dimension_id": "d1000000-0000-0000-0000-000000000005",
        "stack_tag": None,
        "score": "green",
        "comment": "Live at a public URL on Streamlit Cloud. Secrets are properly configured in the deployment dashboard. README includes the live link.",
        "action_item": None,
        "was_acted_on": True,
    },
    {
        "id": str(uuid4()),
        "dimension_id": "d1000000-0000-0000-0000-000000000005",
        "stack_tag": None,
        "score": "yellow",
        "comment": "App is deployed but the live URL returns a 502 error — likely a missing secret or requirements issue.",
        "action_item": "Check the Streamlit Cloud logs (app dashboard → Manage app → Logs). Verify that ANTHROPIC_API_KEY is set under Settings → Secrets. Confirm requirements.txt lists all dependencies including `anthropic`.",
        "was_acted_on": True,
    },
    {
        "id": str(uuid4()),
        "dimension_id": "d1000000-0000-0000-0000-000000000005",
        "stack_tag": None,
        "score": "red",
        "comment": "No deployed URL provided. The project only runs locally.",
        "action_item": "Deploy to Streamlit Cloud (free tier): 1. Push your code to GitHub. 2. Go to share.streamlit.io. 3. Click 'New app' → connect your repo. 4. Set your API key under Secrets. Include the public URL in your README.",
        "was_acted_on": False,
    },

    # ---- Documentation ----
    {
        "id": str(uuid4()),
        "dimension_id": "d1000000-0000-0000-0000-000000000006",
        "stack_tag": None,
        "score": "green",
        "comment": "README has: project description, setup instructions, environment variable guide, live URL, and a usage screenshot. Code has inline comments for non-obvious logic.",
        "action_item": None,
        "was_acted_on": True,
    },
    {
        "id": str(uuid4()),
        "dimension_id": "d1000000-0000-0000-0000-000000000006",
        "stack_tag": None,
        "score": "yellow",
        "comment": "README exists but is just the default GitHub template. No setup instructions or description of what the project does.",
        "action_item": "Update README.md to include: (1) What the project does in 2-3 sentences, (2) How to run it locally (`pip install -r requirements.txt && streamlit run app.py`), (3) Required environment variables, (4) Live demo URL.",
        "was_acted_on": True,
    },
    {
        "id": str(uuid4()),
        "dimension_id": "d1000000-0000-0000-0000-000000000006",
        "stack_tag": None,
        "score": "red",
        "comment": "No README. No comments in code. Someone cloning this repo would have no idea how to run it or what it does.",
        "action_item": "Create README.md now with at minimum: project title, one-line description, `pip install -r requirements.txt`, how to set the API key, how to run the app. Then add docstrings to your main functions.",
        "was_acted_on": False,
    },

    # ---- Prompt Engineering ----
    {
        "id": str(uuid4()),
        "dimension_id": "d1000000-0000-0000-0000-000000000007",
        "stack_tag": None,
        "score": "green",
        "comment": "System message clearly defines the AI persona and constraints. Output format is specified in the prompt. User input is validated before being sent to the LLM.",
        "action_item": None,
        "was_acted_on": True,
    },
    {
        "id": str(uuid4()),
        "dimension_id": "d1000000-0000-0000-0000-000000000007",
        "stack_tag": None,
        "score": "yellow",
        "comment": "System message exists but is very vague ('You are a helpful assistant'). No output format specified, so the LLM response format varies unpredictably.",
        "action_item": "Improve your system message to specify: role ('You are a Python coding tutor for beginners'), constraints ('Keep answers under 200 words'), and output format ('Always end with a working code example'). Test with 5 different inputs to verify consistency.",
        "was_acted_on": True,
    },
    {
        "id": str(uuid4()),
        "dimension_id": "d1000000-0000-0000-0000-000000000007",
        "stack_tag": None,
        "score": "red",
        "comment": "No system message. User input is passed directly to the API with no context, persona, or format instructions. Results are inconsistent.",
        "action_item": "Add a system message to every API call: `messages.create(model=..., system='Your role here', messages=[...])`. Define: what the AI is, what it should/shouldn't do, and what format the output should be in. This is the single highest-leverage improvement you can make.",
        "was_acted_on": False,
    },
]


def seed_examples() -> None:
    client = get_service_client()
    success = 0
    failed = 0

    print(f"Seeding {len(EXAMPLES)} example feedback entries...\n")

    for example in EXAMPLES:
        dim_id = example["dimension_id"]
        score = example["score"]
        try:
            resp = (
                client.table("example_feedback")
                .upsert(example, on_conflict="id")
                .execute()
            )
            if resp.data:
                print(f"  + [{score.upper():6}] dim={dim_id[:8]}... — {example['comment'][:60]}...")
                success += 1
            else:
                print(f"  ! FAILED: dim={dim_id[:8]} score={score}")
                failed += 1
        except Exception as exc:
            print(f"  ! ERROR: {exc}")
            failed += 1

    print(f"\n{'='*50}")
    print(f"Done. Seeded: {success}  Failed: {failed}")


if __name__ == "__main__":
    seed_examples()
