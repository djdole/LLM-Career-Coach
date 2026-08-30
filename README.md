[![Tests](https://github.com/djdole/LLM-Career-Coach/actions/workflows/tests.yml/badge.svg)](https://github.com/djdole/LLM-Career-Coach/actions/workflows/tests.yml)
[![Coverage](https://raw.githubusercontent.com/djdole/LLM-Career-Coach/main/badges/coverage-badge.svg)](https://github.com/djdole/LLM-Career-Coach/actions/workflows/tests.yml)
[![Tests Passing](https://raw.githubusercontent.com/djdole/LLM-Career-Coach/main/badges/tests-badge.svg)](https://github.com/djdole/LLM-Career-Coach/actions/workflows/tests.yml)

---

# LLM Career Coach

**One structured knowledge base in → tailored resumes, cover letters, a
GitHub profile README, and job-fit analysis out.** A single Python
script (`generator.py`) reads `data/profile.json` and, through a
self-hosted LLM (LiteLLM in front of Ollama, or any OpenAI-compatible
backend), fills in Markdown templates and renders the results as
PDF/DOCX/TXT/MD/JSON - so updating one JSON file regenerates every
job-application document, in every format, consistently. No paid API,
no per-run cost, no usage limits.

---

## What it generates

| Target | Output |
|---|---|
| **Resumes** | One per configured position variant (`SDE`/`SDET` by default, but any number of variants - see `VARIANTS` below) × 5 formats each (`pdf`, `docx`, `txt`, `md`, `json`) |
| **Cover letters** | Same variants as resumes × 3 formats (`pdf`, `docx`, `txt`) |
| **GitHub profile README** | 1 Markdown file, filled in from the same knowledge base |
| **Job-fit analysis** | Given a job posting (pasted text, a file, or a URL), estimates percentage fit, lists missing skills/qualifications, and suggests free resources to close the gaps |
| **Knowledge-base maintenance** | An opt-in workflow that folds new source material (old resumes, notes, etc.) into `profile.json` itself, non-destructively |

Everything above is baseline content, not tailored to one specific job
posting - `--analyze` is the closest this tool comes to
posting-specific output, and it only evaluates fit, it doesn't rewrite
the resume. Tailoring a resume for a single application is a separate,
manual, chat-based process outside this script.

## How it works

- **`data/profile.json` is the single source of truth.** Skills, work
  history, education, and reusable summary/cover-letter building
  blocks all live there once; every generated document is derived from
  it, not maintained by hand.
- **Position variants are configurable, not fixed to two.** `VARIANTS`
  (a JSON array in `.env`, `["SDE", "SDET"]` by default) controls which
  variants get generated - add, remove, rename, or reorder however
  many you need, and each one gets its own tailored resume and cover
  letter set, pulled from that variant's fields in `profile.json`.
  Quoting each entry means a variant name can contain spaces, e.g.
  `["Product Manager", "HR Admin"]`.
- **Everything runs through a self-hosted LLM**, via a LiteLLM proxy in
  front of Ollama (or anything else OpenAI-compatible LiteLLM can
  reach). Generation never spends API credits and never fails because
  of an account balance.
- **Templates drive the wording**, naming templates drive the file
  layout - both fully configurable via `.env` (see `.env.template`).
- **Output can be checked into a different repository entirely.**
  Setting `OUTPUT_REPO` decouples this generator from wherever the
  actual resumes/cover letters/README get committed: this repo clones
  that other repo, writes the generated files there, and commits (and
  optionally pushes) automatically. That's how this repo stays just
  the tool, while the generated documents themselves live in their own
  repo.

## Quick start

```bash
cp .env.template .env        # then fill in LITELLM_BASE_URL / LITELLM_API_KEY
python generator.py                       # generate resumes + cover letters + README
python generator.py --generate resume     # just resumes
python generator.py --analyze "paste a job description here"
```

Or use `./generate.sh`, which bootstraps a venv and installs
dependencies for you on first run.

## Automation

GitHub Actions workflows under `.github/workflows/` can regenerate
output automatically whenever `data/profile.json` changes, and keep
the test suite/coverage badges above up to date - see `USAGE.md` for
details. None of it is required to run this locally.

## Learn more

Full configuration reference, every `.env` variable, naming-template
placeholders, `--analyze` details, and the test suite are documented
in [`USAGE.md`](./USAGE.md).
