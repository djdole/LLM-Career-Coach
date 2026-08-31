# Automation (GitHub Actions)

None of the workflows under `.github/workflows/` are required to run
`generator.py` locally - they are optional automation layered on top
of it.

| Workflow | Trigger | Purpose | Enabled by default |
|---|---|---|---|
| `tests.yml` | Push to any branch; PRs to `main` | Runs the full test suite with coverage, publishes results, and auto-commits coverage/test badges. | Yes |
| `generate.yml` | Push to `main` touching `data/profile.json`; manual `workflow_dispatch` | Regenerates baseline resumes/cover letters/README and opens a pull request with the result. | Yes |
| `auto-pr.yml` | Push to any branch except `main` | Opens a pull request back to `main` for that branch if one does not already exist. | Yes |
| `analyze.yml.disabled` | Manual `workflow_dispatch` (once renamed/enabled) | Runs a restricted, access-gated `--analyze` job-fit analysis. | No - ships disabled |

## `tests.yml`

Runs on push to any branch, and on PRs opened or synchronized against
`main`. Step by step:

1. Checks out the repository and sets up Python 3.12.
2. Installs `requirements-test.txt`.
3. Runs `pytest -q --testmon-noselect --cov=. --cov-report=term-missing --cov-report=xml:coverage.xml --cov-report=html:htmlcov --junitxml=pytest-results.xml`.
4. Publishes the JUnit test results (`dorny/test-reporter`).
5. Uploads the HTML coverage report as a workflow artifact.
6. Posts a coverage summary to the job summary, and - on pull requests -
   as a sticky PR comment.
7. On pushes only (not PRs), syncs to the latest commit on the branch,
   then regenerates `badges/coverage-badge.svg` and
   `badges/tests-badge.svg` via `genbadge` and auto-commits them with
   `[skip ci]` in the message.

It always passes `--testmon-noselect`, even though a local bare
`pytest` defaults to testmon-selected runs (`addopts = --testmon` in
`pytest.ini`). This is deliberate: CI needs the guarantee that every
push and PR runs the complete suite with full coverage every time,
since the coverage percentage, the badges, and the PR comment all
depend on that being true - testmon's dependency tracking is a local,
per-checkout convenience, not something CI correctness should rely on.
`--testmon-noselect` keeps the testmon plugin active (so the
`--testmon` flag baked into `pytest.ini`'s `addopts` stays valid,
rather than erroring) but forces it back to running everything, as if
testmon were not involved at all. See `10-testing.md` for the full
`pytest-testmon` explanation.

## `generate.yml`

Triggers on a push to `main` that touches `data/profile.json`, plus a
manual `workflow_dispatch`. The `paths` filter means this **only**
fires for a local `KNOWLEDGE_BASE` at its default path - a URL-based
`KNOWLEDGE_BASE` (pointing somewhere outside this repo) would need a
different trigger, since GitHub Actions' `paths` filter only watches
files inside this repository.

What it does:

1. Checks out the repository and sets up Python 3.12.
2. Installs `requirements.txt`.
3. Runs `python generator.py` (the default targets - resume, cover
   letter, readme) with every setting from `03-configuration.md`
   sourced from repo/org secrets or variables
   (`${{ secrets.X || vars.X || 'default' }}`), falling back to the
   default baked into the workflow file if neither a secret nor a
   variable is set for that name.
4. Opens a pull request with the regenerated files via
   `peter-evans/create-pull-request`, using the same environment
   resolution as step 3, labeled `automated-pr` with a body noting
   that local-model output can drift more than a hosted model's and is
   worth a closer review.

For this to work end to end, at minimum
`LITELLM_BASE_URL`/`LITELLM_API_KEY`/`LITELLM_MODEL` must be
configured as repo (or org) secrets or variables under
**Settings > Secrets and variables > Actions**. If you use
`OUTPUT_REPO`, its related variables (`OUTPUT_REPO`,
`OUTPUT_REPO_TOKEN`, and so on) need to be configured there too, or the
workflow falls back to the placeholder defaults baked into the file
(for example a literal `https://github.com/YOUR_USERNAME/your-resumes.git`),
which will fail against a real run.

