"""
GitHub service.

Wraps PyGithub to fetch repository file trees and key file content
for stack detection.
"""

from __future__ import annotations

import logging
import re
from typing import Optional

from github import Github, GithubException
from github.Repository import Repository

from api.config import GITHUB_TOKEN

logger = logging.getLogger(__name__)

# Files that give strong signals about the project stack
_KEY_FILES = [
    "requirements.txt",
    "pyproject.toml",
    "package.json",
    "Pipfile",
    "app.py",
    "main.py",
    "server.py",
    "index.py",
    "Dockerfile",
    "docker-compose.yml",
    "README.md",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_owner_repo(repo_url: str) -> tuple[str, str]:
    """
    Extract (owner, repo_name) from a GitHub URL.

    Handles formats:
    - https://github.com/owner/repo
    - https://github.com/owner/repo.git
    - git@github.com:owner/repo.git
    """
    # HTTPS format
    match = re.search(r"github\.com[/:]([^/]+)/([^/.]+?)(?:\.git)?$", repo_url)
    if not match:
        raise ValueError(f"Cannot parse owner/repo from URL: {repo_url!r}")
    return match.group(1), match.group(2)


def _get_repo(repo_url: str) -> Repository:
    """Return a PyGithub Repository object."""
    owner, repo_name = _parse_owner_repo(repo_url)
    g = Github(GITHUB_TOKEN or None)
    return g.get_repo(f"{owner}/{repo_name}")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def fetch_repo_files(
    repo_url: str, commit_sha: Optional[str] = None
) -> list[str]:
    """
    Return a flat list of all file paths in the repository at a given
    commit (defaults to the default branch HEAD).

    Large repos are truncated at 500 files to keep LLM input manageable.
    """
    try:
        repo = _get_repo(repo_url)
        ref = commit_sha or repo.default_branch

        tree = repo.get_git_tree(ref, recursive=True)
        paths = [item.path for item in tree.tree if item.type == "blob"]

        if len(paths) > 500:
            logger.warning(
                "Repo %s has %d files — truncating to 500 for stack detection.",
                repo_url,
                len(paths),
            )
            paths = paths[:500]

        return paths

    except GithubException as exc:
        logger.error("GitHub API error fetching file tree for %s: %s", repo_url, exc)
        return []
    except Exception as exc:
        logger.error("Unexpected error fetching repo files for %s: %s", repo_url, exc)
        return []


async def get_file_content(repo_url: str, filepath: str) -> str:
    """
    Fetch the content of a single file from the repository as a string.

    Returns an empty string if the file cannot be read.
    """
    try:
        repo = _get_repo(repo_url)
        contents = repo.get_contents(filepath)
        # get_contents may return a list for directories
        if isinstance(contents, list):
            return ""
        return contents.decoded_content.decode("utf-8", errors="replace")

    except GithubException as exc:
        logger.warning("Could not fetch %s from %s: %s", filepath, repo_url, exc)
        return ""
    except Exception as exc:
        logger.warning(
            "Unexpected error fetching %s from %s: %s", filepath, repo_url, exc
        )
        return ""


async def parse_key_files(repo_url: str) -> dict[str, str]:
    """
    Fetch the first 50 lines of each key dependency/entry-point file that
    exists in the repo.

    Returns a mapping of filename → content_snippet (up to 50 lines).
    """
    snippets: dict[str, str] = {}
    for filename in _KEY_FILES:
        content = await get_file_content(repo_url, filename)
        if content:
            lines = content.splitlines()[:50]
            snippets[filename] = "\n".join(lines)

    return snippets
