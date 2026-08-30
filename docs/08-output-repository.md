# Checking Output Into a Separate Repository (`OUTPUT_REPO`)

## TODO Documentation Tasks

- Explain the default behavior first, as a baseline to contrast
  against: without `OUTPUT_REPO` set, `OUTPUT_FOLDER` and
  `README_OUTPUT` are written straight into this checkout, and it is
  on the user (or a CI workflow such as
  `.github/workflows/generate.yml`) to commit them.
- Explain what setting `OUTPUT_REPO` changes, as an ordered list of
  what happens on a run that generates a resume, cover letter, and/or
  README, reading `sync_output_repo()` and
  `commit_and_push_output_repo()` in `generator.py`:
  1. Clones `OUTPUT_REPO` into `OUTPUT_REPO_CLONE_DIR` - or, if already
     cloned there from a previous run, fetches and hard-resets that
     clone to match `origin` first, discarding any leftover
     uncommitted output from an interrupted previous run.
  2. Writes `OUTPUT_FOLDER` and `README_OUTPUT` inside that clone
     instead of inside the main checkout.
  3. Commits everything new under the clone, and pushes it unless
     `OUTPUT_REPO_PUSH` is `false`.
- Explicitly note that `KNOWLEDGE_BASE_DRAFT` is NOT affected by
  `OUTPUT_REPO` - it is the source-of-truth knowledge base everything
  else is generated from, not generated output, so it always stays
  local to the main checkout.
- Document each related variable, reading `.env.template`'s comments
  and `load_file_location_settings()` / `sync_output_repo()` in
  `generator.py` for exact behavior:
  - `OUTPUT_REPO` - accepts anything `git clone` accepts: an `https://`
    URL, an `ssh://`/`git@...` URL, or a local path. Unset means no
    change from default behavior.
  - `OUTPUT_REPO_BRANCH` - defaults to that repo's own default branch
    if unset.
  - `OUTPUT_REPO_TOKEN` - only used for an `https://` URL to a private
    repo; read `_inject_repo_token()` in `generator.py` to document
    exactly how it is embedded into the clone/fetch/push URL (HTTP
    Basic auth, works like a GitHub/GitLab personal access token used
    as the password with any non-empty username).
  - `OUTPUT_REPO_CLONE_DIR` - local folder the repo is cloned into and
    kept up to date in, default `.output-repo`, already covered by
    `.gitignore`.
  - `OUTPUT_REPO_AUTHOR_NAME` / `OUTPUT_REPO_AUTHOR_EMAIL` - commit
    identity used in `OUTPUT_REPO`, useful to set in CI where no
    global git identity may be configured.
  - `OUTPUT_REPO_COMMIT_MESSAGE` - a naming template (see
    `03-configuration.md`), though only its `{datetime.now}`-family
    placeholders make sense here since a commit is not per-variant.
  - `OUTPUT_REPO_PUSH` - set to `false` to only commit locally without
    skipping the commit itself, for example to review the diff before
    pushing.
- Add the example `.env` snippet from `USAGE.md` showing a minimal
  `OUTPUT_REPO` + `OUTPUT_REPO_TOKEN` setup.
- Add a short troubleshooting note: what happens if `OUTPUT_REPO` is
  unreachable, or if authentication fails - read `_run_git()` and
  `sync_output_repo()` for how errors surface, and describe the
  failure mode a user should expect to see.