## `auto-pr.yml`

Triggers on a push to any branch **except** `main`. If no open pull
request already targets `main` from that branch (checked via
`gh pr list`), it opens one with `gh pr create`, using the `PAT_TOKEN`
secret rather than the default `GITHUB_TOKEN`, and applies the labels
`auto-generated,needs-review`.

## `analyze.yml.disabled` and `README-analyze-setup.md`

These two files are a pair: the workflow implements a manually
triggered, access-restricted `--analyze` run, and the companion doc
covers the one-time setup it needs.

**Why it ships disabled:** the `.disabled` suffix makes GitHub Actions
ignore the file entirely - it will not appear in the Actions tab and
cannot be triggered - specifically so it cannot go live before the
access restrictions it depends on are actually configured. It must not
be renamed to `analyze.yml` until the setup steps below are done;
doing so first would make it triggerable by anyone with write access,
with none of the intended restrictions in place yet.

**The four layers of restriction it relies on**, from strongest to
weakest:

| Layer | What it restricts | Enforced by |
|---|---|---|
| Repository access | Whether the workflow (and everything else in the repo) is visible at all | GitHub, platform-level |
| Workflow execution protections (actor rules) | Who can trigger `workflow_dispatch` on this specific workflow | GitHub, platform-level (public-preview feature, may not be on your plan) |
| Environment required reviewers | Approval gate before the job runs; scopes secrets to approved runs | GitHub, platform-level (Settings > Environments) |
| The in-workflow `authorize` job | An allow-list check against configured usernames/team, as a fallback for plans without actor rules | This workflow's own code, not GitHub itself |

Be explicit about what this does **not** give you: GitHub has no
per-workflow visibility control. Workflow files are ordinary files in
the repo, and a workflow's run history and logs follow repository read
access - anyone who can read the repo can see every workflow's runs
and logs, including failed `authorize` runs from someone not on the
allow-list. If you need this to be genuinely invisible to everyone but
one person or team, the repository itself needs to be private (or
internal) with collaborator access limited to that person or team;
everything else is defense-in-depth on top of that, not a substitute
for it.

**One-time setup**, from `README-analyze-setup.md`, in order:

1. **Repository access** - make the repo private if it is not already,
   and grant only the intended user(s)/team read (or higher) access.
2. **Environment protection** - create a `job-fit-analysis` environment
   (Settings > Environments) matching the workflow's `environment:`
   key, add the intended user or team as a required reviewer, and add
   `LITELLM_BASE_URL`/`LITELLM_API_KEY` as environment secrets there
   (not repository secrets), so they are only readable by approved
   runs.
3. **Allow-list variables/secrets** for the in-workflow `authorize`
   job's fallback check: `ANALYZE_ALLOWED_USERS` (a comma-separated
   list of GitHub usernames), or `ANALYZE_ALLOWED_TEAM` (an
   `org/team-slug`) plus `ANALYZE_TEAM_READ_TOKEN` (a PAT able to read
   team membership, since the default `GITHUB_TOKEN` cannot) if you
   use a team instead of a hardcoded list. `LITELLM_MODEL` can
   optionally be set here too.
4. **Enable the workflow** - with steps 1-3 in place, rename
   `analyze.yml.disabled` to `analyze.yml` and commit that rename.
5. **Workflow execution protections** (if available on your plan,
   under Settings > Actions > Policies) - only possible once the
   workflow is enabled and GitHub has indexed it. Add an actor rule
   limiting who can trigger `workflow_dispatch` on `analyze.yml`.
6. Trigger it from the Actions tab, or:
   ```bash
   gh workflow run analyze.yml -f job_description="paste text, a repo-relative file path, or a URL here"
   ```

**Operational details worth knowing:** the job writes a throwaway
`.env` from the configured secrets at the start of the run and deletes
it at the end (`if: always()`), so it does not persist in the checkout
or get uploaded anywhere. It then runs `./generate.sh --analyze "..."`
directly, and since `generate.sh` bootstraps a fresh Python virtual
environment on every run with no cache between runs, expect the run to
take a few minutes even for a quick analysis.
