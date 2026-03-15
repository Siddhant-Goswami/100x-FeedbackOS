"""
Create Supabase Auth users for test accounts.

Must run AFTER seed_test_data.py.
Uses the service role key to create users with specific IDs so they
match the rows seeded in the public.users table.

Usage:
    python scripts/create_auth_users.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from api.models.database import get_service_client

TEST_USERS = [
    {
        "id": "u0000000-0000-0000-0000-000000000001",
        "email": "instructor@100x.test",
        "password": "feedbackos-dev-2026",
        "role": "instructor",
    },
    {
        "id": "u0000000-0000-0000-0000-000000000002",
        "email": "ta1@100x.test",
        "password": "feedbackos-dev-2026",
        "role": "ta",
    },
    {
        "id": "u0000000-0000-0000-0000-000000000003",
        "email": "ta2@100x.test",
        "password": "feedbackos-dev-2026",
        "role": "ta",
    },
    {
        "id": "u0000000-0000-0000-0000-000000000004",
        "email": "priya@100x.test",
        "password": "feedbackos-dev-2026",
        "role": "student",
    },
    {
        "id": "u0000000-0000-0000-0000-000000000005",
        "email": "arjun@100x.test",
        "password": "feedbackos-dev-2026",
        "role": "student",
    },
    {
        "id": "u0000000-0000-0000-0000-000000000006",
        "email": "kavitha@100x.test",
        "password": "feedbackos-dev-2026",
        "role": "student",
    },
]


def create_users() -> None:
    client = get_service_client()

    print("\nCreating Supabase Auth users...\n")
    for user in TEST_USERS:
        try:
            resp = client.auth.admin.create_user({
                "email": user["email"],
                "password": user["password"],
                "email_confirm": True,  # skip email confirmation in dev
                "user_metadata": {"role": user["role"]},
            })
            if resp.user:
                auth_id = resp.user.id
                print(f"  CREATED  {user['email']}  auth_id={auth_id}")

                # Update the public.users row with the real auth ID
                # (The seed_test_data.py used fake fixed IDs; now sync to the real auth UUID)
                client.table("users").update({"id": auth_id}).eq("email", user["email"]).execute()
                print(f"           → Synced public.users id to {auth_id}")
            else:
                print(f"  WARN     {user['email']}: no user returned")
        except Exception as e:
            err = str(e)
            if "already been registered" in err or "already exists" in err:
                print(f"  EXISTS   {user['email']} (already registered)")
            else:
                print(f"  ERROR    {user['email']}: {e}")

    print()
    print("Done. Login credentials:")
    print("  Email:    <any of the above>")
    print("  Password: feedbackos-dev-2026")
    print()
    print("NOTE: After running this, also run seed_test_data.py again if")
    print("      submission foreign keys point to the old fake user IDs.")


if __name__ == "__main__":
    create_users()
