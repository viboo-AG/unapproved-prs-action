#!/usr/bin/env python3
"""
Script to identify merged Pull Requests that were never approved.

This is useful for tracking PRs that were merged during emergency hot-fixes
without prior approval, so they can be reviewed post-merge.
"""

import argparse
import os
import sys
from collections.abc import Sequence
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any, TextIO

from github import Github
from github.GithubException import GithubException

if TYPE_CHECKING:
    from github.PullRequest import PullRequest
    from github.Repository import Repository


def _get_pr_approval_status(
    pr: Any,  # PullRequest - using Any to avoid runtime import
    merge_time: datetime | None,
) -> bool:
    """
    Check if a PR had any approvals before it was merged.

    Args:
        pr: Pull request object
        merge_time: When the PR was merged

    Returns:
        True if the PR had at least one approval before merge
    """
    if not merge_time:
        return False

    # Track the latest review state per reviewer
    reviewer_states: dict[str, tuple[datetime, str]] = {}

    for review in pr.get_reviews():
        reviewer = review.user.login
        review_time = review.submitted_at

        # Only consider reviews submitted before merge
        if review_time and review_time < merge_time:
            # Keep only the latest review from each reviewer
            if reviewer not in reviewer_states or review_time > reviewer_states[reviewer][0]:
                reviewer_states[reviewer] = (review_time, review.state)

    # Check if any reviewer's final state was APPROVED
    return any(state == "APPROVED" for _, state in reviewer_states.values())


def _find_unreviewed_merged_prs(
    repo: Any,  # Repository - using Any to avoid runtime import
    since_days: int = 30,
) -> Sequence[tuple[Any, str]]:  # list[tuple[PullRequest, str]]
    """
    Find merged PRs that were never approved before merge.

    Args:
        repo: GitHub repository object
        since_days: How many days back to search

    Returns:
        List of tuples (pr, merged_by)
    """
    unreviewed_prs: list[tuple[Any, str]] = []
    since_date = datetime.now(timezone.utc) - timedelta(days=since_days)

    # Get all closed PRs sorted by updated date
    # Note: We can't use search API here because it requires different authentication
    # Fallback to listing all closed PRs and filter by merged status and date
    all_prs = repo.get_pulls(state="closed", sort="updated", direction="desc")

    for pr in all_prs:
        # Skip if not merged
        if not pr.merged:
            continue

        # Skip if no merge timestamp
        if not pr.merged_at:
            continue

        # Stop if we've gone past our lookback window
        # Use updated_at for cutoff since that's what we sorted by
        if pr.updated_at and pr.updated_at < since_date:
            break

        # Skip if merged before our cutoff
        if pr.merged_at < since_date:
            continue

        # Check if it had approval before merge (optimized to break early)
        has_approval = _get_pr_approval_status(pr, pr.merged_at)

        if not has_approval:
            merged_by = pr.merged_by.login if pr.merged_by else "unknown"
            unreviewed_prs.append((pr, merged_by))

    return unreviewed_prs


def _generate_report(
    f: TextIO,
    repo: Any,  # Repository - using Any to avoid runtime import
    since_days: int = 30,
) -> None:
    """Generate a report of unapproved merged PRs."""

    unreviewed_prs = _find_unreviewed_merged_prs(repo, since_days)

    # If no unreviewed PRs found, exit without generating a report
    if not unreviewed_prs:
        return

    print("# Merged PRs Without Approval", file=f)
    print("", file=f)
    print(f"This report shows PRs merged in the last {since_days} days without approval.", file=f)
    print("These PRs should be reviewed post-merge to ensure code quality.", file=f)
    print("", file=f)

    print(f"⚠️ **Found {len(unreviewed_prs)} merged PR(s) without approval:**", file=f)
    print("", file=f)

    # Group by merged_by
    by_merger: dict[str, list[Any]] = {}  # dict[str, list[PullRequest]]
    for pr, merged_by in unreviewed_prs:
        if merged_by not in by_merger:
            by_merger[merged_by] = []
        by_merger[merged_by].append(pr)

    # Print grouped by who merged
    for merged_by in sorted(by_merger.keys()):
        prs = by_merger[merged_by]
        print(f"## Merged by @{merged_by} ({len(prs)} PR(s))", file=f)
        print("", file=f)

        for pr in prs:
            merged_at = pr.merged_at.strftime("%Y-%m-%d %H:%M UTC") if pr.merged_at else "unknown"
            print(f"- **[#{pr.number}]({pr.html_url})**: {pr.title}", file=f)
            print(f"  - Merged: {merged_at}", file=f)
            print(f"  - Author: @{pr.user.login}", file=f)
            print("", file=f)

    print("## Action Required", file=f)
    print("", file=f)
    print("Please review these PRs and add a post-merge review:", file=f)
    print("1. Review the changes in the PR", file=f)
    print("2. Add your review comments (GitHub mobile app allows post-merge reviews)", file=f)
    print("3. Close this issue once all PRs have been reviewed", file=f)
    print("", file=f)
    print("---", file=f)
    print(f"*Report generated on {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}*", file=f)


def main() -> None:
    """Main function."""
    parser = argparse.ArgumentParser(description="Generate report of merged PRs without approval.")
    parser.add_argument(
        "--owner",
        required=True,
        help="Repository owner (organization or user)",
    )
    parser.add_argument(
        "--repo",
        required=True,
        help="Repository name",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=30,
        help="Number of days to look back (default: 30)",
    )

    args = parser.parse_args()

    # Get GitHub token from environment
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        print("Error: GITHUB_TOKEN environment variable not set", file=sys.stderr)
        sys.exit(1)

    # Initialize GitHub client
    gh = Github(token)

    try:
        repo = gh.get_repo(f"{args.owner}/{args.repo}")

        # Check if there are any unreviewed PRs before generating report
        unreviewed_prs = _find_unreviewed_merged_prs(repo, args.days)

        if not unreviewed_prs:
            # No unreviewed PRs found - exit with code 1 to signal no action needed
            sys.exit(1)

        # Generate the report
        _generate_report(sys.stdout, repo, args.days)
    except GithubException as e:
        print(f"Error accessing GitHub: {e}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
