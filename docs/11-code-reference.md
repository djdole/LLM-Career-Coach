# Code Reference (`generator.py`)

A function-by-function reference for `generator.py` (roughly 2200
lines, single-file script), grouped in the order functions appear in
the file.

## CLI and argument parsing

### `build_arg_parser()`

Builds and returns the `argparse.ArgumentParser` for `--generate` and
`--analyze`. `--generate` is defined with `action="append"`,
`nargs="?"`, `const=""`, so it can be omitted, passed with no value, or
passed (repeatedly) with a comma-separated value. `--analyze` is a
plain string flag. No side effects; `python generator.py --help` shows
this parser's live help text, which is the authoritative source for
current flag descriptions.

### `parse_generate_targets(raw_values)`

**Parameters:** `raw_values` - the raw list argparse collected for
`--generate` (one string per occurrence, `""` for a valueless
occurrence). **Returns:** a `set` of canonical target names (`"resume"`,
`"cover_letter"`, `"readme"`, `"profile"`). Splits each occurrence on
commas, normalizes each token (lowercased, `-`/`_` stripped), and maps
it through `GENERATE_ALIASES`. **Side effect:** prints an error and
calls `sys.exit(1)` if any token does not match a known alias. A lone
valueless `--generate` yields an empty set (interpreted by `main()` as
"generate nothing," not the default).

## LLM client setup

### `build_llm_client()`

**Parameters:** none (reads `LITELLM_BASE_URL`/`LITELLM_API_KEY` from
the environment). **Returns:** an `openai.OpenAI` client pointed at
`LITELLM_BASE_URL.rstrip("/") + "/v1"`. **Side effect:** if either
environment variable is unset, prints
`LITELLM_BASE_URL and/or LITELLM_API_KEY are not set.` to stderr and
calls `sys.exit(1)` - this is the exit every other run-time function
assumes has already happened, since one client is built once per run
and reused for every LLM call.

## Resume generation

### `compute_job_column_widths(work_experience, body_pt, total_pt, min_title_pt=130)`

**Parameters:** the resume's work-experience list, the body font size,
the total usable width in points, and a floor for the title column.
**Returns:** a `(title_pt, employer_pt, date_pt)` tuple. Measures the
longest actual company name and date range in this resume (using
reportlab's Helvetica-Bold metrics as a stand-in font for both PDF and
DOCX rendering) so the employer and date columns get exactly what they
need, with the title column getting whatever space is left over,
floored at `min_title_pt`. No side effects.

### `strip_em_dashes(text)`

**Parameters:** any string. **Returns:** the same string with every em
dash character replaced by a comma. A belt-and-suspenders fallback
behind the `never_use_em_dash` rule given to the model - not a
substitute for the model actually following it. No side effects.

### `build_baseline_context(kb, variant)`

**Parameters:** the full knowledge base dict, and the current variant
name (for example `"SDE"`). **Returns:** a trimmed dict containing only
what one variant's baseline resume/cover-letter prompt needs: output
rules, personal info, education (renamed to the output schema's field
names), the variant's summary (falling back to `"SDE"`), skills with
pre-formatted category labels, and work experience with per-variant
job titles and `_alt`/`_variant`-suffixed bullets filtered out.
Trimming exists both for token budget and to keep JD-tailoring-only
fields out of the model's view. No side effects.

### `build_resume_fill_prompt(kb, variant, template_text)`

**Parameters:** the knowledge base, the variant, and `RESUME_TEMPLATE`'s
text. **Returns:** the full system-prompt string sent to the LLM,
combining instructions (preserve structure and exact `" | "`
delimiters, follow output rules), the template text, and the trimmed
context as JSON. No side effects.

### `parse_filled_resume(text)`

