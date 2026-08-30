# Troubleshooting and FAQ

## TODO Documentation Tasks

- Document the immediate-exit case when `LITELLM_BASE_URL` or
  `LITELLM_API_KEY` is unset: read `build_llm_client()` in
  `generator.py` for the exact error message/exit behavior, and
  explain the fix (fill in `.env` from `.env.template`).
- Document what happens with an invalid `VARIANTS` value (not valid
  JSON, or not an array of strings): read `parse_variants_env()` for
  the exact error message and exit behavior.
- Document the LiteLLM/reverse-proxy timeout interaction described in
  `.env.template` and `USAGE.md`: symptoms of `LITELLM_TIMEOUT` being
  set higher than a reverse proxy's own read timeout (for example
  nginx's `proxy_read_timeout`) in front of LiteLLM - the proxy kills
  the connection first and the setting never gets a chance to matter.
  Explain how to recognize this failure mode and how to fix it.
- Document the `LITELLM_KEEP_ALIVE` / model-unload scenario: what a
  user would observe if the model unloads mid-run (a slow subsequent
  call paying a full model-load penalty) and how raising
  `LITELLM_KEEP_ALIVE` addresses it.
- Document `--generate profile` being a silent no-op when `DATA` is
  unset - a common point of confusion since no error is raised. Read
  `generate_profile_draft()` / `build_source_file_list()` to confirm
  the exact no-op condition and document it precisely.
- Document `generate.sh`'s auto-repair behavior around missing system
  Python components (it may attempt `sudo apt update && sudo apt
  install python3-full -y`) as something a user might not expect, and
  what to do if that step fails in a restricted environment (create
  the venv and install `requirements-test.txt` manually instead).
- Document `OUTPUT_REPO` authentication failures: read `_run_git()`
  and `sync_output_repo()` in `generator.py` for how a failed
  clone/fetch/push surfaces, and give the likely causes (missing/
  invalid `OUTPUT_REPO_TOKEN` for a private `https://` repo, no
  `ssh-agent`/key configured for an `ssh://` repo).
- Document what an unrecognized `--generate` value does (exits with an
  error listing valid values) - read `parse_generate_targets()` for
  the exact message.
- Document `validate_readme()` / `validate_profile_draft()` /
  `validate_job_fit_analysis()` failure cases: what triggers each
  validator to reject an LLM response, and what the user-facing error
  looks like, so a user seeing a generation failure partway through
  can tell whether it was a validation failure versus a network/LLM
  failure. Read each validator function for its specific checks.
- Add a short "the LLM's output looks wrong" section: since this
  project runs against a self-hosted/local model rather than a large
  hosted one, output quality and JSON-formatting reliability can vary
  more - link back to `06-templates.md` and
  `05-generation-targets-and-outputs.md` for where prompts are built,
  in case a user wants to adjust wording themselves.
- Add entries as new issues are discovered; keep each entry short:
  symptom, cause, fix.
