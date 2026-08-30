# Templates

## TODO Documentation Tasks

- Explain the general idea: `RESUME_TEMPLATE` and `README_TEMPLATE`
  are Markdown files with `{{PLACEHOLDER}}` tokens and HTML comments
  giving repetition instructions, which the LLM fills in per the
  knowledge base; `ANALYSIS_PROMPT_TEMPLATE` is a different kind of
  template (a `string.Template` text file), used to build the prompt
  sent to the LLM for `--analyze`, not a document that gets filled in
  and rendered the same way.
- Document `RESUME.template.md` section by section, reading the actual
  file in the repository root:
  - Header block: `{{FULL_NAME}}`, `{{EMAIL}}`, `{{PHONE}}`,
    `{{LINKEDIN}}`, `{{PORTFOLIO}}`.
  - `SUMMARY` section: `{{PROFESSIONAL_SUMMARY}}`.
  - Skills section: `{{SKILLS_HEADING}}` (note this itself is
    variant-dependent - see `SKILLS_HEADING_BY_VARIANT` in
    `generator.py`), then one `{{CATEGORY_NAME}}: {{COMMA_SEPARATED_SKILLS}}`
    line per skill category, repeated in the knowledge base's order.
  - `WORK EXPERIENCE` section: repeated per job, most recent first,
    with the exact `" | "` (space-pipe-space) separator on the header
    line that later code parses - flag clearly that this delimiter
    must stay exact if anyone edits the template. Document the
    optional team-context line and how it is omitted for jobs with no
    `team_context`, and the `● {{BULLET}}` bullet format.
  - `EDUCATION` section: one `" | "`-delimited line per entry.
  - Cross-check every placeholder name against `parse_filled_resume()`
    in `generator.py` to confirm the parser actually expects that
    exact token, and flag any mismatch you find.
- Document `README.template.md` section by section the same way:
  header/contact block (note `{{EMAIL_MAILTO}}` versus the plain
  `{{EMAIL}}` display, and the `EMAIL_TAG_ADDRESS` behavior this
  connects to), Skills, Experience (including the `{{TEAM_CONTEXT_ITEM}}`
  bullet-separated-by-`*` format, distinct from the resume template's
  `·`-separated format - call out this difference explicitly since
  it's easy to miss), Education, and the "Career Highlights" section
  which is populated **verbatim** from
  `career_narrative_notes.strongest_differentiators` in the knowledge
  base (the template comment explicitly says do not reword, shorten,
  or reorder these - explain why this one section is verbatim while
  everything else is LLM-generated).
- Document `ANALYSIS_PROMPT.template.txt`: its three placeholders
  (`$output_rules`, `$candidate_data`, `$job_description`), that it is
  a plain `string.Template` file so editing it directly changes
  `--analyze`'s behavior with no Python changes needed, and the exact
  JSON response shape it demands from the LLM (`fit_assessments`,
  `overall_summary`, `upskill_resources`) - read the file directly and
  reproduce its expected JSON shape here as a documented schema, since
  `validate_job_fit_analysis()` in `generator.py` enforces it.
- Add a short "customizing templates" section: since these are plain
  files referenced by `RESUME_TEMPLATE` / `README_TEMPLATE` /
  `ANALYSIS_PROMPT_TEMPLATE`, a user can point those settings at their
  own files instead - note what constraints must be preserved (the
  exact placeholder tokens and delimiters the parsing code expects)
  versus what is safe to restyle freely (wording of surrounding
  headings, emoji, ordering of non-parsed sections).