**Parameters:** the LLM's filled-in template text. **Returns:** a
structured dict (`name`, `contact_line`, `skills_heading`, `summary`,
`skills`, `work_experience`, `education`) matching what the renderers
expect. Walks the text line by line expecting an exact structure
(name, contact line, `SUMMARY` block, skills lines, `WORK EXPERIENCE`
header, one job block per job with an optional team-context line and
`●`-prefixed bullets, `EDUCATION` header, pipe-delimited education
lines). **Side effect:** raises `ValueError` (not caught here) on any
structural mismatch, which the caller uses to trigger a retry.

### `call_llm_fill_resume(client, kb, variant, template_text)`

**Parameters:** the shared LLM client, knowledge base, variant, and
template text. **Returns:** the parsed resume dict from
`parse_filled_resume()`. Sends the prompt from
`build_resume_fill_prompt()`, extracts Markdown fencing if present via
`extract_markdown()`, parses the result, and checks the job count
matches the knowledge base. **Side effects:** makes a network call to
LiteLLM; retries once with a corrective follow-up message on a parse
failure or job-count mismatch; prints progress/error messages to
stderr; calls `sys.exit(1)` on a connection error, an API error
response, or two consecutive failed attempts.

### `extract_json_object(raw)`

**Parameters:** a raw LLM response string that may have prose or
markdown fences around a JSON object. **Returns:** the substring from
the first `{` to its matching balanced `}`, tracking brace depth as it
scans. **Side effect:** raises `ValueError` if no `{` is found, or if
no balanced closing `}` is found.

## Cover letter generation

### `build_cover_letter_prompt(kb, variant)`

**Parameters:** the knowledge base and variant. **Returns:** a system
prompt asking the model to lightly adapt
`cover_letter_generic_template` (from `cover_letter_building_blocks`)
and respond with `{"body": "..."}` JSON only. No side effects.

### `call_llm_cover_letter(client, kb, variant)`

**Parameters:** the shared client, knowledge base, and variant.
**Returns:** the parsed cover letter dict (`{"body": ...}`). Requests
JSON mode from LiteLLM where supported, falling back to a plain
request if the proxy rejects the `response_format` parameter
(`openai.BadRequestError`). **Side effects:** network call; retries
once on invalid JSON or a missing `"body"` key; prints progress/error
messages to stderr; exits on connection/API errors or two failed
attempts.

## Rendering (text/Markdown/DOCX/PDF)

### `render_resume_txt(r)` / `render_resume_md(r)`

**Parameters:** the parsed resume dict. **Returns:** the resume
rendered as plain text or Markdown respectively, with em dashes
stripped via `strip_em_dashes()`. No side effects (pure string
building).

### `render_cover_letter_txt(cl)` / `render_cover_letter_md(cl)`

**Parameters:** the parsed cover letter dict. **Returns:** `cl["body"]`
with em dashes stripped. `render_cover_letter_md()` exists but is never
called from `main()` - see `05-generation-targets-and-outputs.md`. No
side effects.

### `_tight(paragraph, space_after=2, space_before=0)`

**Parameters:** a `python-docx` paragraph object and spacing overrides.
**Returns:** the same paragraph, after setting its `space_after`/
`space_before` formatting in points. Used throughout `render_resume_docx()`
to keep paragraph spacing compact. Mutates the paragraph in place.

### `render_resume_docx(r, path, body_pt=10.5)`

**Parameters:** the parsed resume dict, the output path, and the base
body font size. **Returns:** `None`. Builds a full `python-docx`
document (name/contact header, SUMMARY, skills, a bordered heading
style, a three-column table per job sized via
`compute_job_column_widths()`, bulleted job bullets, education) and
saves it. **Side effect:** writes a `.docx` file to `path`.

### `render_cover_letter_docx(cl, path)`

**Parameters:** the parsed cover letter dict and output path.
**Returns:** `None`. Splits the body on blank lines into paragraphs and
writes a plain `python-docx` document. **Side effect:** writes a
`.docx` file to `path`.

### `_build_resume_story(r, tier)`

