# Automation (GitHub Actions)

## TODO Documentation Tasks

- State upfront that none of the workflows under `.github/workflows/`
  are required to run `generator.py` locally - they are optional
  automation on top of it.
- Document `tests.yml` (runs on push to any branch and on PRs to
  `main`): what it does step by step (install `requirements-test.txt`,
  run `pytest -q --testmon-noselect --cov=. ...`, publish JUnit test
  results, upload an HTML coverage report artifact, post a coverage
  summary to the job summary and as a PR comment, and on pushes,
  regenerate `badges/coverage-badge.svg` and `badges/tests-badge.svg`
  via `genbadge` and auto-commit them). Explain why it always passes
  `--testmon-noselect` even though local `pytest` defaults to
  testmon-selected runs - cross-reference `10-testing.md` for the full
  testmon explanation instead of repeating it here.
- Document `generate.yml`: triggers on a push to `main` that touches
  `data/profile.json` (note this only fires for a **local**
  `KNOWLEDGE_BASE` at its default path - a URL-based `KNOWLEDGE_BASE`
  would need a different trigger), plus a manual
  `workflow_dispatch`. Explain what it does: installs
  `requirements.txt`, runs `python generator.py` with every setting
  from `03-configuration.md` sourced from repo/org secrets or
  variables (falling back to the defaults baked into the workflow
  file if neither is set), then opens a pull request with the
  regenerated files via `peter-evans/create-pull-request`. List which
  secrets/variables must be configured in
  Settings > Secrets and variables > Actions for this to work
  end to end (at minimum `LITELLM_BASE_URL`, `LITELLM_API_KEY`,
  `LITELLM_MODEL`, and `OUTPUT_REPO`-related ones if used).
- Document `auto-pr.yml`: triggers on push to any branch except
  `main`, and opens a pull request back to `main` if one doesn't
  already exist for that branch, using the `PAT_TOKEN` secret and
  `gh pr create`. Note the labels it applies
  (`auto-generated,needs-review`).
- Document `analyze.yml.disabled` and its companion
  `.github/workflows/README-analyze-setup.md` as a pair:
  - Explain why it ships disabled (the `.disabled` suffix makes GitHub
    Actions ignore it entirely) and that it must not be renamed live
    until the setup steps are done.
  - Summarize the four layers of restriction it relies on (repository
    access, workflow execution protections/actor rules, environment
    required reviewers, the in-workflow `authorize` job's allow-list
    check) and which of those GitHub actually enforces versus which is
    defense-in-depth. Be explicit that GitHub has no per-workflow
    visibility control - anyone with repository read access can see
    every workflow's run history and logs.
  - Walk through the one-time setup steps from
    `README-analyze-setup.md` in order (repository access, environment
    protection with required reviewers, allow-list variables/secrets,
    enabling the workflow, optional actor-rule restriction, and how to
    trigger it via `gh workflow run analyze.yml -f job_description=...`).
  - Note operational details: it writes a throwaway `.env` from
    configured secrets at the start of the job and deletes it at the
    end (`if: always()`), and that `generate.sh` bootstraps a fresh
    venv on every run with no cache, so expect the run to take a few
    minutes even for a quick analysis.
- Add a summary table at the top of this file: workflow file name,
  trigger, one-line purpose, whether it is enabled by default.
