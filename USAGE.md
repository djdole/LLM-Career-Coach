# USAGE

## What this is

This project turns a single structured knowledge base
(`data/profile.json`) into ready-to-send job application materials,
using a self-hosted LiteLLM proxy (in front of Ollama) rather than a paid
hosted API - generation never spends API credits and never fails due to
account balance. Everything is driven by one script, `generator.py`:

- **Resumes** - two variants (SDE and SDET), each in 5 formats
  (pdf/docx/txt/md/json).
- **Cover letters** - one per variant, in 3 formats (pdf/docx/txt).
- **A GitHub profile README** - filled in from the same knowledge base.
- **A job-fit analysis** - given a job description (pasted text, a
  file, or a URL), estimates how well the candidate fits it, lists
  missing skills/qualifications, and suggests free resources to close
  the gaps.
- **Knowledge-base maintenance** - an opt-in workflow that folds new
  source documents (old resumes, notes, etc.) into `profile.json`
  itself via LiteLLM, non-destructively.

Everything the resume/cover letter/README generation reads is baseline,
not-tailored-to-a-specific-posting content. Tailoring a resume to one
specific job posting is a separate, manual, chat-based workflow (see
`profile.json`'s own `generation_workflow_for_llm` field) - this
script does not do that. `--analyze` is the closest thing to
posting-specific output this script produces, and it only *analyzes*
fit against a posting, it doesn't rewrite the resume for one.

---

## Setup

1. **Python 3.12** and the dependencies in `requirements.txt`
   (`openai`, `httpx`, `python-docx`, `reportlab`, `pypdf`).
2. **A LiteLLM proxy** in front of an LLM (self-hosted Ollama, or any
   OpenAI-compatible backend LiteLLM can reach) that you have a base URL
   and API key for.
3. Copy `.env.template` to `.env` and fill in your values - at minimum
   `LITELLM_BASE_URL` and `LITELLM_API_KEY`. Every other setting has a
   working default (see [Configuration](#configuration) below).
4. Run it:
   ```bash
   python generator.py                      # generate everything (default)
   python generator.py --generate resume     # just resumes
   python generator.py --analyze "job description text"
   ```

### `generate.sh`

A convenience wrapper that: creates `.env` from `.env.template` on first
run (and exits, asking you to fill it in and rerun); otherwise sources
`.env`, builds/reuses a local `venv`, installs `requirements-test.txt`
into it, and runs `python generator.py "$@"` - so `./generate.sh
--analyze "..."` works without you managing the venv yourself. Every
argument you pass to `generate.sh` is forwarded to `generator.py`
unchanged.

### `getModels.sh`

Sources `.env` and hits your LiteLLM proxy's `/models` endpoint, so you
can see which model strings are available to put in `LITELLM_MODEL`.

---

## Configuration

All configuration is environment variables, normally set via `.env`
(see `.env.template` for the full file with inline comments). Nothing
below has a UI or config file of its own - `.env` is the only source
of truth `generator.py` reads at startup.

### LiteLLM connection

| Variable | Default | Purpose |
|---|---|---|
| `LITELLM_BASE_URL` | *(required, no default)* | Your LiteLLM proxy's address, e.g. `https://litellm.example.com`. `generator.py` exits immediately if this or `LITELLM_API_KEY` is unset. |
| `LITELLM_API_KEY` | *(required, no default)* | The API key for that proxy (its `LITELLM_MASTER_KEY`, if self-hosted). |
| `LITELLM_MODEL` | `qwen3.6:latest` | The model string LiteLLM proxies to. Run `./getModels.sh` after setting the two above to see what's available. |
| `LITELLM_MAX_TOKENS` | `10000` | Max output tokens per LLM call. |
| `OLLAMA_NUM_CTX` | `16384` | Ollama context window size (input + output tokens). Lower this if your GPU can't hold the default for the model in use. |
| `LITELLM_TIMEOUT` | `550` (seconds) | How long to wait for a single LLM response before giving up on that attempt. Keep this comfortably *below* any reverse proxy's own read timeout in front of LiteLLM (e.g. nginx's `proxy_read_timeout`), or the proxy silently kills the connection first and this setting never gets to matter. |
| `LITELLM_KEEP_ALIVE` | `30m` | How long Ollama keeps the model loaded in VRAM after a request. A full run makes several sequential calls; keep this comfortably longer than a full run takes end to end so the model doesn't unload mid-run. Accepts a duration string (`30m`, `1h`) or a number of seconds. |

### Output locations

| Variable | Default | Purpose |
|---|---|---|
| `OUTPUT_FOLDER` | `generated` | Where resume/cover letter files are written. |
| `README_TEMPLATE` | `README.template.md` | Template `--generate readme` fills in. |
| `README_OUTPUT` | `README.md` | Where the filled-in README is written (repo root, so it renders as the GitHub profile README). |
| `EMAIL_TAG_ADDRESS` | `""` | Optional "plus addressing" tag (RFC 5233 subaddressing -- Gmail/Outlook/etc. honor it) applied to the README's email **mailto: link only**. The email address as *displayed* on the page is never changed. E.g. with this set to `resume` and `personal_info.email` = `jane@example.com`, the page still shows `jane@example.com`, but the link behind it is `mailto:jane+resume@example.com` -- so you can tell whether a reply came from someone who found you via the README. Leave blank (the default) for no tag at all. |
| `RESUME_TEMPLATE` | `RESUME.template.md` | Template `--generate resume` fills in. |
| `RESUME_NAMING_TEMPLATE` | `{FirstName} {LastName} Resume ({JobAcronym}).{Extension}` | Output filename pattern for resumes. `{FirstName}`/`{LastName}` come from `personal_info.full_name` in the knowledge base (middle name/initial dropped); `{JobAcronym}` is the variant (`SDE`/`SDET`); `{Extension}` is the output format. |
| `COVERLETTER_NAMING_TEMPLATE` | `{FirstName} {LastName} Cover Letter ({JobAcronym}).{Extension}` | Same, for cover letters. |

### Knowledge base

| Variable | Default | Purpose |
|---|---|---|
| `KNOWLEDGE_BASE` | `data/profile.json` | Where every generation target reads the knowledge base from. Can be a local path (original behavior) **or an http(s) URL** - e.g. a raw file URL into a private repo - to pull it from somewhere other than this checkout. |
| `KNOWLEDGE_BASE_URL_TOKEN` | *(unset)* | Only used when `KNOWLEDGE_BASE` is a URL pointing at a private source. Sent as `Authorization: token <value>` (GitHub's convention - works for both `api.github.com` and `raw.githubusercontent.com` with a personal access token). Leave unset for a public URL. |
| `KNOWLEDGE_BASE_DRAFT` | `data/profile.json` | Where `--generate profile` writes its output. Defaults to the *same path* as `KNOWLEDGE_BASE`, so by default a successful run overwrites the knowledge base directly - set this to a different path if you'd rather review the draft before promoting it yourself. Always a local path, even when `KNOWLEDGE_BASE` is a URL (there's no way to push a draft back to an arbitrary URL - promoting it back to that source is a manual step). |
| `DATA` | *(unset)* | Folder `--generate profile` reads source documents from (pdf/txt/json/xml/docx). Not used by any other target. If unset, `--generate profile` is a no-op. |

**A note on "non-destructive"** for `--generate profile`: it means
the merge is *structure-preserving* - no top-level section present in
the existing knowledge base is allowed to disappear from the draft.
It does **not** mean your original file is left untouched on disk:
with the default settings, the draft is written right back over
`KNOWLEDGE_BASE`. Point `KNOWLEDGE_BASE_DRAFT` somewhere else if you
want a review step first.

### `--analyze`'s prompt

| Variable | Default | Purpose |
|---|---|---|
| `ANALYSIS_PROMPT_TEMPLATE` | `ANALYSIS_PROMPT.template.txt` | The LLM prompt `--analyze` uses, as a `string.Template` file with `$output_rules`/`$candidate_data`/`$job_description` placeholders. Edit this file directly to change how the analysis is framed - no Python changes needed. |

---

## `--flags`

Run `python generator.py --help` for the authoritative, always-current
list. Summary:

### `--generate [TARGETS]`

Controls what to build this run. Repeatable, with an optional value:

| Invocation | Effect |
|---|---|
| *(flag omitted entirely)* | Generates `resume` + `cover_letter` + `readme` (the default) - **unless** `--analyze` was given and `--generate` was not, in which case nothing from `--generate` runs and the invocation does only the analysis. |
| `--generate` *(no value)* | Generates nothing. |
| `--generate resume` | Just resumes. |
| `--generate resume,cover_letter` | Comma-separated list in one occurrence. |
| `--generate resume --generate readme` | Repeated occurrences are unioned together - equivalent to `--generate resume,readme`. |

Valid values: `resume`, `cover_letter` (or `coverletter`), `readme`,
`profile` (or `resumedata`). Values are case-insensitive and
`-`/`_` are interchangeable. An unrecognized value exits with an error
listing the valid ones.

`profile` is **never** included in the "omitted entirely" default --
it's a separate, opt-in maintenance workflow (see
[Knowledge base](#knowledge-base) above and `generate_profile_draft()`
in `generator.py`), not something that should run just because you ran
the script with no flags.

### `--analyze JOB_DESCRIPTION`

Runs a job-fit analysis, independent of `--generate` - pass both to do
both in one invocation. Its value **is** the job description itself,
interpreted in this order:

1. An `http://` or `https://` URL - fetched, and reduced to plain text
   if the response looks like HTML.
2. A path to an existing local file - text extracted from it
   (pdf/docx/txt/md/json/xml all supported).
3. Otherwise, the value itself: job description text pasted directly on
   the command line.

```bash
python generator.py --analyze "paste the job description here"
python generator.py --analyze path/to/job_posting.pdf
python generator.py --analyze https://example.com/careers/some-job
```

Uses `KNOWLEDGE_BASE` plus LiteLLM to:

- Estimate percentage fit (0-100). If the posting separates its
  qualifications into more than one distinct list (e.g. "Required
  Qualifications" vs. "Preferred Qualifications"), a **separate**
  percentage is produced per list instead of one overall number.
- List skills/qualifications the posting calls for that aren't present
  in the knowledge base.
- Suggest (preferably free) courses/tutorials/books/docs to close each
  gap.

The report is written to `OUTPUT_FOLDER` (as `ANALYSIS_NAMING_TEMPLATE`)
and also printed to stdout.

### `-h` / `--help`

Standard argparse help, listing both flags above with their current
descriptions.

---

## Output formats

| Target | Files per variant | Formats |
|---|---|---|
| `resume` | 1 per variant (SDE, SDET) | `.json`, `.txt`, `.md`, `.pdf`, `.docx` (5) |
| `cover_letter` | 1 per variant (SDE, SDET) | `.txt`, `.pdf`, `.docx` (3) |
| `readme` | 1 | `.md`, written to `README_OUTPUT` (repo root by default) |
| `profile` | 1 | `.json`, written to `KNOWLEDGE_BASE_DRAFT` |
| `analyze` | 1 | `.md`, written to `OUTPUT_FOLDER`, and also printed to stdout |

---

## Running tests

`pytest` alone (no flags) only runs tests affected by whatever you've
changed since your last run - **not** the full suite. This is
[pytest-testmon](https://testmon.org/): it tracks, per test, exactly
which lines of code that test executed, and on the next run skips any
test whose tracked code (and the test file itself) is unchanged. It's
configured as the default in `pytest.ini` (`addopts = --testmon`) so you
don't have to remember to opt in.

```bash
pytest                       # only tests affected by your latest changes
pytest tests/test_analyze.py # testmon selection still applies within an explicit path
pytest --testmon-noselect    # force a full run (also refreshes testmon's data)
rm .testmondata               # discard tracked state; the next `pytest` does a full run
```

A few things worth knowing:

- **First run ever** (no `.testmondata` yet) always runs everything --
  there's nothing to compare against. `.testmondata` (a local sqlite
  file, gitignored) is created/updated after every run.
- **`.testmondata` is per-machine, per-checkout state** - it's not
  committed, and switching branches or pulling changes you didn't
  author locally can make testmon's picture stale relative to what's
  actually different. When in doubt, `pytest --testmon-noselect`.
- **CI never uses selection.** `tests.yml` explicitly passes
  `--testmon-noselect`, so every push/PR always runs the complete suite
  with full coverage - the coverage %, badges, and PR comment all
  depend on that being true every time, and testmon's dependency
  tracking is a local convenience, not something CI correctness should
  rely on.
- Don't combine plain `--testmon` (selection mode) with `--cov` in the
  same local run: `--cov` then only measures coverage from whatever
  subset of tests testmon actually ran, which is both a misleadingly
  low number and, if testmon selects zero tests (nothing changed since
  last run), pytest-cov prints "No data to report" warnings instead of
  a real report. For a real local coverage check, use
  `pytest --testmon-noselect --cov=.` (the same command CI runs),
  which forces the full suite while keeping testmon's tracking data
  up to date.

---

## Automation (optional)

This repo also ships a few GitHub Actions workflows under
`.github/workflows/`, none of which are required to use `generator.py`
locally:

- **`generate.yml`** - regenerates baseline resumes/cover letter and
  opens a PR whenever `data/profile.json` changes on `main`.
- **`analyze.yml`** - a manually-triggered, access-restricted
  `--analyze` run; see `.github/workflows/README-analyze-setup.md` for
  what it does and doesn't restrict, and the one-time setup it needs.
- **`tests.yml`** - runs the test suite (`pytest`) on push/PR.

These are independent of running `generator.py` directly and require
their own repo secrets/variables (`LITELLM_BASE_URL`, `LITELLM_API_KEY`,
`LITELLM_MODEL`) configured in Settings -> Secrets and variables ->
Actions - see the comments at the top of each workflow file.