**Parameters:** the parsed resume dict and one entry from `PDF_TIERS`
(a `(body_pt, leading, bullet_space_after, margin_in, name_pt,
heading_pt)` tuple). **Returns:** a list of reportlab flowables (a
"story") representing the whole resume at that font-size tier, reusing
`compute_job_column_widths()` for the work-experience table. No side
effects - this is the shared builder both `render_resume_pdf()` calls
per attempted tier.

### `render_resume_pdf(r, path, max_pages=2)`

**Parameters:** the parsed resume dict, output path, and a page-count
ceiling. **Returns:** a `(pages, body_pt)` tuple for the tier that was
ultimately used. Tries each tier in `PDF_TIERS` (largest font first),
building and writing the PDF at each tier, stopping at the first tier
that fits within `max_pages` - or falling through to the smallest tier
if none fit. **Side effect:** writes a `.pdf` file to `path` (possibly
rewritten once per tier tried).

### `render_cover_letter_pdf(cl, path)`

**Parameters:** the parsed cover letter dict and output path.
**Returns:** `None`. Builds a simple reportlab document, one paragraph
per blank-line-separated block of the body. **Side effect:** writes a
`.pdf` file to `path`.

## GitHub profile README generation

### `build_tagged_email(email, tag_address)`

**Parameters:** the plain email address and an optional plus-address
tag. **Returns:** `local+tag@domain` if `tag_address` is non-blank and
`email` looks like a single-`@` address, otherwise `email` unchanged.
No side effects.

### `build_readme_context(kb)`

**Parameters:** the full knowledge base. **Returns:** a trimmed,
variant-agnostic (always `"SDE"`-based) context for the README prompt,
including `personal_info.email_mailto` (via `build_tagged_email()`)
alongside the unmodified `personal_info.email`, plus README-only
fields like `field_of_study` and `career_highlights`. No side effects.

### `build_readme_system_prompt(kb, template_text)`

**Parameters:** the knowledge base and `README_TEMPLATE`'s text.
**Returns:** the full system prompt, with explicit instructions to
reproduce `career_highlights` verbatim and to never swap or merge the
`email`/`email_mailto` fields. No side effects.

### `extract_markdown(raw)`

**Parameters:** a raw LLM response. **Returns:** the response with a
single wrapping ` ``` ` fence (and optional language tag) stripped, if
the model wrapped the whole document in one despite being told not to.
No side effects.

### `validate_readme(md, expected_job_count)`

**Parameters:** the candidate README Markdown and the number of jobs
the knowledge base has. **Returns:** `None` on success. **Side
effect:** raises `ValueError` if the top-level `# ` heading is
missing, a required section header is missing, an unfilled
`{{placeholder}}` remains, an em dash is present, or the number of
`### ` job headers does not match `expected_job_count`.

### `call_llm_readme(client, kb, template_text)`

**Parameters:** the shared client, knowledge base, and template text.
**Returns:** the validated README Markdown string. **Side effects:**
network call; retries once on a `validate_readme()` failure; prints
progress/error messages to stderr; exits on connection/API errors or
two failed attempts.

## Knowledge base maintenance (`--generate profile`)

### `extract_text_from_source_file(path)`

**Parameters:** a path to a candidate source file. **Returns:**
extracted plain text - read directly for `.json`/`.txt`/`.md`/`.xml`,
via `python-docx` (paragraphs plus pipe-joined table rows) for
`.docx`, via `pypdf`'s per-page extraction for `.pdf`. **Side effect:**
prints a message to stderr and returns `""` for an unsupported
extension or any read error, rather than raising, so one bad file
does not abort the batch.

### `build_source_file_list(data_dir, knowledge_base_path, draft_path)`

**Parameters:** the `DATA` folder, the resolved local knowledge-base
path (or `None` if `KNOWLEDGE_BASE` is a URL), and the resolved draft
output path. **Returns:** a sorted list of candidate source file
paths - every regular, non-hidden file in `data_dir`'s immediate
contents except the knowledge base file itself and the draft path.
Returns `[]` if `data_dir` does not exist. No side effects.

