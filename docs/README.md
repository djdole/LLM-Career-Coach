# Documentation Instructions (for an LLM)

This `docs/` folder is a set of stub documentation files for the
LLM-Career-Coach project. Each stub file (every `.md` file in this
folder other than this one) contains a `## TODO Documentation Tasks`
section: a checklist of specific documentation work that still needs
to be written, with brief context on what code, file, feature,
prerequisite, or tool each item covers.

If you are an LLM being asked to work on one of these stub files,
follow the process below.

## Your task, given one stub file

1. **Read the whole stub file first**, including any content that is
   already populated (a stub may already have partial documentation
   above its TODO list from a previous pass).
2. **Read the source of truth for each TODO item.** TODO items point
   you at real files in the repository root (for example
   `generator.py`, `.env.template`, `USAGE.md`, `README.md`, files
   under `.github/workflows/`, files under `tests/`). Open and read
   those files rather than guessing at their contents. Where a TODO
   references a specific function name, search for that function in
   `generator.py` and read its full body, not just its signature.
3. **Write the documentation for human consumption.** Replace each
   completed TODO item with real, clear, well-organized prose,
   tables, and code samples as appropriate. Do not leave placeholder
   text like "TBD" or "coming soon" in the finished sections.
4. **Remove each TODO item from the list once it is fully documented.**
   If the TODO list becomes empty, remove the `## TODO Documentation
   Tasks` heading and the empty list entirely, since the file is
   complete. If only some items are done, leave the remaining items in
   place and only remove the ones you finished.
5. **Do not remove or weaken existing correct documentation.** If you
   find an existing sentence is inaccurate against the current code,
   correct it, but do not delete accurate content just to shorten the
   file.

## What "fully documented" means for this project

While populating a stub file, make sure the result:

* Organizes documentation cleanly, with a logical heading structure,
  short paragraphs, and tables where a table is clearer than prose
  (for example, config settings, CLI flags, file formats).
* Starts (in `01-overview.md` specifically, and briefly restated at
  the top of any file that stands alone) with a summary describing
  what the project is and what it does, so a reader landing on a
  single page still has orientation.
* Includes every config setting relevant to that file's topic: the
  environment variable name, its default value (or "required, no
  default"), and a clear description of what it does and how it is
  used. Cross-reference `03-configuration.md` rather than duplicating
  the full table elsewhere.
* Includes every `--flag`/option relevant to that file's topic,
  covering all of its distinct behaviors (for example, what happens
  when a flag is omitted vs. passed with no value vs. passed with a
  value). Cross-reference `04-cli-usage.md` rather than duplicating
  the full flag reference elsewhere.
* Includes any setup steps required for prerequisites (Python version,
  system packages, external services like a LiteLLM proxy or Ollama,
  accounts or tokens needed).
* Includes clear, step-by-step configuration steps a new user can
  follow without needing to read the source code themselves.
* As needed, creates any additional stub `.md` files for topics that
  turn out to deserve their own page, and populates their own
  `## TODO Documentation Tasks` list following the same format used in
  this folder (a bullet list, brief instructions, enough context for
  another LLM to pick up the task without re-reading the whole
  codebase from scratch). Add a link to any new file from
  `01-overview.md`'s table of contents section and from this file's
  file index below, if one is added.
* Uses hyphens instead of em dashes, and asterisks or hyphens for
  bullet points, never em dashes anywhere in the written documentation.

## Formatting rules

* No em dashes anywhere. Use a hyphen (`-`) instead.
* Bullet points use `*` or `-`, not em dashes and not numbered lists
  unless the content is genuinely sequential steps.
* Prefer tables for anything that is a list of named settings, flags,
  or files with a value/description pair.
* Keep code and file paths in backticks (for example `generator.py`,
  `.env`, `--generate`).
* Match the tone of the existing `README.md` and `USAGE.md` in the
  repository root: direct, technical, no marketing language.

## File index

* `01-overview.md` - project summary, what it generates, how it is
  built, high-level architecture.
* `02-setup.md` - prerequisites and first-time setup.
* `03-configuration.md` - full `.env` / environment variable reference.
* `04-cli-usage.md` - `generator.py` command-line flags and options.
* `05-generation-targets-and-outputs.md` - what `--generate` targets
  produce, in which formats, and where.
* `06-templates.md` - the Markdown/prompt templates the project fills
  in (`RESUME.template.md`, `README.template.md`,
  `ANALYSIS_PROMPT.template.txt`).
* `07-knowledge-base-schema.md` - the shape of `data/profile.json`.
* `08-output-repository.md` - the `OUTPUT_REPO` workflow for checking
  generated files into a separate repository.
* `09-automation-ci.md` - the GitHub Actions workflows under
  `.github/workflows/`.
* `10-testing.md` - running and understanding the test suite.
* `11-code-reference.md` - a function-by-function reference for
  `generator.py`.
* `12-troubleshooting-faq.md` - common problems and their causes.

When you add a new stub file, add it to this list too.
