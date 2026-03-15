"""
Seed script: load rubric JSON files and upsert into Supabase.

Usage:
    python scripts/seed_rubrics.py

Requires SUPABASE_URL and SUPABASE_SERVICE_KEY to be set in .env.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Allow running from project root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from api.config import RUBRIC_DIR
from api.models.database import get_service_client


def seed_rubrics() -> None:
    client = get_service_client()
    rubric_files = sorted(RUBRIC_DIR.glob("*.json"))

    if not rubric_files:
        print(f"No JSON files found in {RUBRIC_DIR}")
        return

    total_rubrics = 0
    total_dimensions = 0

    for filepath in rubric_files:
        print(f"\nProcessing: {filepath.name}")
        with filepath.open("r", encoding="utf-8") as fh:
            data = json.load(fh)

        # Upsert the rubric record
        rubric_payload = {
            "id": data["id"],
            "name": data["name"],
            "type": data["type"],
            "stack_tag": data.get("stack_tag"),
        }
        rubric_resp = (
            client.table("rubrics")
            .upsert(rubric_payload, on_conflict="id")
            .execute()
        )
        if rubric_resp.data:
            print(f"  Upserted rubric: {data['name']} (id={data['id']})")
            total_rubrics += 1
        else:
            print(f"  WARNING: Could not upsert rubric {data['name']}")
            continue

        # Upsert each dimension
        dimensions: list[dict] = data.get("dimensions", [])
        for dim in dimensions:
            dim_payload = {
                "id": dim["id"],
                "rubric_id": data["id"],
                "name": dim["name"],
                "description": dim["description"],
                "category": dim["category"],
                "sort_order": dim.get("sort_order", 0),
                "is_required": dim.get("is_required", True),
                "stack_tags": dim.get("stack_tags", []),
            }
            dim_resp = (
                client.table("rubric_dimensions")
                .upsert(dim_payload, on_conflict="id")
                .execute()
            )
            if dim_resp.data:
                print(f"    + Dimension: {dim['name']}")
                total_dimensions += 1
            else:
                print(f"    WARNING: Could not upsert dimension {dim['name']}")

    print(f"\n{'='*50}")
    print(f"Seeding complete.")
    print(f"  Rubrics:    {total_rubrics}")
    print(f"  Dimensions: {total_dimensions}")


if __name__ == "__main__":
    seed_rubrics()
