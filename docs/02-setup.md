# Setup and Prerequisites

LLM Career Coach is a single Python script (`generator.py`) that turns
`data/profile.json` into resumes, cover letters, a GitHub profile
README, and job-fit analysis reports via a self-hosted LLM. This page
covers everything needed to get a fresh checkout to a first successful
run. See `01-overview.md` for what the project does, and
`03-configuration.md` for the full `.env` reference.

## Prerequisites

### Python 3.12

The project is pinned to Python 3.12 (see the `actions/setup-python`
step in `.github/workflows/tests.yml`). Check your version and install
it if needed:

```bash
python3 --version          # confirm 3.12.x
```

If you do not have 3.12 available, install it via your OS package
manager or [python.org](https://www.python.org/downloads/) before
continuing.

### Python packages

| Purpose | File | Packages |
|---|---|---|
| Running `generator.py` | `requirements.txt` | `openai`, `httpx`, `python-docx`, `reportlab`, `pypdf` |
| Running the test suite | `requirements-test.txt` (also pulls in `requirements.txt`) | `pytest`, `pytest-mock`, `pytest-cov`, `pytest-testmon`, `pydantic`, `requests`, `beautifulsoup4`, `genbadge` |

Install whichever set you need inside a virtual environment:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt          # or requirements-test.txt for testing
```

`./generate.sh` (see below) does this for you automatically, so a
manual venv is only needed if you want to run `python generator.py`
directly instead.

### A LiteLLM proxy in front of an LLM backend

This project never calls a paid hosted API. Instead it talks to a
[LiteLLM](https://docs.litellm.ai/) proxy, which is a lightweight
server that exposes an OpenAI-compatible API in front of one or more
LLM backends. That backend is typically
[Ollama](https://ollama.com/), a tool for running open-weight language
models locally, but LiteLLM can point at any OpenAI-compatible
backend.

You need a base URL and an API key for this proxy before `generator.py`
will run at all. `generator.py` exits immediately at startup if either
is unset (see `build_llm_client()`), printing:

```
LITELLM_BASE_URL and/or LITELLM_API_KEY are not set.
```

There is no default for either value; you must have a running LiteLLM
instance (self-hosted or otherwise) to point this project at.

## Two ways to run the tool

### Directly: `python generator.py`

After manually creating a virtual environment and installing
`requirements.txt` (see above), run the script directly:

```bash
python generator.py [flags]
```

Use this if you already manage your own virtual environment, or want
finer control over the Python environment the script runs in.

### Via the wrapper: `./generate.sh`

`./generate.sh [flags]` is a convenience wrapper (see `generate.sh` in
the repository root) that:

* On first run, creates `.env` from `.env.template` and exits, asking
  you to fill it in and rerun.
* On later runs, sources `.env`, builds (or reuses) a local `venv`,
  installs `requirements-test.txt` into it, and runs
  `python generator.py "$@"` - every argument you pass to
  `generate.sh` is forwarded to `generator.py` unchanged.

Use this if you want to get running without managing a virtual
environment yourself.

`generate.sh` also contains an auto-repair step: if it does not detect
the system Python components it expects, or if building the venv
fails, it attempts `sudo apt update && sudo apt install python3-full -y`
before retrying. This can surprise a user who does not expect a setup
script to call `sudo` - see `12-troubleshooting-faq.md` for what to do
if that step fails or is unavailable (for example in a restricted
environment or a system without `apt`).

## First-time `.env` setup

1. Copy `.env.template` to `.env`:
   ```bash
   cp .env.template .env
   ```
2. Open `.env` and fill in `LITELLM_BASE_URL` and `LITELLM_API_KEY` at
   minimum.
3. Every other setting in `.env.template` has a working default - see
   `03-configuration.md` for the full reference rather than repeating
   every variable here.
4. Run `./getModels.sh` to confirm which model strings are available
   at your configured `LITELLM_BASE_URL`. It sources `.env` and sends
   a `GET` request to the proxy's `/models` endpoint with your
   `LITELLM_API_KEY` as a bearer token, then prints the raw response
   (see `getModels.sh` for the exact request). Use one of the returned
   model strings to set `LITELLM_MODEL` in `.env` if the default
   (`qwen3.6:latest`) is not available on your proxy.

## The knowledge base

`data/profile.json` (or wherever `KNOWLEDGE_BASE` points, if you have
changed it) must exist with real content before generation produces
useful output. This file is not checked into the repository, since it
holds personal data. See `07-knowledge-base-schema.md` for its
structure, and `05-generation-targets-and-outputs.md` for the
`--generate profile` workflow, which can help build it from existing
documents (old resumes, notes, and so on) instead of writing it by
hand.

## Verifying your setup

Once `.env` is filled in and `data/profile.json` has content, confirm
everything works with a minimal run. Setting `VARIANTS` to a single
entry keeps the first run quick:

```bash
VARIANTS='["SDE"]' python generator.py --generate resume
```

or, using the wrapper:

```bash
VARIANTS='["SDE"]' ./generate.sh --generate resume
```

A successful run prints progress to the terminal and writes resume
files (`.pdf`, `.docx`, `.txt`, `.md`, `.json`) under `OUTPUT_FOLDER`
(`generated` by default). If the files appear there, your setup is
working and you can drop the `VARIANTS` override to generate your
normal set of variants.
