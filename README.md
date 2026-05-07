# Unapproved PRs Report Action

GitHub Action to identify and report merged Pull Requests that were never approved before merging **to the default branch**.

This is useful for tracking emergency hot-fix PRs that were merged without prior review, enabling post-merge code review processes.

## Features

- ✅ Finds all merged PRs without approval reviews **to the default branch** (main/develop/etc)
- ✅ Checks approval status before merge time (not after)
- ✅ Correctly handles approval states (COMMENTED reviews don't override APPROVED)
- ✅ Tracks latest approval per reviewer (handles review state changes)
- ✅ Optionally creates a GitHub issue with detailed report
- ✅ Configurable lookback period
- ✅ Groups results by who merged the PR
- ✅ Progress logging for long-running searches
- ✅ Graceful cancellation support
- ✅ Efficient API filtering (only checks default branch PRs)

## Usage

### Basic Example

```yaml
name: Unapproved PRs Report

on:
  schedule:
    - cron: '0 9 * * *'  # Daily at 9 AM UTC
  workflow_dispatch:

permissions:
  issues: write
  pull-requests: read

jobs:
  check-approvals:
    runs-on: ubuntu-latest
    steps:
      - uses: viboo-AG/unapproved-prs-action@main
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

### Advanced Example

```yaml
name: Unapproved PRs Report

on:
  schedule:
    - cron: '0 9 * * *'
  workflow_dispatch:
    inputs:
      days:
        description: 'Number of days to look back'
        required: false
        default: '30'

permissions:
  issues: write
  pull-requests: read

jobs:
  check-approvals:
    runs-on: ubuntu-latest
    timeout-minutes: 60  # For repos with 100s of PRs per month
    steps:
      - name: Generate token for org-level access
        id: generate-token
        uses: actions/create-github-app-token@v1
        with:
          app-id: ${{ secrets.ORG_AUTH_APP_ID }}
          private-key: ${{ secrets.ORG_AUTH_APP_PEM }}
      
      - name: Check for unapproved PRs
        uses: viboo-AG/unapproved-prs-action@main
        with:
          days: ${{ github.event.inputs.days || '30' }}
          assignees: 'didier-viboo,hubebenj'
          labels: 'code-review,needs-review'
          issue-title-prefix: 'Code Review Required'
        env:
          GITHUB_TOKEN: ${{ steps.generate-token.outputs.token }}
```

### Check Multiple Repositories

```yaml
jobs:
  check-all-repos:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        repo: ['viboo-AG/PCaaS', 'viboo-AG/config-gcp', 'viboo-AG/viboo-cloud']
    steps:
      - uses: viboo-AG/unapproved-prs-action@main
        with:
          repo: ${{ matrix.repo }}
          days: '30'
          assignees: 'didier-viboo'
        env:
          GITHUB_TOKEN: ${{ secrets.PAT_TOKEN }}
```

## Inputs

| Input | Description | Required | Default |
|-------|-------------|----------|---------|
| `repo` | Repository to check (format: `owner/name`) | No | Current repository |
| `days` | Number of days to look back | No | `30` |
| `create-issue` | Create GitHub issue with report | No | `true` |
| `assignees` | Comma-separated assignees for the issue | No | - |
| `labels` | Comma-separated labels for the issue | No | `code-review` |
| `issue-title-prefix` | Prefix for the issue title | No | `Unapproved Merged PRs Report` |

## Outputs

| Output | Description |
|--------|-------------|
| `has-unapproved` | Whether unapproved PRs were found (`true`/`false`) |
| `report-file` | Path to the generated markdown report file |
| `pr-count` | Number of unapproved PRs found |

## Performance

The action's runtime depends on the number of PRs **to the default branch** in your repository:

| Time Period | Typical PR Count | Estimated Runtime |
|-------------|-----------------|-------------------|
| 7 days      | 10-20 PRs       | 1-2 minutes       |
| 30 days     | 50-100 PRs      | 5-10 minutes      |
| 90 days     | 150-300 PRs     | 15-25 minutes     |
| 180 days    | 300-500 PRs     | 30-45 minutes     |
| 365 days    | 600-1000 PRs    | 50-70 minutes     |

**Optimization:** The action filters PRs at the API level using `base=default_branch`, which significantly reduces the number of PRs to check. For repositories with many feature-to-feature branch merges, this can reduce processing time by 50-80%.

**Note on GitHub App Tokens:** GitHub App tokens (from `actions/create-github-app-token`) expire after **1 hour**. For very active repositories or searches >365 days that may take >60 minutes:
- Use a Personal Access Token (PAT) instead
- Or split into multiple smaller time periods

```yaml
# For long-running searches, use a PAT
env:
  GITHUB_TOKEN: ${{ secrets.LONG_RUNNING_PAT || steps.generate-token.outputs.token }}
```

Progress is logged every 50 PRs to monitor long-running searches.

## Example Output

The action creates an issue like this:

```markdown
# Merged PRs Without Approval

This report shows PRs merged to `develop` in the last 30 days without approval.
These PRs should be reviewed post-merge to ensure code quality.

⚠️ **Found 3 merged PR(s) without approval:**

## Merged by @didier-viboo (2 PR(s))

- **[#123](https://github.com/viboo-AG/PCaaS/pull/123)**: Fix critical production bug
  - Merged: 2026-05-06 22:30 UTC
  - Author: @didier-viboo

- **[#124](https://github.com/viboo-AG/PCaaS/pull/124)**: Hotfix database connection
  - Merged: 2026-05-06 23:15 UTC
  - Author: @didier-viboo

## Merged by @hubebenj (1 PR(s))

- **[#125](https://github.com/viboo-AG/PCaaS/pull/125)**: Emergency scaling fix
  - Merged: 2026-05-07 01:20 UTC
  - Author: @hubebenj

## Action Required

Please review these PRs and add a post-merge review:
1. Review the changes in the PR
2. Add your review comments (GitHub mobile app allows post-merge reviews)
3. Close this issue once all PRs have been reviewed
```

## How It Works

1. **Queries merged PRs** from the last N days (configurable) **that were merged to the default branch**
2. **Filters at API level** using `base=default_branch` to reduce unnecessary checks
3. **Checks each PR** for approval reviews submitted before merge time
4. **Tracks approval states** per reviewer:
   - `APPROVED` stays in effect until explicitly dismissed or changed to `REQUEST_CHANGES`
   - `COMMENTED` reviews don't cancel approvals
   - Only `DISMISSED` or `REQUEST_CHANGES` override a previous approval
5. **Generates report** grouped by who merged the PR (if unapproved PRs exist)
6. **Creates GitHub issue** with the report (optional)

### Why Only Default Branch?

The action only checks PRs merged to the default branch (e.g., `main`, `develop`, `master`) because:
- These are production-bound changes that require the highest scrutiny
- Feature-to-feature branch merges are typically part of ongoing development
- Reduces API calls by 50-80% in repos with many feature branches
- Focuses on the most critical code review gaps

### Approval Detection Logic

The action correctly handles GitHub's review state model:
- An `APPROVED` review remains valid until the reviewer explicitly dismisses it or requests changes
- Adding comments after approving doesn't cancel the approval
- This matches GitHub's native PR approval behavior

## Requirements

- **Permissions**: The workflow needs `issues: write` and `pull-requests: read` permissions
- **GitHub Token**: Must have access to the repository being checked
- **Python**: Uses Python 3.11 (automatically installed by the action)

## Post-Merge Review

According to [this GitHub discussion](https://github.com/orgs/community/discussions/70480#discussioncomment-8831121), GitHub's mobile app supports post-merge reviews, allowing teams to review emergency PRs after they've been merged.

## Troubleshooting

### Workflow runs for >1 hour then fails

**Cause:** GitHub App tokens expire after 1 hour.

**Solution:** Use a Personal Access Token for long searches:
```yaml
env:
  GITHUB_TOKEN: ${{ secrets.LONG_RUNNING_PAT || steps.generate-token.outputs.token }}
```

### Approved PRs appearing in report

**Cause:** This was a bug in earlier versions where `COMMENTED` reviews were incorrectly overriding `APPROVED` status.

**Solution:** Upgrade to the latest version (`@main`). The bug was fixed in commit `ebc5128`.

### No output or progress updates

**Cause:** The action prints progress to stderr, which may not be visible depending on your logging setup.

**Solution:** Check the full workflow logs. Progress is logged every 50 PRs checked.

### Feature branch PRs appearing in report

**Cause:** You may be using an older version that didn't filter by default branch.

**Solution:** Upgrade to `@main`. The action now only checks PRs merged to the default branch (commit `316ee41`).

## License

MIT

## Contributing

Contributions welcome! Please open an issue or PR.
