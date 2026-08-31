# Command-Line Usage

`python generator.py --help` is the authoritative, always-current
source for flags - this page is a curated explanation on top of it.
The CLI can change independently of `USAGE.md` and this page, so if
something here looks stale, `--help` (backed by `build_arg_parser()`
in `generator.py`) wins.

`generator.py` takes two flags, `--generate` and `--analyze`, plus the
standard `-h`/`--help`. They are independent of each other and can be
combined in a single invocation.

## `--generate [TARGETS]`

Controls what to build this run. It is repeatable, and its value is
optional.

| Invocation | Effect |
|---|---|
| *(flag omitted entirely)* | Generates `resume` + `cover_letter` + `readme` (the default) - **unless** `--analyze` was given and `--generate` was not, in which case nothing from `--generate` runs and the invocation does only the analysis. |
| `--generate` *(no value)* | Generates nothing. |
| `--generate resume` | Just resumes. |
| `--generate resume,cover_letter` | Comma-separated list in one occurrence. |
| `--generate resume --generate readme` | Repeated occurrences are unioned together - equivalent to `--generate resume,readme`. |

Valid values: `resume`, `cover_letter` (or `coverletter`), `readme`,
`profile` (or `resumedata`). Values are case-insensitive and `-`/`_`
are interchangeable - `Cover-Letter` and `cover_letter` both resolve to
the same target. An unrecognized value exits with an error listing the
valid canonical values, for example:

```
Unknown --generate value: 'resum'. Valid values: cover_letter, profile, readme, resume.
```

`profile` is never included in the "omitted entirely" default. It is a
separate, opt-in maintenance workflow (see
`05-generation-targets-and-outputs.md` and `generate_profile_draft()`
in `generator.py`), not something that should run just because you ran
the script with no flags.

## `--analyze JOB_DESCRIPTION`

Runs a job-fit analysis, independent of `--generate` - pass both to do
both in one invocation. Its value **is** the job description itself,
interpreted in this order (see `resolve_job_description()` in
`generator.py`):

1. An `http://` or `https://` URL - fetched, and reduced to plain text
   if the response looks like HTML.
2. A path to an existing local file - text extracted from it
   (`pdf`/`docx`/`txt`/`md`/`json`/`xml` all supported).
3. Otherwise, the value itself: job description text pasted directly
   on the command line.

```bash
python generator.py --analyze "paste the job description here"
python generator.py --analyze path/to/job_posting.pdf
python generator.py --analyze https://example.com/careers/some-job
```

Uses `KNOWLEDGE_BASE` plus LiteLLM to:

* Estimate percentage fit (0-100). If the posting separates its
  qualifications into more than one distinct list (for example
  "Required Qualifications" vs. "Preferred Qualifications"), a
  **separate** percentage is produced per list instead of one overall
  number.
* List skills/qualifications the posting calls for that are not
  present in the knowledge base.
* Suggest (preferably free) courses, tutorials, books, or docs to close
  each gap.

**Where the report goes:** the rendered report is printed to stdout.
Despite `.env.template` and the root `USAGE.md` describing an
`ANALYSIS_NAMING_TEMPLATE`-named file under `OUTPUT_FOLDER` as an
additional destination, reading `main()` in `generator.py` shows the
current code never writes the analysis report to disk - only
`print(rendered_job_fit_analysis_report)` runs. If you want to save a
report, redirect stdout yourself:

```bash
python generator.py --analyze "..." > "Job Fit Analysis.md"
```

See `12-troubleshooting-faq.md` and `03-configuration.md` for more on
this discrepancy.

## `-h` / `--help`

Standard argparse help, listing both flags above with their current
descriptions and defaults, straight from `build_arg_parser()`.

## Common invocations

| Goal | Command |
|---|---|
| Generate everything (default) | `python generator.py` |
| Generate only resumes | `python generator.py --generate resume` |
| Generate only cover letters | `python generator.py --generate cover_letter` |
| Generate resumes and the README, but not cover letters | `python generator.py --generate resume,readme` |
| Run only a job-fit analysis | `python generator.py --analyze "paste a job description"` |
| Generate everything and analyze a posting in one run | `python generator.py --generate resume,cover_letter,readme --analyze "paste a job description"` |
| Build/update the knowledge base from source documents | `python generator.py --generate profile` (requires `DATA` to be set - see `05-generation-targets-and-outputs.md` for the full `--generate profile` workflow) |
