# Knowledge Base Schema (`data/profile.json`)

`data/profile.json` (or wherever `KNOWLEDGE_BASE` points) is not
checked into this repository - it is personal data, and is
gitignored. There is no sample file to read directly, so the schema
below was reverse-engineered from every `kb["..."]` / `kb.get("...")`
access across `generator.py`, cross-checked against the placeholders
used in `RESUME.template.md` and `README.template.md` (see
`06-templates.md`), and against the test suite's hand-built fixture
knowledge base (`tests/conftest.py`).

## Top-level keys

### `meta`

Read in `build_baseline_context()`, `build_readme_context()`, and
`build_job_fit_prompt()`, always via `kb["meta"]["output_rules"]`.
Holds generation-time rules, not versioning notes - specifically:

```json
{
  "meta": {
    "output_rules": {
      "never_fabricate": "Do not invent facts.",
      "never_use_em_dash": "Never use an em dash."
    }
  }
}
```

Both `never_fabricate` and `never_use_em_dash` are read as plain
strings and passed straight into every LLM prompt (resume, cover
letter, README, and job-fit analysis) as instructions the model must
follow. `never_use_em_dash` is additionally enforced in code:
`validate_readme()` rejects a README containing an em dash outright,
and `strip_em_dashes()` replaces any em dash that slips into resume or
cover letter text with a comma as a fallback.

### `personal_info`

Read wholesale (`kb["personal_info"]`, or `dict(kb["personal_info"])`
for the README) rather than field-by-field in most places - the only
sub-fields `generator.py` reads by literal name are `full_name` (used
in `main()` and for naming-template placeholders) and `email` (used in
`build_tagged_email()`). Every other sub-field the templates ask for -
`{{EMAIL}}`, `{{PHONE}}`, `{{LINKEDIN}}`, `{{PORTFOLIO}}` in the resume
template, and `{{LOCATION}}`, `{{ORCID_URL}}`, `{{LINKEDIN_DISPLAY}}`,
`{{LINKEDIN_URL}}`, `{{PORTFOLIO_DISPLAY}}`, `{{PORTFOLIO_URL}}` in the
README template - is read directly by the LLM from whatever
`personal_info` contains, not validated or renamed by code. In
practice this means `personal_info` needs at least a name, an email,
and enough contact/link fields (phone, LinkedIn, portfolio, location,
and optionally something ORCID-related) for the model to fill in both
templates, but the exact key names for those extra fields are a
convention between your knowledge base and the templates, not
something `generator.py` enforces.

### `summary_variants`

Per-variant professional summaries, keyed by variant name (for
example `"SDE"`, `"SDET"`):

```json
{
  "summary_variants": {
    "SDE": "Software engineer summary text.",
    "SDET": "SDET-focused summary text."
  }
}
```

`build_baseline_context()` looks up `summary_variants[variant]` and
falls back to `summary_variants["SDE"]` if the current `VARIANTS`
entry has no key of its own here - so a new variant (for example
`"Product Manager"`) works without erroring, but reuses the SDE
summary until you add a real one for it. The README (which is not
per-variant) always uses `summary_variants["SDE"]` directly. The
job-fit analysis context (`build_job_fit_context()`) includes the
whole `summary_variants` dict as-is, across every variant.

### `skills`

A dict of skill categories, each mapping to a list of skill strings:

```json
{
  "skills": {
    "languages": ["Python", "Go"],
    "apis_and_web_servers": ["FastAPI", "gRPC"]
  }
}
```

Every value that is a list is turned into
`{{CATEGORY_NAME}}: {{COMMA_SEPARATED_SKILLS}}` template lines. The
category key is mapped to a display label via `CATEGORY_LABELS` in
`generator.py` if a matching entry exists there (for example
`"apis_and_web_servers"` becomes `"APIs & Web Servers"`); otherwise it
falls back to a title-cased version of the key with underscores turned
into spaces. A non-list value under `skills` (for example a free-text
guidance string) is simply skipped when building categories, so
`skills` can hold non-category metadata alongside real categories
without breaking anything.

