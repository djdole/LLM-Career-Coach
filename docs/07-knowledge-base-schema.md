# Knowledge Base Schema (`data/profile.json`)

## TODO Documentation Tasks

- Note that `data/profile.json` (or wherever `KNOWLEDGE_BASE` points)
  is not checked into this repository (it is personal data, and is
  gitignored) - there is no sample file to read directly, so this
  schema must be reverse-engineered from how `generator.py` reads it.
  Read every `kb["..."]` / `kb.get("...")` access in `generator.py`
  (search the whole file, not just one function) to build an accurate
  field list, and cross-check each field against the placeholders used
  in `RESUME.template.md` and `README.template.md`
  (see `06-templates.md`).
- Document each observed top-level key with what it contains and which
  code path reads it. At minimum, confirm and document:
  - `meta` - read in `build_baseline_context()`; determine what it is
    used for (for example versioning or generation notes) by reading
    that function.
  - `personal_info` - name, email, phone, links; confirm exact field
    names by reading `build_baseline_context()` and
    `build_readme_context()`, since `{{FULL_NAME}}`, `{{EMAIL}}`,
    etc. in the templates must map to something here.
  - `summary_variants` - per-variant professional summaries, keyed by
    variant name (for example `"SDE"`, `"SDET"`), with the documented
    fallback to the `"SDE"` entry for a variant missing its own entry.
  - `skills` - skill categories and their contents, feeding the
    `{{CATEGORY_NAME}}: {{COMMA_SEPARATED_SKILLS}}` template lines.
  - `work_experience` - list of jobs, each with (confirm exact names
    by reading the code) a title (possibly per-variant via
    `title_by_variant`), company, start/end dates, optional
    `team_context`, and bullets. Document the per-variant title
    fallback behavior (falls back to whichever variant IS present)
    mentioned in `USAGE.md`.
  - `education` - degree, institution, field of study, graduation
    date.
  - `cover_letter_building_blocks` - read
    `build_cover_letter_prompt()` to determine what sub-fields this
    contains and how they are used to construct the cover letter
    prompt.
  - `career_narrative_notes` - specifically its
    `strongest_differentiators` list, used verbatim in the README's
    "Career Highlights" section (see `06-templates.md`). Read
    `build_readme_context()` for the exact access path and confirm
    whether `career_narrative_notes` has other sub-fields used
    elsewhere (it appears to be read with `.get()`, suggesting it may
    be optional - confirm and document that).
  - `generation_workflow_for_llm` - mentioned in `USAGE.md` as holding
    the manual, chat-based, per-posting tailoring workflow description
    that is outside `generator.py`'s own scope. Confirm whether
    `generator.py` reads this field itself anywhere, or whether it
    exists purely for a human/LLM reading the JSON directly.
- Document the `--generate profile` maintenance workflow's
  relationship to this schema: `validate_profile_draft()` in
  `generator.py` enforces the "non-destructive" structural guarantee
  (no top-level section can disappear). Summarize exactly what that
  function checks.
- Provide an annotated example `profile.json` skeleton (with obviously
  fake placeholder data, not a real person's information) showing the
  top-level shape, for a reader who wants to build one from scratch.
  Keep real personal data out of this documentation entirely.
- Cross-reference `02-setup.md` for how to bootstrap this file via
  `--generate profile` from existing source documents instead of
  writing it by hand.