### `build_profile_prompt(existing_kb, source_texts)`

**Parameters:** the existing knowledge base dict (or `None` for a
from-scratch build) and a `{filename: text}` dict of extracted source
text. **Returns:** the system prompt for `call_llm_update_profile()`,
branching on whether `existing_kb` is `None` (build-from-scratch
instructions) or a dict (explicit non-destructive update
instructions - only add or modify, never remove or shorten). No side
effects.

### `validate_profile_draft(data, existing_kb)`

**Parameters:** the candidate draft dict and the existing knowledge
base (or `None`). **Returns:** `None` on success. **Side effect:**
raises `ValueError` if `data` is not a dict, is missing one of
`personal_info`/`education`/`skills`/`work_experience`, or (when
`existing_kb` is given) drops a top-level key that existed there.

### `call_llm_update_profile(client, existing_kb, source_texts)`

**Parameters:** the shared client, existing knowledge base (or
`None`), and source texts. **Returns:** the validated draft dict.
**Side effects:** network call; retries once on invalid JSON or a
`validate_profile_draft()` failure; prints progress/error messages to
stderr; exits on connection/API errors or two failed attempts.

### `fetch_knowledge_base_json(url)`

**Parameters:** a `KNOWLEDGE_BASE` URL. **Returns:** the parsed JSON
response body. Sends `KNOWLEDGE_BASE_URL_TOKEN` as an
`Authorization: token <value>` header if set. **Side effects:** makes
an HTTP GET request; raises `ValueError` (wrapping the underlying
error) on a connection failure, non-2xx status, or invalid JSON body.

### `load_knowledge_base(location)`

**Parameters:** the `KNOWLEDGE_BASE` setting (path or URL). **Returns:**
the parsed knowledge base dict - via `fetch_knowledge_base_json()` for
an `http(s)://` value, or a plain local JSON read otherwise. **Side
effects:** whatever the chosen path implies (network call, or a local
file read that can raise `FileNotFoundError`/`json.JSONDecodeError`).

### `generate_profile_draft(client, s)`

**Parameters:** the shared client and the full settings dict from
`load_file_location_settings()`. **Returns:** `None`. Orchestrates the
whole `--generate profile` workflow: no-ops if `DATA` is unset or has
no usable source files; otherwise reads the existing knowledge base
(if any), extracts text from every source file, calls
`call_llm_update_profile()`, writes the result to
`KNOWLEDGE_BASE_DRAFT`, and deletes every consumed source file. **Side
effects:** reads and deletes files under `DATA`; writes the draft
file; makes an LLM call (via the functions above); prints progress
messages to stderr/stdout; can call `sys.exit(1)` if reading an
existing local `KNOWLEDGE_BASE` fails.

## Job-fit analysis (`--analyze`)

### `_strip_html(markup)`

**Parameters:** raw HTML text. **Returns:** a best-effort plain-text
reduction - `<script>`/`<style>` blocks removed, remaining tags
stripped, entities unescaped, excess whitespace collapsed. Not a real
HTML parser; just enough to avoid adding a dependency. No side
effects.

### `_fetch_job_description_from_url(url)`

**Parameters:** a URL passed to `--analyze`. **Returns:** the fetched
text - reduced via `_strip_html()` if the response looks like HTML,
otherwise the raw body. **Side effects:** makes an HTTP GET request;
raises `ValueError` (wrapping the underlying error) on any connection,
timeout, or non-2xx-status failure.

### `resolve_job_description(raw)`

**Parameters:** `--analyze`'s raw CLI value. **Returns:** the resolved
job description text, interpreted in order as a URL, an existing local
file path (via `extract_text_from_source_file()`), or the literal
value. **Side effects:** may make a network call or read a local file;
raises `ValueError` if the result is empty in any of the three cases.

### `build_job_fit_context(kb)`

