# Unapproved PRs Report Action

GitHub Action to identify and report merged Pull Requests that were never approved before merging.

This is useful for tracking emergency hot-fix PRs that were merged without prior review, enabling post-merge code review processes.

## Features

- ✅ Finds all merged PRs without approval reviews
- ✅ Checks approval status before merge time (not after)
- ✅ Tracks latest review state per reviewer (handles review changes)
- ✅ Optionally creates a GitHub issue with detailed report
- ✅ Configurable lookback period
- ✅ Groups results by who merged the PR

## Usage

### Basic Example

```yaml
name: Unapproved PRs Report

on:
  schedule:
    - cron: '0 9 * * *'  # Daily at 9 AM UTC
  workflow_dispatch:

permissions:
  contents: read
  issues: write
  pull-requests: read

jobs:
  check-approvals:
    runs-on: ubuntu-latest
    steps:
      - uses: viboo-AG/unapproved-prs-action@v1
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
  contents: read
  issues: write
  pull-requests: read

jobs:
  check-approvals:
    runs-on: ubuntu-latest
    steps:
      - name: Generate token for org-level access
        id: generate-token
        uses: actions/create-github-app-token@v1
        with:
          app-id: ${{ secrets.ORG_AUTH_APP_ID }}
          private-key: ${{ secrets.ORG_AUTH_APP_PEM }}
      
      - name: Check for unapproved PRs
        uses: viboo-AG/unapproved-prs-action@v1
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
      - uses: viboo-AG/unapproved-prs-action@v1
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

## Example Output

The action creates an issue like this:

```markdown
# Merged PRs Without Approval

This report shows PRs merged in the last 30 days without approval.
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

1. **Queries merged PRs** from the last N days (configurable)
2. **Checks each PR** for approval reviews submitted before merge time
3. **Tracks review states** per reviewer to handle review changes
4. **Generates report** grouped by who merged the PR (if unapproved PRs exist)
5. **Creates GitHub issue** with the report (optional)

## Requirements

- **Permissions**: The workflow needs `issues: write` and `pull-requests: read` permissions
- **GitHub Token**: Must have access to the repository being checked
- **Python**: Uses Python 3.11 (automatically installed by the action)

## Post-Merge Review

According to [this GitHub discussion](https://github.com/orgs/community/discussions/70480#discussioncomment-8831121), GitHub's mobile app supports post-merge reviews, allowing teams to review emergency PRs after they've been merged.

## License

MIT

## Contributing

Contributions welcome! Please open an issue or PR.

## Related

- Issue: [viboo-AG/PCaaS#4850](https://github.com/viboo-AG/PCaaS/issues/4850)
- PR: [viboo-AG/PCaaS#4896](https://github.com/viboo-AG/PCaaS/pull/4896)
