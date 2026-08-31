# Testing

## Test modules

Every module below lives under `tests/`. `conftest.py` is not a test
module itself; it defines shared fixtures used throughout the suite -
notably a hand-built `sample_kb`-style knowledge base fixture (see the
`_base_kb()` helper in `conftest.py`) with the same shape as
`profile.json`, plus fixtures that load the real `RESUME.template.md`,
`README.template.md`, and `ANALYSIS_PROMPT.template.txt` files from the
repository root so tests exercise the actual templates rather than
copies of them.

| Module | Covers |
|---|---|
| `test_analyze.py` | The `--analyze` job-fit-analysis feature end to end: context trimming, resolving `--analyze`'s value (text/file/URL), prompt building and validation, the LLM call (mocked, no network), and Markdown rendering. |
| `test_context_builders.py` | `build_baseline_context()`, `build_readme_context()`, and the prompt-builder functions that wrap them. |
| `test_helpers.py` | Small, pure helper functions in `generator.py` - `GENERATE_ALIASES`, `build_tagged_email()`, `strip_em_dashes()`, `extract_markdown()`, `extract_json_object()`, `render_filename()`, `_NowPlaceholder`, `ensure_parent_dir_exists()`, `compute_job_column_widths()`, `load_file_location_settings()`, and `build_llm_client()`. |
| `test_knowledge_base_url.py` | `KNOWLEDGE_BASE` being an `http(s)` URL instead of a local path: `fetch_knowledge_base_json()`, `load_knowledge_base()`, and how `main()` and `generate_profile_draft()` use them. |
| `test_llm_calls.py` | The three functions that drive a chat-completion call and validate/retry its output: `call_llm_fill_resume()`, `call_llm_cover_letter()`, and `call_llm_readme()`. The OpenAI-compatible client is mocked throughout - these tests never make a network call. |
| `test_main.py` | Integration tests for `main()`, with the LLM calls (`call_llm_fill_resume`, `call_llm_cover_letter`, `call_llm_readme`) and `build_llm_client` stubbed out - exercises everything `main()` does around them: reading the knowledge base and templates, creating the output directory, naming files, and calling every renderer, without a network call. |
| `test_output_repo.py` | `OUTPUT_REPO` and friends: checking generated files into a different git repository instead of this checkout. Covers `_inject_repo_token()`, `sync_output_repo()`, and `commit_and_push_output_repo()` directly, plus `main()`'s end-to-end wiring (LLM calls stubbed, same as `test_main.py`) using real local git repos, so clone/fetch/commit/push genuinely happen - no network involved, since a local path is a valid git remote. |
| `test_profile.py` | The `--generate profile` workflow: `build_source_file_list()`, `extract_text_from_source_file()`, `build_profile_prompt()`, `validate_profile_draft()`, `call_llm_update_profile()` (mocked client), and the `generate_profile_draft()` orchestrator (LLM call stubbed). |
| `test_readme_validation.py` | `validate_readme()`, the structural check run on the LLM's filled-in README before it is accepted (see `call_llm_readme()`). |
| `test_renderers.py` | The `render_*` functions: plain text, Markdown, DOCX, and PDF output for both the resume and the cover letter. |
| `test_resume_parsing.py` | `parse_filled_resume()`, which turns a filled-in `RESUME_TEMPLATE` back into the structured dict the renderers expect (see `build_resume_fill_prompt()` / `RESUME.template.md` for the expected shape). |

## Installing test dependencies

```bash
pip install -r requirements-test.txt
```

This also pulls in `requirements.txt`, so a single install gets you
everything needed to both run `generator.py` and run the test suite.
`./generate.sh` does this into a local `venv` automatically, so if you
are already using the wrapper you do not need this step separately.

## Why bare `pytest` is not a full test run here

This repo uses [pytest-testmon](https://testmon.org/), configured as
the default via `pytest.ini`:

```ini
[pytest]
addopts = --testmon
```

`addopts = --testmon` makes every bare `pytest` invocation use testmon
automatically, rather than something you have to remember to opt into.
Testmon tracks, per test, exactly which lines of code that test
executed (via `coverage.py` under the hood), and on the next run skips
any test whose tracked code - or the test file itself - is unchanged
since the last run. In practice, a plain `pytest` locally becomes "only
run what my last edit could plausibly have broken" instead of the full
suite every time.

A few things worth knowing:

* **First run ever** (no `.testmondata` yet) always runs everything -
  there is nothing to compare against. `.testmondata` (a local sqlite
  file, gitignored) is created and updated after every run.
* **`.testmondata` is per-machine, per-checkout state** - it is not
  committed, and switching branches or pulling changes you did not
  author locally can make testmon's picture stale relative to what is
  actually different. When in doubt, use `pytest --testmon-noselect`.
* **CI never uses selection.** `tests.yml` explicitly passes
  `--testmon-noselect`, so every push/PR always runs the complete suite
  with full coverage - the coverage percentage, badges, and PR comment
  all depend on that being true every time, and testmon's dependency
  tracking is a local convenience, not something CI correctness should
  rely on. See `09-automation-ci.md` for the rest of what `tests.yml`
  does (badge generation, PR comments, artifact uploads).

## Practical commands

| Command | What it does |
|---|---|
| `pytest` | Only tests affected by whatever you have changed since your last run. |
| `pytest tests/test_analyze.py` | Testmon selection still applies within an explicit path. |
| `pytest --testmon-noselect` | Force a full run (also refreshes testmon's tracked data). |
| `rm .testmondata` | Discard tracked state; the next `pytest` does a full run. |
| `pytest --testmon-noselect --cov=.` | A real local coverage check, matching what CI runs. |

## Gotcha: do not combine `--testmon` with `--cov`

Do not combine plain `--testmon` (selection mode - the default via
`addopts`) with `--cov` in the same local run. `--cov` then only
measures coverage from whatever subset of tests testmon actually ran,
which is both a misleadingly low number and, if testmon selects zero
tests (nothing changed since the last run), causes pytest-cov to print
"No data to report" warnings instead of a real report. For a real
local coverage check, use `pytest --testmon-noselect --cov=.` (the
same command CI runs), which forces the full suite while keeping
testmon's tracking data up to date.

## Writing new tests

Pick an existing test file with a shape similar to what you are
testing as a starting template - for example `test_renderers.py` for a
new renderer, or `test_helpers.py` for a small pure function - and
follow its fixture usage and mocking style. New test code is picked up
automatically by testmon on its next run; there is no extra setup
needed to make a new test file or test function tracked.
