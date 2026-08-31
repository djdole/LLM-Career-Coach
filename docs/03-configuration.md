# Configuration Reference

All configuration is environment variables, normally set via `.env`
(see `.env.template` in the repository root for the canonical file
with inline comments). Nothing has a UI or a separate config file -
`.env` is the only source `generator.py` reads at startup.

## LiteLLM connection

| Variable | Default | Purpose |
|---|---|---|
| `LITELLM_BASE_URL` | *(required, no default)* | Your LiteLLM proxy's address, for example `https://litellm.example.com`. `generator.py` exits immediately (see `build_llm_client()`) if this or `LITELLM_API_KEY` is unset. |
| `LITELLM_API_KEY` | *(required, no default)* | The API key for that proxy (its `LITELLM_MASTER_KEY`, if self-hosted). |
| `LITELLM_MODEL` | `qwen3.6:latest` | The model string LiteLLM proxies to. Run `./getModels.sh` after setting the two variables above to see what is available. |
| `LITELLM_MAX_TOKENS` | `10000` | Max output tokens per LLM call. |
| `OLLAMA_NUM_CTX` | `16384` | Ollama context window size (input + output tokens). Lower this if your GPU cannot hold the default for the model in use. |
| `LITELLM_TIMEOUT` | `550` (seconds) | How long to wait for a single LLM response before giving up on that attempt. Keep this comfortably below any reverse proxy's own read timeout in front of LiteLLM (for example nginx's `proxy_read_timeout`) - if the proxy's timeout is shorter, it kills the connection first, silently, and this setting never gets the chance to matter. |
| `LITELLM_KEEP_ALIVE` | `30m` | How long Ollama keeps the model loaded in VRAM after a request. A full run makes several sequential calls; keep this comfortably longer than a full run takes end to end so the model does not unload mid-run. Accepts a duration string (`30m`, `1h`) or a number of seconds. |

## Resume/cover letter variants

| Variable | Default | Purpose |
|---|---|---|
| `VARIANTS` | `["SDE", "SDET"]` | A JSON array of variant names to generate, in order. |

`VARIANTS` is JSON, not a bare comma-separated list, specifically so a
variant name can contain spaces (or even a comma) without being split
apart. In `.env`, wrap the whole value in single quotes, since the
JSON syntax itself uses double quotes:

```bash
VARIANTS='["Product Manager", "HR Admin"]'
```

Each entry becomes:

* `{JobAcronym}` in a naming template (see below).
* A key looked up in `profile.json`'s per-variant fields
  (`summary_variants`, `title_by_variant`, and so on). A variant
  missing from one of those fields does not fail the run:
  `summary_variants` falls back to that field's `"SDE"` entry, and a
  job's `title_by_variant` falls back to whichever variant it does
  have.
* The resume's skills-section heading. `SDE` and `SDET` get custom
  wording via `SKILLS_HEADING_BY_VARIANT` in `generator.py`; any other
  value gets a generic `"CORE <VARIANT> SKILLS"` heading rather than an
  error.

A `VARIANTS` value that is not valid JSON, or is not a JSON array of
strings, exits immediately with an error rather than being silently
ignored or falling back to the default (see `parse_variants_env()`).
Set `VARIANTS='["SDE"]'` to generate a single variant, or
`VARIANTS='[]'` to generate none.

## Output locations

