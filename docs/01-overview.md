# Project Overview

## TODO Documentation Tasks

- Write a short summary (3-6 sentences) describing LLM-Career-Coach:
  a single Python script (`generator.py`) that reads a structured
  knowledge base (`data/profile.json`) and, through a self-hosted
  LLM reached via a LiteLLM proxy in front of Ollama (or any
  OpenAI-compatible backend), fills in Markdown templates and renders
  resumes, cover letters, a GitHub profile README, and job-fit
  analysis reports. Base this on the repository root `README.md`'s
  intro section and the "What this is" section of `USAGE.md`.
- Add a "What it generates" table listing each output target
  (resume, cover letter, GitHub profile README, job-fit analysis,
  knowledge-base maintenance draft), how many files it produces, and
  in which formats. Source: the "What it generates" table in the root
  `README.md` and the "Output formats" table in `USAGE.md`.
- Add a "How it works" section covering these key ideas, each as its
  own short paragraph or bullet:
  - `data/profile.json` is the single source of truth that every
    output is derived from.
  - Position variants (`VARIANTS`) are configurable, not fixed to two.
  - Everything runs through a self-hosted LLM via LiteLLM, so there is
    no per-run API cost.
  - Templates (`RESUME.template.md`, `README.template.md`) drive the
    wording, and naming templates (`RESUME_NAMING_TEMPLATE`, etc.)
    drive the output file layout, both configurable via `.env`.
  - Output can optionally be checked into a separate git repository
    via `OUTPUT_REPO`, decoupling this tool from wherever generated
    resumes actually live.
  Source: the "How it works" section of the root `README.md`.
- Add an explicit "What this project does NOT do" callout: baseline
  content is not tailored to one specific job posting; `--analyze`
  only evaluates fit against a posting, it does not rewrite the resume
  for it. Mention that `profile.json`'s own `generation_workflow_for_llm`
  field describes the separate, manual, chat-based tailoring workflow
  that is outside this script's scope.
- Add a high-level architecture diagram or ordered list showing the
  pipeline for one generation target, for example resume generation:
  load `.env` settings -> load knowledge base -> build an LLM client
  -> build a fill-in prompt from the knowledge base and template ->
  call the LLM -> parse the filled sections -> render to each output
  format (txt/md/pdf/docx/json) -> write to `OUTPUT_FOLDER` (or
  `OUTPUT_REPO`). Base this on reading `generator.py`'s `main()`
  function and the functions it calls for one target end to end.
- Add a "Quick start" section with the minimal command sequence to go
  from a fresh checkout to a first successful run. Source: the "Quick
  start" section of the root `README.md` and the "Setup" section of
  `USAGE.md`.
- Add a table of contents at the top of this file linking to every
  other file in `docs/` (see the file index in `docs/README.md`).
- Link to the upstream project repository/README for anything this
  overview intentionally does not repeat in full (for example, the
  full config reference lives in `03-configuration.md`, not here).