**Parameters:** the full knowledge base. **Returns:** a trimmed
context spanning both variants' skills and work-experience bullets
(unlike `build_baseline_context()`, not scoped to one variant), for
judging fit against an arbitrary job description. No side effects.

### `build_job_fit_prompt(kb, job_description, prompt_template_text)`

**Parameters:** the knowledge base, resolved job description text, and
`ANALYSIS_PROMPT_TEMPLATE`'s contents. **Returns:** the filled prompt
string, via `string.Template.substitute()` with `$output_rules`,
`$candidate_data`, and `$job_description`. No side effects.

### `validate_job_fit_analysis(data)`

**Parameters:** the candidate analysis dict. **Returns:** `None` on
success. **Side effect:** raises `ValueError` on any structural
problem - missing top-level keys, an empty or wrong-typed
`overall_summary`/`fit_assessments`, a missing key or out-of-range
`fit_percentage` on an assessment, or a malformed `upskill_resources`
entry.

### `call_llm_analyze_fit(client, kb, job_description, prompt_template_text)`

**Parameters:** the shared client, knowledge base, job description,
and prompt template text. **Returns:** the validated analysis dict.
**Side effects:** network call, requesting JSON mode where supported;
retries once on invalid JSON or a `validate_job_fit_analysis()`
failure; prints progress/error messages to stderr; exits on
connection/API errors or two failed attempts.

### `render_job_fit_analysis_md(analysis)`

**Parameters:** the validated analysis dict. **Returns:** a
human-readable Markdown report - rendered flat if there is exactly one
fit assessment, or as a per-list breakdown under an overall summary if
there is more than one. No side effects.

### `_render_matched_and_missing_md(assessment, heading_level)`

**Parameters:** one fit assessment dict and the Markdown heading level
to use (`"##"` or `"###"`). **Returns:** a list of Markdown lines for
that assessment's matched and missing qualifications, shared by both
branches of `render_job_fit_analysis_md()`. No side effects.

## Settings, naming templates, and file locations

### `parse_variants_env(raw)`

**Parameters:** the raw `VARIANTS` environment value (or `None`).
**Returns:** `["SDE", "SDET"]` if `raw` is `None`; otherwise the parsed
JSON array of (trimmed, non-empty) strings. **Side effect:** prints an
error and calls `sys.exit(1)` if `raw` is set but is not valid JSON, or
is not an array of strings.

### `load_file_location_settings()`

**Parameters:** none (reads from the environment). **Returns:** a dict
of every file-location and naming-template setting `main()` needs,
each read fresh from `os.environ` with its documented default - see
`03-configuration.md` for the full table. No side effects beyond
calling `parse_variants_env()` (which can exit on invalid input).

### `_NowPlaceholder` (class)

A `str` subclass wrapping one `datetime.datetime.now()` call, so a
naming template can use `{datetime.now}` bare (renders as
`YYYY-MM-DD_HHMMSS`) or with dotted attribute access
(`{datetime.now.year}`, `.month`, and so on, or any other real
`datetime.datetime` attribute) - all from the *same* underlying
instant, so a template combining several of these (for example a year
folder and a day-stamped file) cannot straddle a rollover between them.
`__getattr__` falls through to the wrapped `datetime` object for
anything not defined on `str` itself.

### `render_filename(naming_template, full_name, job_acronym, extension, email="")`

**Parameters:** the naming template string and this run's actual
values. **Returns:** the template filled in via `str.format()`, with
`{FirstName}`/`{LastName}` derived from `full_name`'s first/last
whitespace-separated tokens (both `""` if `full_name` is falsy), and a
fresh `_NowPlaceholder` supplied for every `{datetime.now...}`
placeholder in this call. No side effects - creating any subfolder the
result implies is the caller's job, via `ensure_parent_dir_exists()`.

### `ensure_parent_dir_exists(path)`

**Parameters:** a `Path` about to be written to. **Returns:** the same
`path`, unchanged. **Side effect:** creates `path`'s parent directory
(and any missing intermediate directories) if it does not already
exist, via `mkdir(parents=True, exist_ok=True)`.

