# Troubleshooting and FAQ

Short, symptom-first entries for problems you might hit running
`generator.py`. Each entry lists the symptom, the cause, and the fix.
For flag and config reference, see `04-cli-usage.md` and
`03-configuration.md`.

## `LITELLM_BASE_URL` and/or `LITELLM_API_KEY` are not set

**Symptom:** The script exits immediately, before any generation
happens, printing:

```
LITELLM_BASE_URL and/or LITELLM_API_KEY are not set.
```

**Cause:** `build_llm_client()` requires both `LITELLM_BASE_URL` and
`LITELLM_API_KEY` to be set with no default for either. If either is
missing, the script exits with status 1 rather than attempting a
request that would fail later with a less clear error.

**Fix:** Copy `.env.template` to `.env` if you have not already, and
fill in both values. See `02-setup.md` for first-time setup.

## `VARIANTS must be a JSON array of strings`

**Symptom:** The script exits at startup with an error like:

```
VARIANTS must be a JSON array of strings, e.g. ["SDE", "SDET"] -- got: '<your value>'
```

**Cause:** `parse_variants_env()` requires `VARIANTS` to be valid JSON
and a JSON array whose elements are all strings. A bare comma-separated
list, invalid JSON, or an array containing a non-string value all fail
this check and exit immediately rather than being silently ignored or
crashing later mid-run.

**Fix:** Set `VARIANTS` to a JSON array of strings, wrapped in single
quotes in `.env` (since the JSON syntax itself uses double quotes),
for example:

```bash
VARIANTS='["SDE", "SDET"]'
```

## LLM calls time out or the connection drops before `LITELLM_TIMEOUT` is reached

**Symptom:** A generation run fails partway through with a connection
error, even though `LITELLM_TIMEOUT` is set high enough that the model
should have had time to respond.

**Cause:** If LiteLLM sits behind a reverse proxy (for example nginx),
that proxy has its own read timeout (nginx's `proxy_read_timeout`, for
example). If that timeout is shorter than `LITELLM_TIMEOUT`, the proxy
kills the connection first and `LITELLM_TIMEOUT` never gets the chance
to matter - the failure looks like a network error rather than a clean
timeout message.

**Fix:** Keep `LITELLM_TIMEOUT` comfortably below any reverse proxy's
own read timeout in front of LiteLLM, not above it. If generation
routinely needs more time than that (for example with a large
`LITELLM_MAX_TOKENS` or `OLLAMA_NUM_CTX` on slow hardware), raise the
reverse proxy's timeout to match, rather than only raising
`LITELLM_TIMEOUT`.

## A run partway through is slow, as if the model is loading from scratch

**Symptom:** The first LLM call in a run is fast, but a later call in
the same run is unusually slow - as slow as if the model were loading
for the first time.

**Cause:** A full run makes several sequential LLM calls. Ollama
unloads a model from VRAM after `LITELLM_KEEP_ALIVE` of inactivity. If
that value is too short relative to how long a full run takes end to
end, the model can unload between calls, and the next call pays a full
model-load penalty on top of normal generation time.

**Fix:** Raise `LITELLM_KEEP_ALIVE` (a duration string like `30m`/`1h`,
or a number of seconds) to comfortably exceed how long a full run
takes on your hardware, so the model stays loaded for the whole run.

## `--generate profile` does nothing

**Symptom:** Running `python generator.py --generate profile` exits
cleanly with no error, but no draft knowledge base is written.

**Cause:** This is by design, not a bug, and the script does not raise
an error for it. `generate_profile_draft()` short-circuits with no
output in either of these cases:

* `DATA` is not set at all. `--generate profile` reads source
  documents from the folder `DATA` points at; without `DATA`, there is
  nowhere to read from, and the script prints
  `[profile] DATA is not set; skipping.` to stderr and returns.
* `DATA` is set, but `build_source_file_list()` finds no usable source
  files in it - the folder does not exist, or every file in it is
  either hidden, the knowledge base file itself, or a pre-existing
  draft (excluded so a leftover draft is never re-consumed as if it
  were new source material).

**Fix:** Set `DATA` to a folder containing real source documents
(pdf/txt/json/xml/docx) before running `--generate profile`, and make
sure at least one non-hidden file in that folder is not the knowledge
base or a stale draft.

## `generate.sh` runs `sudo apt install` without asking

**Symptom:** Running `./generate.sh` for the first time prompts for a
`sudo` password, or attempts to install system packages, which you may
not expect from a script that is "just" running a Python tool.

**Cause:** `generate.sh` has an auto-repair step: if it does not detect
the system Python components it expects (or if building the venv
fails), it attempts `sudo apt update && sudo apt install python3-full -y`
before retrying.

