# Testing

## TODO Documentation Tasks

- List the test modules under `tests/` with a one-line description of
  what each covers, read from the test file names and their contents:
  `test_analyze.py`, `test_context_builders.py`, `test_helpers.py`,
  `test_knowledge_base_url.py`, `test_llm_calls.py`, `test_main.py`,
  `test_output_repo.py`, `test_profile.py`,
  `test_readme_validation.py`, `test_renderers.py`,
  `test_resume_parsing.py`. Skim each file's test function names to
  summarize what behavior it locks in, and mention `conftest.py`'s
  role (shared fixtures) if it defines any worth calling out.
- Explain how to install test dependencies:
  `pip install -r requirements-test.txt` (which also pulls in
  `requirements.txt`), or via `./generate.sh`, which does this into a
  local `venv` automatically.
- Explain `pytest-testmon` and why bare `pytest` is not a full test
  run in this repo, reading the comments in `pytest.ini`:
  - `addopts = --testmon` in `pytest.ini` makes every bare `pytest`
    invocation use testmon.
  - Testmon tracks, per test, exactly which lines of code that test
    executed (via coverage.py), and on the next run skips any test
    whose tracked code (or the test file itself) is unchanged.
  - First run ever (no `.testmondata` yet) always runs everything -
    there is nothing to compare against yet;`.testmondata` (a local,
    gitignored sqlite file) is created/updated after every run.
  - `.testmondata` is per-machine, per-checkout state, not committed -
    switching branches or pulling changes you did not author locally
    can make its picture stale.
- Document the practical commands, as a table or list:
  - `pytest` - only tests affected by the latest changes.
  - `pytest tests/test_analyze.py` - testmon selection still applies
    even within an explicit path.
  - `pytest --testmon-noselect` - force a full run (also refreshes
    testmon's data).
  - `rm .testmondata` - discard tracked state; the next `pytest` does
    a full run.
  - `pytest --testmon-noselect --cov=.` - the real local coverage
    check, matching what CI runs.
- Explain why CI (`tests.yml`) always passes `--testmon-noselect`:
  every push/PR must run the complete suite with full coverage, since
  the coverage percentage, badges, and PR comment all depend on that
  being true every time - testmon's dependency tracking is a local
  convenience only, not something CI correctness should rely on.
  Cross-reference `09-automation-ci.md` for the rest of what
  `tests.yml` does (badge generation, PR comments, artifact uploads)
  instead of repeating it here.
- Document the one documented gotcha: do not combine plain `--testmon`
  (selection mode) with `--cov` in the same local run, since `--cov`
  then only measures coverage from whatever subset of tests testmon
  actually ran (a misleadingly low number), and if testmon selects
  zero tests, pytest-cov prints "No data to report" warnings instead
  of a real report.
- Add a short "writing new tests" note: point to an existing test file
  with a similar shape as a starting template, and mention that new
  test code automatically gets tracked by testmon on its next run with
  no extra setup needed.
