# Setting up the restricted "Job Fit Analysis" workflow

`.github/workflows/analyze.yml` runs `./generate.sh --analyze <job_description>`
on demand. This doc covers what it takes to actually restrict it to one
person or team, and is honest about a couple of things GitHub does not
let you restrict at the workflow level, so you don't end up assuming
protection that isn't there.

## What GitHub can and can't do here

**Can't:** GitHub has no "hide this one workflow" setting. Workflow files
are ordinary files in the repo, and a workflow's run history and logs
follow **repository read access** - anyone who can read the repo can see
every workflow in it, every run, and every run's logs. There is no
per-workflow visibility list that lets some repo collaborators see a
workflow's runs while others can't.

**Can:** restrict who can *trigger* it, and gate/scope what happens when
it runs. That's what this workflow and the setup below actually do:

| Layer | What it restricts | Where |
|---|---|---|
| Repository visibility/access | Whether the workflow (and everything else in the repo) is visible at all | Repo Settings > General / Collaborators |
| Workflow execution protections (actor rules) | Who can trigger `workflow_dispatch` on this workflow, platform-side | Settings > Actions > Policies (public preview; may not be on your plan) |
| Environment required reviewers | Approval gate before the job runs; scopes secrets to approved runs | Settings > Environments |
| The `authorize` job in `analyze.yml` | In-workflow fallback allow-list check | Repo/org Actions variables + this workflow |

If you need this to be genuinely invisible to everyone but one person or
team - not just gated - the repository itself needs to be private (or
internal, on GitHub Enterprise) with collaborator access limited to that
person/team. Everything else below is defense-in-depth on top of that,
not a substitute for it.

## One-time setup

1. **Repository access.** Make the repo private if it isn't already, and
   only grant the intended user(s)/team read (or higher) access.

2. **Workflow execution protections** (if available to you - this is a
   public-preview GitHub feature as of mid-2026, under Settings > Actions
   > Policies, built on rulesets). Add an actor rule limiting who can
   trigger `workflow_dispatch` on `analyze.yml` to the intended user or
   team. This is the strongest trigger-side control, enforced by GitHub
   itself before the workflow even starts.

3. **Environment protection.** Settings > Environments > New environment,
   named `job-fit-analysis` (matching the `environment:` key in
   `analyze.yml`). Add the intended user or team as a required reviewer.
   Add `LITELLM_BASE_URL` and `LITELLM_API_KEY` as **environment secrets**
   here (not repository secrets) so they're only readable by runs of this
   environment.

4. **Allow-list variables/secrets**, for the `authorize` job's fallback
   check (Settings > Secrets and variables > Actions):
   - `ANALYZE_ALLOWED_USERS` (variable) - comma-separated GitHub
     usernames, e.g. `octocat, some-teammate`. Simplest option for a
     single person or small fixed group.
   - `ANALYZE_ALLOWED_TEAM` (variable) - `org/team-slug`, if you'd
     rather manage membership via a GitHub team instead of a hardcoded
     list.
   - `ANALYZE_TEAM_READ_TOKEN` (secret) - only needed if you set
     `ANALYZE_ALLOWED_TEAM`. A PAT with `read:org` (classic) or
     "Members: Read-only" (fine-grained) scope; the default `GITHUB_TOKEN`
     can't read team membership.
   - `LITELLM_MODEL` (variable, optional) - overrides the default model
     if you don't want `generator.py`'s built-in default.

5. Commit `analyze.yml` (already done if you're reading this from the
   repo). Trigger it from the Actions tab, or:
   ```
   gh workflow run analyze.yml -f job_description="paste text, a repo-relative file path, or a URL here"
   ```

## Notes

- The `authorize` job fails (and skips the analysis job) for anyone not
  on the configured allow-list, but that failed run - and the fact that
  they tried - is still visible to anyone with repo read access, per the
  limitation above.
- `generate.sh` bootstraps a fresh Python venv and installs
  `requirements-test.txt` on every run since it has no cache between
  runs; expect the run to take a few minutes even for a quick analysis.
- The workflow writes a throwaway `.env` from the configured secrets at
  the start of the job and deletes it at the end (`if: always()`), so it
  doesn't persist in the checkout or get uploaded anywhere.