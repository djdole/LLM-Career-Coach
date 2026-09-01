# LLM Career Coach Documentation

LLM Career Coach turns one structured knowledge base
(`data/profile.json`) into ready-to-send job application materials.
A single Python script, `generator.py`, reads that file and, through a
self-hosted LLM (a LiteLLM proxy in front of Ollama, or any other
OpenAI-compatible backend), fills in Markdown templates and renders
the result as resumes, cover letters, a GitHub profile README, and
job-fit analysis reports - in multiple formats, from one source of
truth. There is no paid API, no per-run cost, and no usage limit tied
to a hosted provider.

This folder is the full documentation for the project. The root
[`README.md`](../README.md) is a short landing page; everything below
is the detailed reference.

## Start here

New to this project? Read these two pages in order:

1. **[Overview](01-overview.md)** - what the project generates, how it
   works, and the high-level architecture of a generation run.
2. **[Setup](02-setup.md)** - prerequisites (Python 3.12, a LiteLLM
   proxy), first-time `.env` setup, and how to verify everything works.

## Reference

Once you are set up, these pages cover specific parts of the project
in depth:

| Page | Covers |
|---|---|
| [`03-configuration.md`](03-configuration.md) | The full `.env` / environment variable reference: LiteLLM connection settings, `VARIANTS`, output locations, `OUTPUT_REPO`, the knowledge base, `--analyze`'s prompt, and naming-template placeholders. |
| [`04-cli-usage.md`](04-cli-usage.md) | `generator.py`'s command-line flags: `--generate` and `--analyze`, every invocation shape, and common command examples. |
| [`05-generation-targets-and-outputs.md`](05-generation-targets-and-outputs.md) | What each `--generate` target (`resume`, `cover_letter`, `readme`, `profile`) and `--analyze` actually produce, in which formats, and the exact pipeline each one runs through. |
| [`06-templates.md`](06-templates.md) | The template files the project fills in: `RESUME.template.md`, `README.template.md`, and `ANALYSIS_PROMPT.template.txt` - what each placeholder means and what is safe to customize. |
| [`07-knowledge-base-schema.md`](07-knowledge-base-schema.md) | The full schema of `data/profile.json`: every top-level section, field, and how each one is used, plus an annotated example. |
| [`08-output-repository.md`](08-output-repository.md) | The `OUTPUT_REPO` workflow for checking generated resumes/cover letters/README into a separate git repository from this one. |
| [`09-automation-ci.md`](09-automation-ci.md) | The GitHub Actions workflows under `.github/workflows/`: automatic regeneration, the test suite, auto-PR creation, and the restricted `--analyze` workflow. |
| [`10-testing.md`](10-testing.md) | Running and understanding the test suite, including how `pytest-testmon` changes what a bare `pytest` run does. |
| [`11-code-reference.md`](11-code-reference.md) | A function-by-function reference for every function and class in `generator.py`, plus its module-level constants. |
| [`12-troubleshooting-faq.md`](12-troubleshooting-faq.md) | Common problems, their causes, and their fixes - start here if something isn't working. |

## Common tasks

A few jumping-off points for specific things you might be trying to do:

* **Just want it running?** [`02-setup.md`](02-setup.md), then the
  quick start in [`01-overview.md`](01-overview.md#quick-start).
* **Adding a new resume/cover-letter variant** (beyond the default
  `SDE`/`SDET`)? See `VARIANTS` in
  [`03-configuration.md`](03-configuration.md#resumecover-letter-variants).
* **Building `profile.json` from old resumes/notes instead of writing
  it by hand?** See `--generate profile` in
  [`05-generation-targets-and-outputs.md`](05-generation-targets-and-outputs.md#the-profile-target---generate-profile)
  and the `DATA` folder workflow.
* **Checking generated output into a different repo than this one?**
  See [`08-output-repository.md`](08-output-repository.md).
* **Trying `--analyze` against a sample posting?** The repository root
  includes `job_description.sample.txt` for exactly this:
  `python generator.py --analyze job_description.sample.txt`. See
  [`04-cli-usage.md`](04-cli-usage.md#--analyze-job_description).
* **Something's not working?** Check
  [`12-troubleshooting-faq.md`](12-troubleshooting-faq.md) first.

## Project conventions

A few things that hold true across every page in this folder:

* **All configuration is environment variables**, normally set via
  `.env` (copied from `.env.template`). There is no other config file
  or UI - see [`03-configuration.md`](03-configuration.md).
* **Everything is generated from `data/profile.json`.** No page in
  this documentation describes tailoring a resume to one specific job
  posting - that stays a separate, manual, chat-based workflow outside
  this script (see `profile.json`'s own `generation_workflow_for_llm`
  field). `--analyze` only evaluates fit against a posting; it does
  not rewrite anything.
* **This documentation is verified against the code, not assumed from
  comments.** Where a `.env.template` comment, a docstring, or another
  file's description turned out to be stale relative to what
  `generator.py` actually does, the page here says so explicitly
  rather than repeating the stale claim - see, for example, the notes
  on `--analyze`'s output in
  [`05-generation-targets-and-outputs.md`](05-generation-targets-and-outputs.md#output-formats).

## Contributing to this documentation

* Keep the full settings/flags tables in
  [`03-configuration.md`](03-configuration.md) and
  [`04-cli-usage.md`](04-cli-usage.md); other pages should
  cross-reference them rather than duplicate them.
* Use tables for anything that is a list of named settings, flags, or
  files with a value/description pair. Use hyphens (`-`), not em
  dashes, and `*`/`-` for bullet points.
* Keep code, file paths, and flags in backticks (for example
  `generator.py`, `.env`, `--generate`).
* When a claim in a comment, `.env.template`, or elsewhere in the repo
  turns out not to match what the code actually does, document the
  code's real behavior and note the discrepancy - don't silently
  repeat the stale claim.
* If a new page is added, link it both from the table above and from
  [`01-overview.md`](01-overview.md)'s "Other docs" section.
