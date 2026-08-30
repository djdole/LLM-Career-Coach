# Setup and Prerequisites

## TODO Documentation Tasks

- Document the prerequisites, with install/verify steps for each:
  - Python 3.12 (this is the version pinned in
    `.github/workflows/tests.yml`'s `actions/setup-python` step and
    referenced in `USAGE.md`'s Setup section).
  - The Python packages in `requirements.txt`
    (`openai`, `httpx`, `python-docx`, `reportlab`, `pypdf`) and, for
    running tests, the additional packages in `requirements-test.txt`
    (`pytest`, `pytest-mock`, `pytest-cov`, `pytest-testmon`,
    `pydantic`, `requests`, `beautifulsoup4`, `genbadge`).
  - A LiteLLM proxy in front of an LLM backend (self-hosted Ollama, or
    any OpenAI-compatible backend LiteLLM can reach). Explain what
    LiteLLM and Ollama are in one sentence each for a reader unfamiliar
    with either, and link to their upstream docs. Note that a base URL
    and API key for this proxy are required, with no default, and that
    `generator.py` exits immediately at startup if either is unset
    (see `build_llm_client()` in `generator.py`).
- Document the two ways to run the tool and when to use each, reading
  `generate.sh` and the "Quick start" / "`generate.sh`" sections of
  `USAGE.md`:
  - Directly: `python generator.py [flags]` after manually creating a
    virtual environment and installing `requirements.txt`.
  - Via the wrapper: `./generate.sh [flags]`, which on first run
    creates `.env` from `.env.template` and exits asking you to fill
    it in, and on later runs sources `.env`, builds/reuses a local
    `venv`, installs `requirements-test.txt` into it, and runs
    `python generator.py "$@"` (forwarding every argument unchanged).
    Note the auto-repair behavior in `generate.sh` that checks for
    missing system Python components and attempts
    `sudo apt install python3-full` if the venv fails to build, since
    this could surprise a user expecting no `sudo` calls.
- Document first-time `.env` setup as ordered steps:
  1. Copy `.env.template` to `.env`.
  2. Fill in `LITELLM_BASE_URL` and `LITELLM_API_KEY` at minimum.
  3. Note that every other setting has a working default (link to
     `03-configuration.md` rather than repeating the full table here).
  4. Run `./getModels.sh` (after setup) to confirm which model strings
     are available at the configured `LITELLM_BASE_URL`, and explain
     what it does: sources `.env` and does a `GET` against the proxy's
     `/models` endpoint (read `getModels.sh` directly for the exact
     request).
- Document that `data/profile.json` (or wherever `KNOWLEDGE_BASE`
  points) must exist with real content before generation produces
  useful output, and cross-reference `07-knowledge-base-schema.md` for
  its structure, and `05-generation-targets-and-outputs.md` for the
  `--generate profile` workflow that can help build it from existing
  documents.
- Add a "Verifying your setup" section: a minimal first command to run
  (for example `python generator.py --generate resume` with a single
  `VARIANTS` entry) and what a successful run looks like (files
  appearing under `OUTPUT_FOLDER`).
