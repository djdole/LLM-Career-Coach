# Templates

## The general idea

`RESUME_TEMPLATE` and `README_TEMPLATE` are plain Markdown (or,
for the resume, plain-text-with-Markdown-like-structure) files
containing `{{PLACEHOLDER}}` tokens and HTML comments that give
repetition instructions (for example "repeat this block once per
job"). The LLM is given the template's text plus the candidate's
knowledge base and asked to produce a filled-in copy - it does not
generate the structure itself, only the content that goes into it.

`ANALYSIS_PROMPT_TEMPLATE` is a different kind of template entirely: a
[`string.Template`](https://docs.python.org/3/library/string.html#template-strings)
text file used to build the *prompt sent to the LLM* for `--analyze`,
not a document that gets filled in and rendered the same way as the
other two. See `build_job_fit_prompt()` in `generator.py`.

## `RESUME.template.md`

Reading the file in the repository root, section by section:

* **Header block:** `{{FULL_NAME}}` on its own line, then a contact
  line: `{{EMAIL}} · {{PHONE}} · {{LINKEDIN}} · {{PORTFOLIO}}`
  (middot-separated).
* **`SUMMARY` section:** the literal header `SUMMARY`, followed by
  `{{PROFESSIONAL_SUMMARY}}`.
* **Skills section:** `{{SKILLS_HEADING}}` as the header line - this
  itself is variant-dependent (see `SKILLS_HEADING_BY_VARIANT` in
  `generator.py`: `"SDE"` and `"SDET"` each get their own wording,
  and any other `VARIANTS` entry falls back to a generic
  `"CORE <VARIANT> SKILLS"` heading). After that, one
  `{{CATEGORY_NAME}}: {{COMMA_SEPARATED_SKILLS}}` line per skill
  category, repeated in the knowledge base's order, per the template's
  HTML comment.
* **`WORK EXPERIENCE` section:** repeated per job, most recent first.
  The job header line uses the exact `" | "` (space-pipe-space)
  separator - `{{JOB_TITLE}} | {{COMPANY}} | {{START_MONTH_YEAR}} to
  {{END_MONTH_YEAR}}` - and this delimiter must stay exact if anyone
  edits the template, since `parse_filled_resume()` splits this line
  on `|` and expects exactly three parts. An optional team-context
  line follows (`{{TEAM_CONTEXT_ITEM}} · {{TEAM_CONTEXT_ITEM}} · ...`,
  middot-separated), omitted entirely for a job with no
  `team_context`. Then one `● {{BULLET}}` line per bullet, using the
  literal bullet character `●` (`BULLET_CHAR` in `generator.py`).
* **`EDUCATION` section:** one `{{DEGREE}} | {{INSTITUTION}} |
  {{GRADUATION_DATE}}` line per entry, again `" | "`-delimited and
  parsed the same strict way.

Cross-checking every placeholder against `parse_filled_resume()`: the
parser expects exactly this shape (name line, contact line, blank,
`SUMMARY` header, summary text, blank, a skills-heading line, skill
lines until a blank or `WORK EXPERIENCE`, the `WORK EXPERIENCE` header,
one job block per job with an optional team-context line and one or
more `●`-prefixed bullets, the `EDUCATION` header, then pipe-delimited
education lines) - no mismatch was found between the template's
placeholders/delimiters and what the parser actually expects.

## `README.template.md`

Reading the file in the repository root, section by section:

* **Header/contact block:** `{{FULL_NAME}}` in the `# Hi, I'm ...`
  heading, `{{PROFESSIONAL_SUMMARY}}`, then a contact block with
  `{{LOCATION}}`, an email line, `{{PHONE}}`, an ORCID link, and
  LinkedIn/portfolio links. The email line is the one place this
  template differs meaningfully from the resume template: it uses
  **two distinct placeholders**, `{{EMAIL}}` for the *displayed* text
  and `{{EMAIL_MAILTO}}` for the address inside the `mailto:` link -
  `[{{EMAIL}}](mailto:{{EMAIL_MAILTO}})`. This is what
  `EMAIL_TAG_ADDRESS` (see `03-configuration.md`) connects to:
  `build_readme_context()` sets `personal_info.email_mailto` to the
  tagged address while leaving `personal_info.email` untouched, and
  the system prompt explicitly warns the model never to swap or merge
  the two.
* **Skills:** one `**{{CATEGORY_NAME}}:** {{COMMA_SEPARATED_SKILLS}}`
  line per category, same repetition rule as the resume template.
* **Experience:** repeated per job, most recent first. The header uses
  `###`/`####` Markdown headings rather than a pipe-delimited line
  (this template is not parsed with the resume's strict delimiter
  rules), and the optional team-context line is
  `* {{TEAM_CONTEXT_ITEM}} * {{TEAM_CONTEXT_ITEM}} * ... *` -
  **asterisk-separated**, distinct from the resume template's
  middot-separated (`·`) team-context line. This difference is easy to
  miss since both are called "team context" and both live in roughly
  the same place in each template. Bullets use plain Markdown `-`
  bullets rather than the resume's `●` character.
* **Education:** one block per entry, including
  `{{FIELD_OF_STUDY}}` alongside degree, institution, and graduation
  date - a field the resume template does not surface.
* **Career Highlights:** populated **verbatim** from
  `career_narrative_notes.strongest_differentiators` in the knowledge
  base. The template's own HTML comment says explicitly: do not
  reword, shorten, or reorder these. This is the one section in either
  template that is copied through as-is rather than generated by the
  LLM - `build_readme_system_prompt()` reiterates this instruction
  outside the template comment too, because everywhere else in the
  README the LLM is generating or lightly rephrasing content, so this
  section needs an explicit carve-out to make the "just copy this part"
  behavior reliable.

`personal_info`'s exact sub-field names (`linkedin`, `portfolio`,
`location`, `orcid`, and so on implied by this template's placeholders)
are not read as literal keys anywhere in `generator.py` - the code
passes `kb["personal_info"]` through to the LLM almost entirely
verbatim (only `full_name` and `email` are read explicitly by name).
The LLM is expected to find whatever `personal_info` sub-fields it
needs to fill in `{{LOCATION}}`, `{{ORCID_URL}}`, `{{LINKEDIN_DISPLAY}}`,
`{{LINKEDIN_URL}}`, `{{PORTFOLIO_DISPLAY}}`, and `{{PORTFOLIO_URL}}`
directly from whatever `personal_info` contains - see
`07-knowledge-base-schema.md` for more on this.

## `ANALYSIS_PROMPT.template.txt`

A plain `string.Template` file (`$placeholder` syntax, not
`{{placeholder}}`), with exactly three placeholders:

| Placeholder | Filled with |
|---|---|
| `$output_rules` | `kb["meta"]["output_rules"]["never_fabricate"]`, as JSON. |
| `$candidate_data` | The trimmed job-fit context from `build_job_fit_context()`, as JSON. |
| `$job_description` | The resolved job description text (see `resolve_job_description()`). |

Because it is a `string.Template` file rather than an f-string or
`str.format()` template, editing it directly changes `--analyze`'s
behavior with no Python changes needed - and the template can freely
use literal `{`/`}` characters (needed for its JSON schema example)
without escaping them, which would be required under `str.format()`.

The template demands a specific JSON response shape from the LLM,
enforced by `validate_job_fit_analysis()` in `generator.py`:

```json
{
  "fit_assessments": [
    {
      "list_label": "string",
      "fit_percentage": 0,
      "assessment_summary": "string",
      "matched_qualifications": ["string", "..."],
      "missing_qualifications": ["string", "..."]
    }
  ],
  "overall_summary": "string",
  "upskill_resources": [
    {
      "missing_item": "string",
      "resource_name": "string",
      "resource_type": "course | tutorial | book | documentation | video",
      "resource_url": "string (optional)",
      "is_free": true
    }
  ]
}
```

`fit_assessments` has one entry per qualifications list the job
description separates out (for example "Required" vs. "Preferred"), or
exactly one entry (`list_label` set to `"Overall Qualifications"`) if
the posting does not separate its qualifications at all.
`matched_qualifications` on an assessment and `resource_url`/`is_free`
on a resource are the only fields not strictly required by the
validator - a model that omits a real URL it is not confident about,
rather than inventing one, should not fail validation over it (see
`never_fabricate` in `output_rules`).

## Customizing templates

`RESUME_TEMPLATE`, `README_TEMPLATE`, and `ANALYSIS_PROMPT_TEMPLATE`
are just file paths in `.env` - point them at your own files instead
of the shipped ones to restyle any of the three.

**Must stay exact**, or the corresponding parser/validator will reject
the LLM's output and force retries (or fail the run after two failed
attempts):

* The `RESUME_TEMPLATE`'s `" | "` delimiters on job-header and
  education lines, and its `●` bullet character - `parse_filled_resume()`
  depends on all of these exactly.
* The `README_TEMPLATE`'s required section headers
  (`## 🛠️ Skills`, `## 💼 Experience`, `## 🎓 Education`,
  `## ✨ Career Highlights`, matched verbatim including the emoji) and
  its top-level `# ` heading - `validate_readme()` checks for all of
  these by exact string match.
* The `ANALYSIS_PROMPT_TEMPLATE`'s three `$output_rules`/
  `$candidate_data`/`$job_description` placeholders, and the JSON
  shape it asks the model to return - `validate_job_fit_analysis()`
  enforces that shape regardless of how the surrounding prompt text is
  worded.

**Safe to restyle freely:** wording of surrounding headings and
instructions, emoji choice (outside the README's required headers),
ordering of sections the parser does not depend on positionally (for
example the exact wording of the resume's `SUMMARY` prose, or the
README's intro paragraph), and any additional Markdown styling that
does not remove or rename a required token.
