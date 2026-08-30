# Command-Line Usage

## TODO Documentation Tasks

- State that `python generator.py --help` is the authoritative,
  always-current source for flags, and that this page is a curated
  explanation on top of it. Read `build_arg_parser()` in
  `generator.py` (around line 139) to confirm current flag names,
  help text, and defaults before writing this page, since the CLI can
  change independently of `USAGE.md`.
- Document `--generate [TARGETS]` fully, as a table of invocations and
  effects:
  - Flag omitted entirely -> generates `resume` + `cover_letter` +
    `readme` (the default), unless `--analyze` was given and
    `--generate` was not, in which case only the analysis runs.
  - `--generate` with no value -> generates nothing.
  - `--generate resume` -> just resumes.
  - `--generate resume,cover_letter` -> comma-separated list in one
    occurrence.
  - `--generate resume --generate readme` -> repeated occurrences are
    unioned together.
  Also document: valid values (`resume`, `cover_letter` or
  `coverletter`, `readme`, `profile` or `resumedata`), that values are
  case-insensitive and `-`/`_` are interchangeable, that an
  unrecognized value exits with an error listing valid ones, and that
  `profile` is never included in the "omitted entirely" default since
  it is a separate, opt-in maintenance workflow. Source: `USAGE.md`'s
  `--generate` section and `parse_generate_targets()` in
  `generator.py` (around line 176).
- Document `--analyze JOB_DESCRIPTION` fully:
  - It runs independently of `--generate`; both can be passed in one
    invocation.
  - Its value is interpreted in this order: an `http://`/`https://`
    URL (fetched and reduced to plain text if the response looks like
    HTML), a path to an existing local file (text extracted from
    pdf/docx/txt/md/json/xml), or otherwise the literal value as
    pasted job description text. Source:
    `resolve_job_description()` in `generator.py` (around line 1470).
  - What it produces: a percentage fit estimate (0-100), a **separate**
    percentage per qualifications list if the posting splits them
    (for example "Required" vs. "Preferred"), a list of missing
    skills/qualifications, and suggested (preferably free) resources
    to close each gap.
  - Where the report goes: written to `OUTPUT_FOLDER` as
    `ANALYSIS_NAMING_TEMPLATE`, and also printed to stdout.
  - Give the three example invocations from `USAGE.md` (pasted text,
    local file path, URL).
- Document `-h` / `--help` briefly: standard argparse help listing
  both flags with their live descriptions.
- Add a "Common invocations" quick-reference table or list, for
  example: generate everything, generate only resumes, run only an
  analysis, generate resumes and run an analysis in one call, generate
  a knowledge-base draft from source documents (`--generate profile`,
  requires `DATA` to be set - cross-reference
  `05-generation-targets-and-outputs.md` for the profile workflow
  details).
