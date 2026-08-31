# Checking Output Into a Separate Repository (`OUTPUT_REPO`)

## Default behavior (no `OUTPUT_REPO`)

Without `OUTPUT_REPO` set, `OUTPUT_FOLDER` and `README_OUTPUT` are
written straight into this checkout, exactly as if this feature did
not exist. It is then on you - or a CI workflow such as
`.github/workflows/generate.yml` - to commit and push those files.
This is the original behavior, and setting `OUTPUT_REPO` is opt-in on
top of it.

## What setting `OUTPUT_REPO` changes

When `OUTPUT_REPO` is set, every run that generates a resume, cover
letter, and/or README does the following instead, reading
`sync_output_repo()` and `commit_and_push_output_repo()` in
`generator.py`:

1. **Clones `OUTPUT_REPO` into `OUTPUT_REPO_CLONE_DIR`** - or, if
   already cloned there from a previous run, fetches `origin` and
   hard-resets that clone to match it first (`git reset --hard` plus
   `git clean -fd`), discarding any leftover uncommitted output from
   an interrupted previous run rather than layering new output on top
   of it. If the remote has no commits reachable yet (a brand new,
   still-empty `OUTPUT_REPO`, or a retry after a previous run crashed
   before ever pushing), there is nothing to reset to, and the clone
   is just cleaned of untracked leftovers instead.
2. **Writes `OUTPUT_FOLDER` and `README_OUTPUT` inside that clone**
   instead of inside this checkout.
3. **Commits everything new under the clone**, and pushes it unless
   `OUTPUT_REPO_PUSH` is `false`.

`KNOWLEDGE_BASE_DRAFT` is **not** affected by any of this. It is the
source-of-truth knowledge base everything else is generated *from*,
not generated output itself, so it always stays local to the main
checkout regardless of `OUTPUT_REPO`.

## Related variables

| Variable | Default | Purpose |
|---|---|---|
| `OUTPUT_REPO` | *(unset)* | Repo to check `OUTPUT_FOLDER` and `README_OUTPUT` into instead of this checkout. Unset means no change from default behavior. Accepts anything `git clone` accepts: an `https://` URL, an `ssh://`/`git@...` URL, or a local path. |
| `OUTPUT_REPO_BRANCH` | *(unset)* | Branch to check out/commit/push in `OUTPUT_REPO`. Defaults to that repo's own default branch if unset. |
| `OUTPUT_REPO_TOKEN` | *(unset)* | Only used when `OUTPUT_REPO` is an `https://` URL to a private repo. |
| `OUTPUT_REPO_CLONE_DIR` | `.output-repo` | Local folder the repo is cloned into, and kept up to date in on later runs. Already covered by `.gitignore` - it is its own separate git repo nested inside this one. |
| `OUTPUT_REPO_AUTHOR_NAME` / `OUTPUT_REPO_AUTHOR_EMAIL` | See note below | Commit author/committer identity used in `OUTPUT_REPO`. Set these if you would rather commits be attributed to a real account - useful in CI, where no global git identity may be configured. |
| `OUTPUT_REPO_COMMIT_MESSAGE` | `Regenerate resumes/cover letters ({datetime.now})` | Commit message for the `OUTPUT_REPO` commit. Also a naming template (see `03-configuration.md`), though only its `{datetime.now}`-family placeholders make sense here, since a commit is not per-resume-variant. |
| `OUTPUT_REPO_PUSH` | `true` in code (`.env.template` ships `"false"` explicitly) | Set to `false` to only commit locally in `OUTPUT_REPO_CLONE_DIR` - for example to review the diff yourself before pushing it on - without skipping the commit itself. |

Two variables are worth a closer look:

* **`OUTPUT_REPO_TOKEN`** - reading `_inject_repo_token()`, when set
  and `OUTPUT_REPO` is an `https://` URL, the token is embedded
  directly into the clone/fetch/push URL as an HTTP Basic auth
  credential: `https://<user-or-x-access-token>:<token>@host/...`.
  This works the same way a GitHub/GitLab personal access token used
  as the password does - any non-empty username is accepted, and
  `x-access-token` (GitHub's own convention) is used if
  `OUTPUT_REPO_USER` is not set. It has no effect on `ssh://` URLs or
  local paths, since there is no equivalent embedding for those - use
  your normal SSH key/`ssh-agent` setup instead.
* **`OUTPUT_REPO_AUTHOR_NAME`/`OUTPUT_REPO_AUTHOR_EMAIL`'s default
  differs by source.** If the environment variable is genuinely unset
  (no `.env` line at all), `load_file_location_settings()` in
  `generator.py` falls back to the original author's own identity,
  hardcoded in the code. The `.env.template` file that ships in this
  repo, however, explicitly sets both to `LLM-Career-Coach` /
  `LLM-Career-Coach@users.noreply.github.com`. Since setup instructs
  you to copy `.env.template` to `.env` (see `02-setup.md`), in
  practice you get the template's `LLM-Career-Coach` identity unless
  you change it - the code-level fallback only applies if that line is
  removed from your `.env` entirely.
* **`OUTPUT_REPO_PUSH`'s code default versus `.env.template`'s shipped
  value** - `load_file_location_settings()` in `generator.py` treats
  an unset `OUTPUT_REPO_PUSH` as `true`. The `.env.template` file that
  ships in this repo, however, explicitly sets
  `OUTPUT_REPO_PUSH="false"`. If you copy `.env.template` as-is, you
  get the template's `"false"` (commit only, no push) rather than the
  code's own `true` default - remove or change that line in your `.env`
  if you want pushes to happen automatically.

## Worked example

```bash
# .env
OUTPUT_REPO="https://github.com/YOUR_USERNAME/your-resumes.git"
OUTPUT_REPO_TOKEN="ghp_..."   # only needed if that repo is private
```

With this set, a run that generates a resume clones
`your-resumes.git` into `.output-repo/`, writes the resume files there
instead of into this checkout, and commits (and, since
`OUTPUT_REPO_PUSH` defaults to `true` in code, pushes) the result -
unless your `.env` still has the template's `OUTPUT_REPO_PUSH="false"`
line, in which case the commit happens locally in `.output-repo/` and
you push it yourself once you have reviewed it.

## Troubleshooting: unreachable repo or failed authentication

`_run_git()` raises a `RuntimeError` (folding in git's own stderr) on
any non-zero exit from a git command, so a problem here surfaces
clearly rather than silently no-op'ing - both `sync_output_repo()` and
`commit_and_push_output_repo()` let this propagate up to `main()`,
which prints it under an `[OUTPUT_REPO]` prefix and exits.

The likely underlying causes:

* A missing or invalid `OUTPUT_REPO_TOKEN` for a private `https://`
  repo - the clone, fetch, or push fails with an authentication error
  from git/the remote host.
* No `ssh-agent` or SSH key configured for an `ssh://` repo -
  `OUTPUT_REPO_TOKEN` does nothing for this URL scheme.
* `OUTPUT_REPO_CLONE_DIR` already exists on disk but is not a git
  clone - `sync_output_repo()` refuses to overwrite it outright and
  raises an error telling you to remove it, or point
  `OUTPUT_REPO_CLONE_DIR` somewhere else, and re-run.

See `12-troubleshooting-faq.md` for the same information in
symptom/cause/fix form.