**Fix:** This is expected behavior on a Debian/Ubuntu-style system
with `sudo` access. If you are in a restricted environment where `sudo`
is unavailable or undesired (for example a container without `apt`, or
a system without root access), skip `generate.sh` and set up the
virtual environment yourself instead:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements-test.txt
python generator.py [flags]
```

## `OUTPUT_REPO` clone, fetch, or push fails

**Symptom:** A run using `OUTPUT_REPO` fails with an error mentioning
`git clone`, `git fetch`, or `git push`, including the underlying
git error message.

**Cause:** `_run_git()` raises a `RuntimeError` (including git's own
stderr) on any non-zero exit from a git command, so an `OUTPUT_REPO`
problem surfaces clearly instead of failing silently. `sync_output_repo()`
and `commit_and_push_output_repo()` are the two places this can happen.
The most likely underlying causes are:

* A missing or invalid `OUTPUT_REPO_TOKEN` for a private `https://`
  repo. `OUTPUT_REPO_TOKEN` is only used for `https://` URLs; it is
  embedded as an HTTP Basic auth credential.
* No `ssh-agent` or SSH key configured for an `ssh://` repo -
  `OUTPUT_REPO_TOKEN` has no effect on `ssh://` URLs, since there is no
  equivalent embedding for them.
* `OUTPUT_REPO_CLONE_DIR` already exists on disk but is not a git
  clone - `sync_output_repo()` refuses to overwrite it and asks you to
  remove it or point `OUTPUT_REPO_CLONE_DIR` elsewhere.

**Fix:** Confirm the token/SSH setup matches the URL scheme you are
using for `OUTPUT_REPO`, and check `OUTPUT_REPO_CLONE_DIR` for a
leftover non-git directory. See `08-output-repository.md` for the full
`OUTPUT_REPO` workflow.

## Unknown `--generate` value

**Symptom:** The script exits with an error like:

```
Unknown --generate value: '<your value>'. Valid values: cover_letter, profile, readme, resume.
```

**Cause:** `parse_generate_targets()` only recognizes `resume`,
`cover_letter` (or `coverletter`), `readme`, and `profile` (or
`resumedata`), case-insensitively, with `-`/`_` treated as
interchangeable. Anything else exits immediately with this message
rather than being silently ignored.

**Fix:** Check the value passed to `--generate` against the valid
list above. See `04-cli-usage.md` for the full `--generate` reference.

## A generation run fails with a validation error

**Symptom:** A run fails partway through with an error describing a
missing section, an unfilled placeholder, or a malformed value, rather
than a network or connection error.

**Cause:** This project validates the LLM's output before writing it,
so a malformed or incomplete response fails clearly instead of
producing a broken file. The relevant validators are:

* `validate_readme()` - the README is missing its top-level `# `
  heading, is missing a required section, still contains an unfilled
  `{{placeholder}}` token, contains an em dash (`never_use_em_dash`),
  or has the wrong number of `### ` job entries compared to what the
  knowledge base expects.
* `validate_profile_draft()` - the draft is not a JSON object, is
  missing one of `personal_info`, `education`, `skills`, or
  `work_experience`, or (when updating an existing knowledge base)
  dropped a top-level section that must be preserved non-destructively.
* `validate_job_fit_analysis()` - the analysis JSON is missing a
  required key, `overall_summary` is empty, `fit_assessments` is empty
  or malformed, a `fit_percentage` is out of the 0-100 range or not a
  number, or `upskill_resources` is malformed.

Each validator's failure triggers a corrective retry against the LLM
inside the corresponding `call_llm_*` function, so a single bad
response does not necessarily fail the whole run - only a validation
failure that persists across retries does.

**Fix:** If a validation failure persists, it usually means the
configured model is not reliably following the template's formatting
instructions. See the next entry.

## The LLM's output looks wrong

Since this project runs against a self-hosted or local model rather
than a large hosted one, output quality and JSON-formatting
reliability can vary more than they would against a frontier hosted
model - a smaller or lower-quality model is more likely to drop a
section, misformat JSON, or ignore a formatting instruction like
"never use an em dash." If output consistently looks wrong for one
target:

* Try a larger or higher-quality model via `LITELLM_MODEL` (see
  `./getModels.sh` to list what is available on your proxy).
* Review and adjust the relevant prompt-building function or template
  directly - see `06-templates.md` for the template files themselves
  and `05-generation-targets-and-outputs.md` for where each target's
  prompt is built in `generator.py`.

## Adding new entries

Add new entries to this page as new issues are discovered. Keep each
entry short: symptom, cause, fix.
