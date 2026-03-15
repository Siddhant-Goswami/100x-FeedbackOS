"""
Commit tracking script.

Queries reviews delivered in the last 7 days and checks if students
made commits to their repos after delivery.  Records comprehension events.

Usage:
    python scripts/track_commits.py

Requires all env vars (SUPABASE_*, GITHUB_TOKEN) to be set.
"""

from __future__ import annotations

import asyncio
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from github import Github, GithubException

from api.config import GITHUB_TOKEN
from api.models.database import get_service_client
from api.services.comprehension_service import (
    log_comprehension_event,
    match_commit_to_feedback,
)


async def main() -> None:
    client = get_service_client()
    gh = Github(GITHUB_TOKEN or None)

    cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    cutoff_iso = cutoff.isoformat()

    print(f"Checking reviews delivered since {cutoff_iso}\n")

    # Fetch recently delivered reviews with submission + student info
    reviews_resp = (
        client.table("reviews")
        .select(
            "id, submitted_at, ta_id, "
            "submission:submissions(github_repo_url, commit_sha, "
            "student:users!submissions_student_id_fkey(id, name, github_username))"
        )
        .in_("status", ["submitted", "delivered"])
        .gte("submitted_at", cutoff_iso)
        .execute()
    )
    reviews = reviews_resp.data or []

    if not reviews:
        print("No reviews found in the last 7 days.")
        return

    print(f"Found {len(reviews)} review(s) to check.\n")

    total_checked = 0
    total_addressed = 0
    total_new_events = 0

    for review in reviews:
        review_id = review["id"]
        submitted_at_str = review.get("submitted_at") or ""
        submission = review.get("submission") or {}
        student = submission.get("student") or {}

        github_username = student.get("github_username")
        student_id = student.get("id")
        student_name = student.get("name", "Unknown")
        repo_url = submission.get("github_repo_url", "")

        if not repo_url or not github_username:
            print(f"  [SKIP] Review {review_id[:8]} — missing repo URL or GitHub username")
            continue

        # Parse review delivery timestamp
        try:
            if submitted_at_str.endswith("Z"):
                submitted_at_str = submitted_at_str[:-1] + "+00:00"
            delivery_time = datetime.fromisoformat(submitted_at_str)
            if delivery_time.tzinfo is None:
                delivery_time = delivery_time.replace(tzinfo=timezone.utc)
        except ValueError:
            print(f"  [SKIP] Review {review_id[:8]} — cannot parse submitted_at: {submitted_at_str}")
            continue

        print(f"  Checking: Review {review_id[:8]} | Student: {student_name} | Repo: {repo_url}")

        # Fetch commits from student's repo after delivery
        try:
            # Extract owner/repo from URL
            import re
            match = re.search(r"github\.com[/:]([^/]+)/([^/.]+?)(?:\.git)?$", repo_url)
            if not match:
                print(f"    [WARN] Cannot parse repo URL: {repo_url}")
                continue

            owner, repo_name = match.group(1), match.group(2)
            repo = gh.get_repo(f"{owner}/{repo_name}")

            # Get commits after delivery time
            commits = list(repo.get_commits(since=delivery_time))

        except GithubException as exc:
            print(f"    [ERROR] GitHub API error for {repo_url}: {exc}")
            continue
        except Exception as exc:
            print(f"    [ERROR] Unexpected error for {repo_url}: {exc}")
            continue

        if not commits:
            print(f"    No new commits since delivery.")
            continue

        print(f"    Found {len(commits)} commit(s) after delivery.")

        for commit in commits:
            commit_sha = commit.sha
            commit_time = commit.commit.author.date
            if commit_time.tzinfo is None:
                commit_time = commit_time.replace(tzinfo=timezone.utc)

            # Files changed in this commit
            try:
                files_changed = [f.filename for f in commit.files]
            except Exception:
                files_changed = []

            hours_after = (commit_time - delivery_time).total_seconds() / 3600.0

            # Check if already logged
            existing = (
                client.table("comprehension_events")
                .select("id")
                .eq("review_id", review_id)
                .eq("commit_sha", commit_sha)
                .maybe_single()
                .execute()
            )
            if existing.data:
                print(f"    [SKIP] Commit {commit_sha[:7]} already logged.")
                continue

            addressed = match_commit_to_feedback(files_changed, review_id, client)

            event = log_comprehension_event(
                client=client,
                review_id=review_id,
                commit_sha=commit_sha,
                commit_timestamp=commit_time,
                files_changed=files_changed,
                addressed=addressed,
                hours_after=round(hours_after, 2),
            )

            status = "ADDRESSED" if addressed else "not addressed"
            print(
                f"    Logged commit {commit_sha[:7]} "
                f"({len(files_changed)} file(s)) — {status} "
                f"[{hours_after:.1f}h after delivery]"
            )
            total_new_events += 1
            if addressed:
                total_addressed += 1

        total_checked += 1

    print(f"\n{'='*50}")
    print(f"Summary:")
    print(f"  Reviews checked:       {total_checked}")
    print(f"  New events logged:     {total_new_events}")
    print(f"  Addressed (acted on):  {total_addressed}")
    if total_new_events > 0:
        rate = round(total_addressed / total_new_events * 100, 1)
        print(f"  Comprehension rate:    {rate}%")


if __name__ == "__main__":
    asyncio.run(main())