## Output repository (`OUTPUT_REPO`) git operations

### `_run_git(args, cwd, env=None)`

**Parameters:** a list of git arguments, the working directory, and an
optional environment dict. **Returns:** the command's stdout. **Side
effects:** runs `git <args>` as a subprocess; raises `RuntimeError`
(folding in git's stderr) on a non-zero exit.

### `_inject_repo_token(repo_url, user, token)`

**Parameters:** the `OUTPUT_REPO` URL, an optional username, and
`OUTPUT_REPO_TOKEN`. **Returns:** the URL unchanged if `token` is
falsy or the URL is not `http(s)://`; otherwise the URL with
`user:token@` (defaulting `user` to `"x-access-token"`) embedded as an
HTTP Basic auth credential. No side effects.

### `_resolve_output_repo_target_ref(clone_dir, branch)`

**Parameters:** the local clone directory and an optional branch name.
**Returns:** the `origin/<branch>`-style ref `sync_output_repo()`
should hard-reset to, or `None` if that ref does not exist yet (an
empty remote). **Side effects:** runs `git symbolic-ref`/`git
rev-parse` subprocesses to check for the ref; does not raise on their
failure (that is the "ref doesn't exist yet" signal).

### `sync_output_repo(s)`

**Parameters:** the settings dict. **Returns:** the local clone `Path`
(`OUTPUT_REPO_CLONE_DIR`). **Side effects:** clones `OUTPUT_REPO` if
not already cloned there; otherwise fetches `origin` and hard-resets
the clone to match it, discarding any uncommitted/untracked leftovers;
raises `RuntimeError` if `OUTPUT_REPO_CLONE_DIR` exists but is not a
git repo, or if any underlying git command fails.

### `commit_and_push_output_repo(s, clone_dir)`

**Parameters:** the settings dict and the clone directory. **Returns:**
`True` if a commit was made, `False` if the working tree already
matched what was committed (nothing new to check in). **Side
effects:** stages and commits everything under `clone_dir` (using
`OUTPUT_REPO_AUTHOR_NAME`/`OUTPUT_REPO_AUTHOR_EMAIL` as the commit
identity, and `OUTPUT_REPO_COMMIT_MESSAGE` rendered via
`render_filename()`); pushes to `OUTPUT_REPO_BRANCH` (or the current
branch) unless `OUTPUT_REPO_PUSH` is falsy; raises `RuntimeError` on
any underlying git failure.

## Entry point

### `main(argv=None)`

Parses arguments (`argv` defaults to `[]` rather than falling back to
`sys.argv`, so calling `main()` directly - for example from a test -
does not pick up an unrelated caller's CLI args). The overall control
flow:

1. Resolves the target set: `ALL_TARGETS` if `--generate` was omitted
   and `--analyze` was not given; empty (analysis-only) if `--generate`
   was omitted but `--analyze` was given; otherwise whatever
   `parse_generate_targets()` returns.
2. Loads settings (`load_file_location_settings()`) and builds the
   shared LLM client (`build_llm_client()`).
3. Loads the knowledge base (`load_knowledge_base()`) only if a target
   that needs it was requested (`resume`/`cover_letter`/`readme`, or
   `--analyze`) - `profile` reads it lazily itself, since it has its
   own rules about whether the knowledge base needs to exist yet.
4. If `OUTPUT_REPO` is set and a resume/cover_letter/readme target was
   requested, syncs the output repo clone once up front
   (`sync_output_repo()`), before any generation, so every target
   writes into the same clone.
5. Dispatches to each requested target in turn: resume and cover
   letter generation (looping over `VARIANTS`, calling the relevant
   `call_llm_*`/`render_*` functions and writing files under
   `OUTPUT_FOLDER` or the output-repo clone), then `readme`
   (`call_llm_readme()`, written to `README_OUTPUT`), then `profile`
   (`generate_profile_draft()`).
6. If `--analyze` was given, resolves the job description
   (`resolve_job_description()`), runs the analysis
   (`call_llm_analyze_fit()`), and prints the rendered report
   (`render_job_fit_analysis_md()`) to stdout.
7. Prints a short summary of what was generated and where.
8. If the output repo was synced in step 4, commits (and pushes,
   unless `OUTPUT_REPO_PUSH` is false) the result
   (`commit_and_push_output_repo()`).

**Side effects:** essentially every side effect in the module can
originate here - network calls, file reads/writes, git operations, and
`sys.exit(1)` on any unrecoverable error from the functions it calls
(a bad `KNOWLEDGE_BASE`, an `OUTPUT_REPO` sync failure, an unresolved
`--analyze` value).

## Module constants

| Constant | Purpose |
|---|---|
| `ALL_TARGETS` | The targets built when `--generate` is omitted entirely: `{"resume", "cover_letter", "readme"}`. Deliberately excludes `"profile"`. |
| `GENERATE_ALIASES` | Maps a normalized `--generate` token to its canonical target name (for example `"coverletter"` and `"cover_letter"` both map to `"cover_letter"`). |
| `ALL_KNOWN_TARGETS` | Every valid canonical target - `set(GENERATE_ALIASES.values())` - used to build the error message for an unrecognized `--generate` value. |
| `MODEL` | The LiteLLM model string, from `LITELLM_MODEL` (default `qwen3.6:latest`), read once at import time. |
| `LITELLM_TIMEOUT_SECONDS` | The read-timeout portion of `LLM_REQUEST_TIMEOUT`, from `LITELLM_TIMEOUT` (default `550`). |
| `LLM_REQUEST_TIMEOUT` | An `httpx.Timeout` with a short (10s) connect timeout and a long read timeout (`LITELLM_TIMEOUT_SECONDS`), so an unreachable proxy fails fast while a slow-but-reachable one still gets its full budget. Passed to every `chat.completions.create()` call. |
| `LITELLM_KEEP_ALIVE` | Ollama's model keep-alive duration, from `LITELLM_KEEP_ALIVE` (default `"30m"`), passed via `extra_body` on every LLM call. |
| `CATEGORY_LABELS` | Maps a knowledge base skill-category key (for example `"apis_and_web_servers"`) to a display label (`"APIs & Web Servers"`) for resume/README/job-fit skill sections. |
| `SKILLS_HEADING_BY_VARIANT` | Custom skills-section heading text for `"SDE"` and `"SDET"` specifically (referenced from `03-configuration.md`'s `VARIANTS` explanation). |
| `SKILLS_HEADING_FALLBACK` | The generic `"CORE {variant} SKILLS"` heading used for any `VARIANTS` entry not in `SKILLS_HEADING_BY_VARIANT`. |
| `BULLET_CHAR` | The `●` character used for resume bullets, matching the existing hand-written resumes' style. |
| `EM_DASH` | The em dash character checked for and stripped/rejected throughout (`strip_em_dashes()`, `validate_readme()`). |
| `ACCENT_RGB` / `ACCENT_COLOR` | The navy accent color used in DOCX and PDF rendering respectively (same color, two different color-object types for the two libraries). |
| `PDF_TIERS` | The ordered list of font-size/margin tiers `render_resume_pdf()` tries, largest first, until the result fits within `max_pages`. |
| `README_REQUIRED_HEADERS` | The exact section header strings (including emoji) `validate_readme()` requires to be present. |
| `REQUIRED_COVER_LETTER_KEYS` | `{"body"}` - the only key `call_llm_cover_letter()` requires in the model's JSON response. |
| `REQUIRED_ANALYSIS_KEYS` / `REQUIRED_ASSESSMENT_KEYS` / `REQUIRED_RESOURCE_KEYS` | The required top-level, per-assessment, and per-resource keys `validate_job_fit_analysis()` checks for. |