### `work_experience`

A list of jobs, most recent first (the code preserves whatever order
this list is already in - it does not sort by date):

```json
{
  "work_experience": [
    {
      "title_by_variant": {"SDE": "Software Engineer", "SDET": "SDET"},
      "company": "Acme Corp",
      "team_context": "Team Widgets, Platform Squad",
      "start_date": "2020-01",
      "end_date": "2023-01",
      "technologies": ["Python", "AWS"],
      "bullets": [
        {"id": "acme_1", "text": "Built the widget service."},
        {"id": "acme_1_alt", "text": "Alternate phrasing for a different variant."}
      ]
    }
  ]
}
```

Confirmed field names, by reading the code:

* `title_by_variant` - a dict keyed by variant name. For the current
  resume/cover-letter variant, `build_baseline_context()` looks up
  `title_by_variant[variant]` and falls back to whichever variant IS
  present (`next(iter(job["title_by_variant"].values()))`) if the
  current variant has no title of its own - so a job missing a title
  for a new variant does not fail the run. The README always uses the
  `"SDE"` entry (falling back the same way).
* `company` - plain string.
* `team_context` - optional (read with `.get("team_context", "")`); a
  job with none of this gets its team-context line omitted entirely
  from the rendered output.
* `start_date` / `end_date` - plain strings, joined as
  `f"{start_date} - {end_date}"` to build the rendered date range. Any
  string format works as long as it reads sensibly once joined this
  way.
* `technologies` - optional (read with `.get("technologies", [])`),
  only used in the job-fit analysis context, not in resumes, cover
  letters, or the README.
