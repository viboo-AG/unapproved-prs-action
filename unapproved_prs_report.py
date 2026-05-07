#!/usr/bin/env python3
"""
Script to identify merged Pull Requests that were never approved.

This is useful for tracking PRs that were merged during emergency hot-fixes
without prior approval, so they can be reviewed post-merge.
"""

import argparse
import os
import signal
import sys
from collections.abc import Sequence
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any, TextIO

from github import Auth, Github
from github.GithubException import GithubException

if TYPE_CHECKING:
    from github.PullRequest import PullRequest
    from github.Repository import Repository


# Flag to track if we should exit early
_should_exit = False


def _signal_handler(signum: int, frame: Any) -> None:
    """Handle SIGTERM and SIGINT for graceful cancellation."""
    global _should_exit
    _should_exit = True
    print("\nReceived cancellation signal, exiting...", file=sys.stderr)
    sys.exit(130)  # Exit code 128 + SIGINT(2)


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

    # Track approval status per reviewer
    # Note: In GitHub, APPROVED stays in effect until explicitly dismissed or
    # changed to REQUEST_CHANGES. COMMENTED reviews don't override approvals.
    approvals: set[str] = set()

    for review in pr.get_reviews():
        # Check for cancellation signal
        if _should_exit:
            sys.exit(130)

        reviewer = review.user.login
        review_time = review.submitted_at

        # Only consider reviews submitted before merge
        if not review_time or review_time >= merge_time:
            continue

        # Track approval state changes
        if review.state == "APPROVED":
            approvals.add(reviewer)
        elif review.state in ("REQUEST_CHANGES", "DISMISSED"):
            # These states override a previous approval
            approvals.discard(reviewer)
        # COMMENTED state doesn't affect approval status

    return len(approvals) > 0


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
    checked_count = 0
    merged_count = 0

    print(f"Searching for merged PRs in the last {since_days} days...", file=sys.stderr)

    # Get all closed PRs sorted by updated date
    all_prs = repo.get_pulls(state="closed", sort="updated", direction="desc")

    for pr in all_prs:
        # Check for cancellation signal
        if _should_exit:
            sys.exit(130)

        checked_count += 1

        # Progress indicator every 50 PRs
        if checked_count % 50 == 0:
            print(f"Checked {checked_count} PRs, found {len(unreviewed_prs)} unapproved...", file=sys.stderr)

        # Skip if not merged
        if not pr.merged:
            continue

        # Skip if no merge timestamp
        if not pr.merged_at:
            continue

        # Stop if we've gone past our lookback window
        # Use updated_at for cutoff since that's what we sorted by
        if pr.updated_at and pr.updated_at < since_date:
            print(f"Reached PRs older than {since_days} days, stopping...", file=sys.stderr)
            break

        # Skip if merged before our cutoff
        if pr.merged_at < since_date:
            continue

        merged_count += 1

        # Check if it had approval before merge
        has_approval = _get_pr_approval_status(pr, pr.merged_at)

        if not has_approval:
            merged_by = pr.merged_by.login if pr.merged_by else "unknown"
            unreviewed_prs.append((pr, merged_by))
            print(f"Found unapproved PR #{pr.number}: {pr.title[:60]}...", file=sys.stderr)

    print(f"✓ Checked {checked_count} PRs ({merged_count} merged), found {len(unreviewed_prs)} unapproved", file=sys.stderr)
    return unreviewed_prs


def _generate_report(
    f: TextIO,
    repo: Any,  # Repository - using Any to avoid runtime import
    since_days: int = 30,
) -> None:
    """Generate a report of unapproved merged PRs."""

    unreviewed_prs = _find_unreviewed_merged_prs(repo, since_days)

    # If no unreviewed PRs found, don't generate a report
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
    # Register signal handlers for graceful cancellation
    signal.signal(signal.SIGTERM, _signal_handler)
    signal.signal(signal.SIGINT, _signal_handler)

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
    parser.add_argument(
        "--output",
        default="-",
        help="Output file path (default: stdout)",
    )

    args = parser.parse_args()

    # Get GitHub token from environment
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        print("Error: GITHUB_TOKEN environment variable not set", file=sys.stderr)
        sys.exit(1)

    # Initialize GitHub client with new authentication method
    auth = Auth.Token(token)
    gh = Github(auth=auth)

    try:
        repo = gh.get_repo(f"{args.owner}/{args.repo}")

        # Check if there are any unreviewed PRs before generating report
        unreviewed_prs = _find_unreviewed_merged_prs(repo, args.days)

        if not unreviewed_prs:
            # No unreviewed PRs found - this is success, just don't write output
            print(f"✓ No unapproved merged PRs found in the last {args.days} days", file=sys.stderr)
            sys.exit(0)

        # Generate the report to file or stdout
        if args.output == "-":
            _generate_report(sys.stdout, repo, args.days)
        else:
            with open(args.output, "w") as f:
                _generate_report(f, repo, args.days)
            print(f"✓ Report written to {args.output}", file=sys.stderr)

    except GithubException as e:
        print(f"Error accessing GitHub: {e}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