| Variable | Default | Purpose |
|---|---|---|
| `OUTPUT_FOLDER` | `generated` | Where resume/cover letter files are written. |
| `README_TEMPLATE` | `README.template.md` | Template `--generate readme` fills in. |
| `README_OUTPUT` | `README.md` | Where the filled-in README is written (repository root, by default, so it renders as the GitHub profile README). |
| `EMAIL_TAG_ADDRESS` | `""` (no tag) | Optional "plus addressing" tag (RFC 5233 subaddressing - Gmail, Outlook, and similar providers honor it) applied to the README's email `mailto:` link only. |
| `RESUME_TEMPLATE` | `RESUME.template.md` | Template `--generate resume` fills in. |
| `RESUME_NAMING_TEMPLATE` | `{FirstName} {LastName} Resume ({JobAcronym}).{Extension}` | Output path pattern for resumes - see [Naming template placeholders](#naming-template-placeholders) below. |
| `COVERLETTER_NAMING_TEMPLATE` | `{FirstName} {LastName} Cover Letter ({JobAcronym}).{Extension}` | Same, for cover letters. |

`EMAIL_TAG_ADDRESS` changes only the link a reader clicks, never the
address displayed on the page. `build_tagged_email()` in
`generator.py` builds the tagged address: with `EMAIL_TAG_ADDRESS` set
to `resume` and `personal_info.email` equal to `jane@example.com`, the
README still shows `jane@example.com` as text, but the link behind it
becomes `mailto:jane+resume@example.com` - useful for telling whether
a reply came from someone who found you via the README. Leave it blank
(the default) for no tag at all, in which case the link matches the
displayed address exactly.

## Output repository (`OUTPUT_REPO`)

Checking generated output into a separate git repository is
configured with the following variables. See
`08-output-repository.md` for the full explanation of what setting
`OUTPUT_REPO` changes and how each variable is used.

* `OUTPUT_REPO`
* `OUTPUT_REPO_BRANCH`
* `OUTPUT_REPO_TOKEN`
* `OUTPUT_REPO_CLONE_DIR`
* `OUTPUT_REPO_AUTHOR_NAME`
* `OUTPUT_REPO_AUTHOR_EMAIL`
* `OUTPUT_REPO_COMMIT_MESSAGE`
* `OUTPUT_REPO_PUSH`

## Knowledge base

| Variable | Default | Purpose |
|---|---|---|
| `KNOWLEDGE_BASE` | `data/profile.json` | Where every generation target reads the knowledge base from. Can be a local path, or an `http(s)` URL - for example a raw file URL into a private repo - to pull it from somewhere other than this checkout. |
| `KNOWLEDGE_BASE_URL_TOKEN` | *(unset)* | Only used when `KNOWLEDGE_BASE` is a URL pointing at a private source. Sent as `Authorization: token <value>` (GitHub's convention - works for both `api.github.com` and `raw.githubusercontent.com` with a personal access token). Leave unset for a public URL. |
| `KNOWLEDGE_BASE_DRAFT` | `data/profile.json` | Where `--generate profile` writes its output. Also a naming template (see below), so for example `KNOWLEDGE_BASE_DRAFT="data/{datetime.now}/profile.json"` nests each run's draft under its own timestamped subfolder instead of overwriting the same file every time. Defaults to the same path as `KNOWLEDGE_BASE`, so with no placeholders a successful run overwrites the knowledge base directly. |
| `DATA` | *(unset)* | Folder `--generate profile` reads source documents from (`pdf`/`txt`/`json`/`xml`/`docx`). Not used by any other target. If unset, `--generate profile` is a no-op. |

"Non-destructive," for `--generate profile`, means the merge is
structure-preserving: no top-level section present in the existing
knowledge base is allowed to disappear from the draft
(`validate_profile_draft()` enforces this). It does **not** mean your
original file is left untouched on disk - with the default settings,
the draft is written right back over `KNOWLEDGE_BASE`. Point
`KNOWLEDGE_BASE_DRAFT` somewhere else if you want a review step first.

## `--analyze`'s prompt

| Variable | Default | Purpose |
|---|---|---|
| `ANALYSIS_PROMPT_TEMPLATE` | `ANALYSIS_PROMPT.template.txt` | The LLM prompt `--analyze` uses, as a `string.Template` file with `$output_rules`/`$candidate_data`/`$job_description` placeholders. Edit this file directly to change how the analysis is framed - no Python changes needed. |

`.env.template` also ships an `ANALYSIS_NAMING_TEMPLATE` setting,
described there (and in the root `USAGE.md`) as the output filename
`--analyze`'s report is written under. Reading `main()` in
`generator.py`, however, the current code never reads
`ANALYSIS_NAMING_TEMPLATE` and never writes the analysis report to a
file at all - `render_job_fit_analysis_md()`'s output is only printed
to stdout. Treat `ANALYSIS_NAMING_TEMPLATE` as currently unused by the
code, and redirect stdout yourself (for example
`python generator.py --analyze "..." > report.md`) if you want the
report saved to a file. See `12-troubleshooting-faq.md` if this
surprises you.

## Naming template placeholders

`RESUME_NAMING_TEMPLATE`, `COVERLETTER_NAMING_TEMPLATE`,
`KNOWLEDGE_BASE_DRAFT`, and `OUTPUT_REPO_COMMIT_MESSAGE` are all filled
in the same way, via `render_filename()`. Every placeholder below is a
plain Python `str.format()` token (`{Like_This}`), so any of them can
be combined, repeated, or omitted freely.

| Placeholder | Renders as | Available in |
|---|---|---|
| `{FirstName}` | First whitespace-separated token of `personal_info.full_name`. | Resume/cover letter naming templates: always. `KNOWLEDGE_BASE_DRAFT`: only once `KNOWLEDGE_BASE` has some readable `personal_info.full_name` to read from - `""` during a from-scratch build (no knowledge base yet), or if `KNOWLEDGE_BASE` is missing, unreadable, or malformed. |
| `{LastName}` | Last whitespace-separated token of `personal_info.full_name` (a middle name/initial is dropped). | Same as `{FirstName}`. |
| `{Email}` | `personal_info.email` verbatim. | Same as `{FirstName}` - `""` wherever a name is not available yet either. |
| `{JobAcronym}` | The resume variant currently being generated. | Resume/cover letter naming templates only. Always `""` in `KNOWLEDGE_BASE_DRAFT` and `OUTPUT_REPO_COMMIT_MESSAGE` (neither is per-variant). |
| `{Extension}` | The output format for this specific file: `pdf`/`docx`/`txt`/`md`/`json` for resumes, `pdf`/`docx`/`txt` for cover letters. | Resume/cover letter naming templates only. Always `"json"` in `KNOWLEDGE_BASE_DRAFT` (the draft is always JSON); always `""` in `OUTPUT_REPO_COMMIT_MESSAGE`. |
| `{datetime.now}` | The current local date/time as `YYYY-MM-DD_HHMMSS` (sortable, no `:` or space, safe as a path segment on any OS). | All naming templates. |
| `{datetime.now.year}` | Four-digit year, as a real `int` (so `{datetime.now.month:02d}` zero-pads via a normal `str.format` spec). | All naming templates. |
| `{datetime.now.month}` | Month, `1`-`12`. | All naming templates. |
| `{datetime.now.day}` | Day of month, `1`-`31`. | All naming templates. |
| `{datetime.now.hour}` | Hour, `0`-`23`. | All naming templates. |
| `{datetime.now.minute}` | Minute, `0`-`59`. | All naming templates. |
| `{datetime.now.second}` | Second, `0`-`59`. | All naming templates. |

A couple of things worth knowing:

* Any `/` in a rendered value becomes a subfolder, created
  automatically the first time something is about to be written into
  it - you do not need to create it yourself first. This is exactly
  how `{JobAcronym}/{FirstName} {LastName} Resume.{Extension}` puts
  each variant's output in its own folder instead of encoding the
  variant into the filename.
* `{datetime.now}` and `{datetime.now.year}` (and its siblings) in the
  same template share one instant - they are both read from a single
  `datetime.now()` call made once per file, so they cannot disagree
  with each other, for example by straddling a year rollover between
  the two.

## Worked example

```bash
# .env
VARIANTS='["SDE", "Product Manager"]'
RESUME_NAMING_TEMPLATE="{JobAcronym}/{FirstName} {LastName} Resume.{Extension}"
COVERLETTER_NAMING_TEMPLATE="{JobAcronym}/{FirstName} {LastName} Cover Letter.{Extension}"
OUTPUT_REPO="https://github.com/YOUR_USERNAME/your-resumes.git"
OUTPUT_REPO_TOKEN="ghp_..."
```

With this `.env`, a run generates an `SDE` resume/cover letter set and
a `Product Manager` resume/cover letter set (rather than the default
`SDE`/`SDET` pair), each variant's files land in their own subfolder
(`SDE/` and `Product Manager/`) instead of all sharing one folder with
the variant only in the filename, and the generated files are written
into a clone of `your-resumes.git` and committed (and pushed) there
instead of into this checkout.
