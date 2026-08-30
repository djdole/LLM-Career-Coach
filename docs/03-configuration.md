# Configuration Reference

## TODO Documentation Tasks

- State up front that all configuration is environment variables,
  normally set via `.env` (see `.env.template` for the canonical file
  with inline comments), and that nothing has a UI or separate config
  file: `.env` is the only source `generator.py` reads at startup.
  Source: the "Configuration" section intro in `USAGE.md`.
- Build one settings table per group below. Each row needs: variable
  name, default value (or "required, no default"), and a full
  description of its purpose and effect. Pull the authoritative values
  and behavior from `.env.template`'s inline comments, `USAGE.md`'s
  "Configuration" section, and by reading where each variable is
  consumed in `generator.py` (search for `os.environ` / `os.getenv`
  usage, and `load_file_location_settings()` around line 1757).
  - **LiteLLM connection**: `LITELLM_BASE_URL`, `LITELLM_API_KEY`,
    `LITELLM_MODEL`, `LITELLM_MAX_TOKENS`, `OLLAMA_NUM_CTX`,
    `LITELLM_TIMEOUT`, `LITELLM_KEEP_ALIVE`. Call out that the first
    two are required with no default and cause an immediate exit if
    unset (see `build_llm_client()`), and explain the interaction
    between `LITELLM_TIMEOUT` and any reverse proxy's own read timeout
    in front of LiteLLM.
  - **Resume/cover letter variants**: `VARIANTS`. Explain it is a JSON
    array (not a bare comma-separated list), why it must be
    single-quoted in `.env` while using double-quoted JSON internally,
    what happens for a variant missing from a per-variant
    `profile.json` field (falls back to that field's `"SDE"` entry, or
    for job titles, to whichever variant is present), what an invalid
    (non-JSON or non-string-array) value does (exits with an error),
    and what `SKILLS_HEADING_BY_VARIANT` in `generator.py` does for
    `SDE`/`SDET` versus any other variant name.
  - **Output locations**: `OUTPUT_FOLDER`, `README_TEMPLATE`,
    `README_OUTPUT`, `EMAIL_TAG_ADDRESS`, `RESUME_TEMPLATE`,
    `RESUME_NAMING_TEMPLATE`, `COVERLETTER_NAMING_TEMPLATE`. Explain
    `EMAIL_TAG_ADDRESS`'s RFC 5233 plus-addressing behavior precisely:
    it only changes the README's `mailto:` link, never the displayed
    email address. Reference `build_tagged_email()` in `generator.py`.
  - **Output repository (`OUTPUT_REPO`)**: cross-reference
    `08-output-repository.md` for the full explanation instead of
    duplicating it, but list the variable names here for completeness:
    `OUTPUT_REPO`, `OUTPUT_REPO_BRANCH`, `OUTPUT_REPO_TOKEN`,
    `OUTPUT_REPO_CLONE_DIR`, `OUTPUT_REPO_AUTHOR_NAME`,
    `OUTPUT_REPO_AUTHOR_EMAIL`, `OUTPUT_REPO_COMMIT_MESSAGE`,
    `OUTPUT_REPO_PUSH`.
  - **Knowledge base**: `KNOWLEDGE_BASE`, `KNOWLEDGE_BASE_URL_TOKEN`,
    `KNOWLEDGE_BASE_DRAFT`, `DATA`. Explain that `KNOWLEDGE_BASE` can
    be a local path or an http(s) URL, what
    `KNOWLEDGE_BASE_URL_TOKEN`'s `Authorization: token <value>` header
    is for, and the "non-destructive" merge guarantee described in
    `USAGE.md` (structure-preserving, but not "leaves the original
    file untouched on disk" since the draft is written back over
    `KNOWLEDGE_BASE` by default).
  - **`--analyze`'s prompt**: `ANALYSIS_PROMPT_TEMPLATE`, and
    `ANALYSIS_NAMING_TEMPLATE` from the naming-template group below.
- Document naming template placeholders in their own subsection:
  `{FirstName}`, `{LastName}`, `{Email}`, `{JobAcronym}`,
  `{Extension}`, `{datetime.now}`, and `{datetime.now.year}` /
  `.month` / `.day` / `.hour` / `.minute` / `.second`. For each, state
  which naming templates it is available in
  (`RESUME_NAMING_TEMPLATE` / `COVERLETTER_NAMING_TEMPLATE` /
  `KNOWLEDGE_BASE_DRAFT` / `OUTPUT_REPO_COMMIT_MESSAGE`) and any
  conditions on when it renders empty. Source: the "Naming template
  placeholders" table in `USAGE.md`, and `render_filename()` in
  `generator.py`. Include the two "worth knowing" notes from
  `USAGE.md`: a `/` in a rendered value creates a subfolder
  automatically, and `{datetime.now}` plus its sub-placeholders in the
  same template share one instant (one `datetime.now()` call).
- Add a worked example showing a customized `.env` snippet (for
  example, changing `VARIANTS`, nesting resumes under a per-variant
  subfolder via `RESUME_NAMING_TEMPLATE`, and setting `OUTPUT_REPO`)
  with a one-line explanation of what changes for the user.
