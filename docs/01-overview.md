# Project Overview

## Table of contents

* [Summary](#summary)
* [What it generates](#what-it-generates)
* [How it works](#how-it-works)
* [What this project does NOT do](#what-this-project-does-not-do)
* [Architecture: resume generation pipeline](#architecture-resume-generation-pipeline)
* [Quick start](#quick-start)
* [Other docs](#other-docs)
* [Full documentation index](#full-documentation-index)

## Summary

LLM Career Coach is a single Python script (`generator.py`) that turns
one structured knowledge base (`data/profile.json`) into ready-to-send
job application materials. It reads that knowledge base and, through a
self-hosted LLM reached via a LiteLLM proxy in front of Ollama (or any
other OpenAI-compatible backend), fills in Markdown templates and
renders resumes, cover letters, a GitHub profile README, and job-fit
analysis reports. Because everything is derived from one JSON file,
updating that file once and re-running the script regenerates every
output, in every format, consistently. There is no paid API, no
per-run cost, and no usage limit tied to a hosted provider.

## What it generates

| Target | Output | Files | Formats |
|---|---|---|---|
| Resume | One per configured position variant (`SDE`/`SDET` by default, but any number via `VARIANTS`) | 1 per variant | `pdf`, `docx`, `txt`, `md`, `json` (5) |
| Cover letter | Same variants as resumes | 1 per variant | `pdf`, `docx`, `txt` (3) |
| GitHub profile README | Filled in from the same knowledge base | 1 | `md` |
| Job-fit analysis | Given a job posting, estimates percentage fit, lists missing skills/qualifications, and suggests free resources to close the gaps | 1 | `md` (also printed to stdout) |
| Knowledge-base maintenance draft | Opt-in workflow that folds new source material (old resumes, notes, and so on) into `profile.json` itself, non-destructively | 1 | `json` |

See `05-generation-targets-and-outputs.md` for the full breakdown of
each target's pipeline and file naming.

## How it works

* **`data/profile.json` is the single source of truth.** Skills, work
  history, education, and reusable summary/cover-letter building
  blocks all live there once. Every generated document is derived from
  it rather than maintained by hand.
* **Position variants are configurable, not fixed to two.** `VARIANTS`
  (a JSON array in `.env`, `["SDE", "SDET"]` by default) controls which
  variants get generated. Add, remove, rename, or reorder however many
  you need, and each one gets its own resume and cover letter set,
  pulled from that variant's fields in `profile.json`.
* **Everything runs through a self-hosted LLM**, via a LiteLLM proxy in
  front of Ollama (or anything else OpenAI-compatible that LiteLLM can
  reach). Generation never spends API credits and never fails because
  of an account balance.
* **Templates drive the wording, naming templates drive the file
  layout.** `RESUME.template.md` and `README.template.md` control what
  gets written; `RESUME_NAMING_TEMPLATE` and `COVERLETTER_NAMING_TEMPLATE`
  control where output files land. Both are configurable via `.env`.
* **Output can be checked into a separate git repository.** Setting
  `OUTPUT_REPO` decouples this generator from wherever the actual
  resumes, cover letters, and README get committed: this repo clones
  that other repo, writes the generated files there, and commits (and
  optionally pushes) automatically. That is how this repo stays just
  the tool, while the generated documents live in their own repo. See
  `08-output-repository.md`.

## What this project does NOT do

Everything above is baseline content, not tailored to one specific job
posting. `--analyze` is the closest this tool comes to
posting-specific output, and it only evaluates fit against a posting;
it does not rewrite the resume for it. Tailoring a resume for a single
application is a separate, manual, chat-based process outside this
script - see `profile.json`'s own `generation_workflow_for_llm` field,
which describes that workflow.

## Architecture: resume generation pipeline

The resume target illustrates the general shape every target follows.
Reading `main()` in `generator.py` and the functions it calls, one
resume variant is produced like this:

1. Load `.env` settings (`load_file_location_settings()`).
2. Load the knowledge base (`load_knowledge_base()`).
3. Build an LLM client (`build_llm_client()`).
4. Build a fill-in prompt from the knowledge base and
   `RESUME_TEMPLATE` (`build_resume_fill_prompt()`).
5. Call the LLM to fill in the template (`call_llm_fill_resume()`).
6. Parse the filled sections back out of the model's response
   (`parse_filled_resume()`).
7. Render the parsed result to each output format - `txt`, `md`,
   `pdf`, `docx`, `json` (`render_resume_txt()`, `render_resume_md()`,
   `render_resume_pdf()`, `render_resume_docx()`, plus the JSON path in
   `main()`).
8. Write the rendered files to `OUTPUT_FOLDER` (or into the
   `OUTPUT_REPO` clone, if that is configured).

Cover letters, the README, the profile draft, and the job-fit analysis
each follow the same overall shape (build context, build prompt, call
the LLM, validate/parse, render, write), with their own prompt-builder
and renderer functions. See `05-generation-targets-and-outputs.md` for
each target's specific pipeline, and `11-code-reference.md` for a
function-by-function reference.

## Quick start

```bash
cp .env.template .env        # then fill in LITELLM_BASE_URL / LITELLM_API_KEY
python generator.py                       # generate resumes + cover letters + README
python generator.py --generate resume     # just resumes
python generator.py --analyze "paste a job description here"
```

Or use `./generate.sh`, which bootstraps a virtual environment and
installs dependencies for you on first run. See `02-setup.md` for the
full first-time setup walkthrough, including prerequisites and how to
verify a working setup.

## Other docs

This page intentionally keeps things high-level. For anything it does
not cover in full:

* Full `.env` / environment variable reference: `03-configuration.md`.
* `generator.py` command-line flags: `04-cli-usage.md`.
* Per-target pipelines and output formats: `05-generation-targets-and-outputs.md`.
* Template file formats: `06-templates.md`.
* `data/profile.json` schema: `07-knowledge-base-schema.md`.
* The root `README.md` remains a short, top-level project pointer;
  this `docs/` folder is the canonical, detailed documentation.

## Full documentation index

See `README.md` in this folder for the complete documentation index.