* `bullets` - a list of `{"id": ..., "text": ...}` objects. Only
  `text` ever reaches an LLM prompt; `id` is used purely to filter
  bullets before that: any bullet whose `id` ends in `_alt` or
  `_variant` is dropped from the baseline/README/job-fit contexts,
  which is how a knowledge base can store alternate phrasings of a
  bullet (for JD-specific tailoring, outside this script's own scope)
  without them leaking into baseline output.

### `education`

A list of education entries:

```json
{
  "education": [
    {
      "institution": "State University",
      "field of study": "Computer Science",
      "degree": "Bachelor of Science in Computer Science",
      "graduation date": "2015"
    }
  ]
}
```

Note the two keys with literal spaces: `"field of study"` and
`"graduation date"` - not `field_of_study`/`graduation_date`. The code
reads them exactly this way (`ed["graduation date"]`,
`ed.get("field of study", "")`) and renames them to the output
schema's `date` / `field_of_study` keys internally; using the
underscored spelling in your actual `profile.json` will silently
produce a `KeyError` for `"graduation date"`, since it is not read
with `.get()`. `field of study` specifically is only read with
`.get()` (optional, defaults to `""`) in the README context - the
resume and job-fit contexts do not use it at all.

### `cover_letter_building_blocks`

Read in `build_baseline_context()` (which feeds `build_cover_letter_prompt()`)
via a single confirmed sub-field:

```json
{
  "cover_letter_building_blocks": {
    "generic_fallback_template": "Dear Hiring Manager, ... Sincerely, [Name]"
  }
}
```

`generic_fallback_template` is the only sub-field `generator.py` reads
by name (`kb["cover_letter_building_blocks"]["generic_fallback_template"]`) -
it is required, since this access is not wrapped in `.get()`. The
cover letter prompt asks the model to lightly adapt this text rather
than invent a cover letter from scratch. Other sub-fields you might
store here (for example JD-specific opening hooks) are not read by
`generator.py` at all, since JD-specific tailoring is outside this
script's scope.

### `career_narrative_notes`

Read only in `build_readme_context()`, and only for one sub-field:

```json
{
  "career_narrative_notes": {
    "strongest_differentiators": [
      "Shipped three products from zero to production.",
      "Built a testing culture from scratch."
    ]
  }
}
```

The access is `kb.get("career_narrative_notes", {}).get("strongest_differentiators", [])` -
both levels use `.get()` with an empty-collection fallback, so this
entire top-level key is optional: a knowledge base without it simply
produces an empty "Career Highlights" section rather than an error.
`strongest_differentiators` items are copied into the README verbatim
(see `06-templates.md`) - not rewritten by the LLM - so word each entry
exactly as you want it to appear.

### `generation_workflow_for_llm`

Mentioned in `generator.py`'s own module docstring as holding the
manual, chat-based, per-posting tailoring
workflow description - the process for adapting a resume to one
specific job posting, which is explicitly outside `generator.py`'s own
scope. Searching every `kb[...]` / `kb.get(...)` access in
`generator.py` confirms this field is never read by the code itself;
it exists purely for a human, or an LLM in a separate chat session
reading the JSON directly, to follow that manual workflow.

## `--generate profile`'s relationship to this schema

`validate_profile_draft()` enforces the "non-destructive" structural
guarantee described in `05-generation-targets-and-outputs.md`:

* The draft must be a JSON object.
* It must contain at least `personal_info`, `education`, `skills`, and
  `work_experience`.
* If an existing knowledge base was supplied (an update rather than a
  from-scratch build), every top-level key present in that existing
  knowledge base must still be present in the draft - a top-level
  section is never allowed to silently disappear.

It does not otherwise validate the *contents* of any section beyond
requiring the four keys above to exist - the fields documented earlier
in this page (for example the exact `work_experience`/`education`
sub-field names) are conventions the templates and prompt-builders
depend on, not something `validate_profile_draft()` checks directly.

## Annotated example skeleton

Obviously fake placeholder data - not a real person's information -
showing the top-level shape a `profile.json` needs:

```json
{
  "meta": {
    "output_rules": {
      "never_fabricate": "Do not invent facts not present in this data.",
      "never_use_em_dash": "Never use an em dash character."
    }
  },
  "personal_info": {
    "full_name": "Jordan Example",
    "email": "jordan@example.com",
    "phone": "555-0100",
    "linkedin": "linkedin.com/in/jordanexample",
    "portfolio_or_profile": "example.dev/jordan",
    "location_short": "Springfield, USA"
  },
  "summary_variants": {
    "SDE": "Backend-leaning software engineer summary.",
    "SDET": "Test-automation-focused engineer summary."
  },
  "skills": {
    "languages": ["Python", "TypeScript"],
    "ci_cd_and_devops": ["GitHub Actions", "Docker"]
  },
  "work_experience": [
    {
      "title_by_variant": {"SDE": "Software Engineer", "SDET": "SDET"},
      "company": "Example Corp",
      "team_context": "Platform team, 6 engineers",
      "start_date": "2021-03",
      "end_date": "Present",
      "technologies": ["Python", "PostgreSQL"],
      "bullets": [
        {"id": "example_1", "text": "Shipped a service handling X requests/day."},
        {"id": "example_1_alt", "text": "Alternate phrasing kept for future JD tailoring."}
      ]
    }
  ],
  "education": [
    {
      "institution": "Example State University",
      "field of study": "Computer Science",
      "degree": "B.S. Computer Science",
      "graduation date": "2020"
    }
  ],
  "cover_letter_building_blocks": {
    "generic_fallback_template": "Dear Hiring Manager, ... Sincerely, Jordan"
  },
  "career_narrative_notes": {
    "strongest_differentiators": [
      "Owns projects end to end, from design through production."
    ]
  },
  "generation_workflow_for_llm": {
    "note": "Manual, chat-based, per-posting tailoring process goes here - not read by generator.py."
  }
}
```

## Building this file without writing it by hand

Rather than hand-writing `profile.json` from scratch, `--generate
profile` can build (or non-destructively update) it from existing
source documents - old resumes, notes, and so on - dropped in the
`DATA` folder. See `02-setup.md` for when to reach for this in initial
setup, and `05-generation-targets-and-outputs.md` for the full
`--generate profile` pipeline.
