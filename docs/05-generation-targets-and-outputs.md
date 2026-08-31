# Generation Targets and Output Formats

## Output formats

| Target | Files per variant | Formats |
|---|---|---|
| `resume` | 1 per `VARIANTS` entry (`SDE`, `SDET` by default) | `.json`, `.txt`, `.md`, `.pdf`, `.docx` (5) |
| `cover_letter` | 1 per `VARIANTS` entry | `.txt`, `.pdf`, `.docx` (3) |
| `readme` | 1 | `.md`, written to `README_OUTPUT` |
| `profile` | 1 | `.json`, written to `KNOWLEDGE_BASE_DRAFT` |
| `analyze` | 0 files - printed to stdout only | `.md` (rendered, not saved) |

Two notes worth calling out, both confirmed by reading `main()`
directly rather than assuming the tables in the root `USAGE.md`:

* **Cover letters are only ever written as `.txt`, `.pdf`, and
  `.docx`.** `render_cover_letter_md()` exists in `generator.py` and
  works fine if called, but `main()` never calls it - only
  `render_cover_letter_txt()`, `render_cover_letter_docx()`, and
  `render_cover_letter_pdf()` are invoked for the `cover_letter`
  target. There is no cover letter Markdown output.
* **The `analyze` target's report is never written to a file.**
  `.env.template` and the root `USAGE.md` describe an
  `ANALYSIS_NAMING_TEMPLATE`-named file under `OUTPUT_FOLDER` as an
  additional destination for the job-fit report, but `main()` only
  calls `print(rendered_job_fit_analysis_report)` - `ANALYSIS_NAMING_TEMPLATE`
  is not read anywhere in `generator.py`. See `12-troubleshooting-faq.md`
  for the workaround (redirect stdout yourself).

## The `resume` target

**Inputs:** `KNOWLEDGE_BASE`, `RESUME_TEMPLATE`, the active `VARIANTS`
list.

**Pipeline**, one pass per variant in `VARIANTS`:

1. `build_baseline_context(kb, variant)` trims the full knowledge base
   down to only what this one variant's resume needs: the variant's
   professional summary (falling back to the `"SDE"` entry if the
   variant has none of its own), skill categories with pre-formatted
   display labels, work history with per-variant job titles and
   variant-specific bullets filtered in, and education entries
   normalized to the output schema's field names. Trimming keeps the
   prompt smaller (token budget) and removes JD-tailoring-only fields
   that have shown up verbatim in bad output before this trimming
   existed.
2. `build_resume_fill_prompt(kb, variant, template_text)` wraps that
   trimmed context and `RESUME_TEMPLATE`'s text into the system prompt
   sent to the LLM, instructing it to preserve the template's exact
   structure and delimiters and only replace `{{PLACEHOLDER}}` tokens.
3. `call_llm_fill_resume(client, kb, variant, template_text)` sends
   that prompt to LiteLLM, then calls `parse_filled_resume()` on the
   response. If parsing fails, or the parsed result has a different
   number of jobs than the knowledge base, it retries once with a
   corrective follow-up message before giving up and exiting.
4. `parse_filled_resume(text)` parses the filled-in, pipe-delimited
   plain-text template back into a structured dict (name, contact
   line, summary, skills, work experience, education) that the
   renderers below expect. It raises `ValueError` on any structural
   mismatch (missing headers, wrong number of pipe-separated fields, a
   job with no bullets), which is what triggers the retry in step 3.
5. One `render_resume_*()` call per output format: `render_resume_txt()`,
   `render_resume_md()`, `render_resume_pdf()`, and `render_resume_docx()`,
   plus the resume dict being written directly as `.json` in `main()`.

`compute_job_column_widths()` sizes the title/employer/date columns in
the PDF and DOCX work-experience layout based on the *actual* text in
this resume at this font size, rather than fixed percentages. A fixed
split would overflow whenever a company name is longer than whatever
guess produced the split, forcing it to wrap mid-name; instead,
employer and date columns each get exactly what their longest actual
value needs, and the title column gets whatever space is left over
(with a floor, so a long employer name cannot crush the title column
to nothing).

`strip_em_dashes()` is a belt-and-suspenders post-process: the model is
told never to use an em dash (`never_use_em_dash` in `output_rules`),
and this function replaces any em dash that slips through anyway with
a comma in the rendered text. It is not a substitute for the model
actually following the rule - the PDF/DOCX story-building and
plain-text renderers all call it on user-visible text before writing
it out.

## The `cover_letter` target

Same variant loop as `resume`, reusing the exact same `VARIANTS` list:

1. `build_cover_letter_prompt(kb, variant)` builds a prompt asking the
   model to lightly adapt `cover_letter_generic_template` from the
   knowledge base's `cover_letter_building_blocks` section, keeping
   "Dear Hiring Manager," and responding with a `{"body": "..."}` JSON
   object.
2. `call_llm_cover_letter(client, kb, variant)` sends that prompt,
   requesting JSON-mode from LiteLLM where supported (falling back to
   a plain request if the proxy rejects `response_format`), then
   extracts and validates the JSON body, retrying once on failure.
3. Rendered via `render_cover_letter_txt()`, `render_cover_letter_docx()`,
   and `render_cover_letter_pdf()` - see the note above about
   `render_cover_letter_md()` existing but never being called.

## The `readme` target

1. `build_readme_context(kb)` builds a variant-agnostic context (the
   profile README always uses the `"SDE"` summary and job titles),
   adding a `personal_info.email_mailto` field alongside the untouched
   `personal_info.email` - the template uses `email` for the text
   displayed on the page and `email_mailto` for the address inside the
   `mailto:` link, so `EMAIL_TAG_ADDRESS` can tag the link without
   changing what is shown.
2. `build_readme_system_prompt(kb, template_text)` wraps that context
   and `README_TEMPLATE`'s text into the system prompt, with explicit
   instructions to reproduce `career_highlights` items verbatim and to
   never swap or merge the `email`/`email_mailto` fields.
3. `call_llm_readme(client, kb, template_text)` sends the prompt, then
   validates the response with `validate_readme()`, retrying once on
   failure.
4. `validate_readme(md, expected_job_count)` checks that the response
   has a top-level `# ` heading, contains every required section
   header (Skills, Experience, Education, Career Highlights), has no
   leftover `{{placeholder}}` tokens, contains no em dash, and has
   exactly as many `### ` job entries as the knowledge base has jobs
   (catching a dropped or duplicated job).
5. The validated Markdown is written to `README_OUTPUT`.

`build_tagged_email()` is what actually builds the tagged address
described above: given an email and an optional tag, it returns
`local+tag@domain`, or the email unchanged if the tag is blank or the
email does not look like a single-`@` address.

## The `profile` target (`--generate profile`)

This is the knowledge-base maintenance workflow, orchestrated end to
end by `generate_profile_draft(client, s)`:

1. **Requires `DATA` to be set.** If it is unset, the function prints
   `[profile] DATA is not set; skipping.` and returns immediately - no
   error, no output.
2. `build_source_file_list(data_dir, knowledge_base_path, draft_path)`
   scans `DATA`'s immediate contents (not subfolders) for candidate
   source files: every regular, non-hidden file except the knowledge
   base file itself and any pre-existing draft output. If the folder
   does not exist, or nothing is left after those exclusions, the
   function prints a "no source files found" message and returns -
   again, no error.
3. `extract_text_from_source_file(path)` pulls plain text out of each
   supported format: `.json`/`.txt`/`.md`/`.xml` are read directly as
   text, `.docx` text comes from paragraphs plus a `" | "`-joined dump
   of any tables, and `.pdf` text comes from `pypdf`'s per-page
   extraction. An unsupported extension, or any read error, logs a
   message and contributes empty text rather than aborting the whole
   run - one bad file does not sink the batch.
4. `build_profile_prompt(existing_kb, source_texts)` builds the system
   prompt, branching on whether an existing knowledge base was found:
   a from-scratch build (no `KNOWLEDGE_BASE` file yet) gets
   "build a new one from these sources" instructions, while an update
   gets explicit non-destructive instructions - preserve every
   existing field unless a source document clearly updates that exact
   fact, only add or modify, never remove or shorten.
5. `call_llm_update_profile(client, existing_kb, source_texts)` sends
   that prompt, parses the JSON response, and validates it with
   `validate_profile_draft(data, existing_kb)`, retrying once on
   failure.
6. `validate_profile_draft()` checks the result is a JSON object
   containing at minimum `personal_info`, `education`, `skills`, and
   `work_experience`, and - when there was an existing knowledge base -
   that no top-level section present there is missing from the draft.
7. The validated draft is written to `KNOWLEDGE_BASE_DRAFT` (a naming
   template - see `03-configuration.md`), and every consumed source
   file is deleted from `DATA` so it is not re-processed on the next
   run.

**"Non-destructive" precisely:** the merge is *structure-preserving* -
no top-level section in the existing knowledge base can disappear from
the draft. It does **not** mean the original file on disk is left
untouched: with the default settings (`KNOWLEDGE_BASE_DRAFT` equal to
`KNOWLEDGE_BASE`), a successful run overwrites the knowledge base
directly. Point `KNOWLEDGE_BASE_DRAFT` at a different path if you want
a review step before promoting a draft.

## The `analyze` target (`--analyze`)

See `04-cli-usage.md` for how `--analyze`'s value is resolved into job
description text (URL, local file, or literal text) - that logic lives
in `resolve_job_description()` and is not repeated here. Once resolved:

1. `build_job_fit_context(kb)` builds a context spanning **both**
   variants' skills and work-experience bullets (unlike the resume's
   `build_baseline_context`, which is scoped to one variant), since
   judging fit against an arbitrary posting needs the candidate's full
   skill set, not just what one resume variant would show.
2. `build_job_fit_prompt(kb, job_description, prompt_template_text)`
   fills `ANALYSIS_PROMPT_TEMPLATE`'s contents (a `string.Template`
   file, not an f-string or `str.format` template - deliberately, so
   the template's JSON schema example can use literal `{`/`}`
   characters without escaping) with the trimmed context and the job
   description.
3. `call_llm_analyze_fit(client, kb, job_description, prompt_template_text)`
   sends the prompt (requesting JSON mode where supported), parses the
   response, and validates it with `validate_job_fit_analysis()`,
   retrying once on failure.
4. `validate_job_fit_analysis()` checks the required top-level keys
   are present, `overall_summary` is a non-empty string,
   `fit_assessments` is a non-empty list where each entry has a
   `list_label`, an in-range numeric `fit_percentage`, a non-empty
   `assessment_summary`, and a list of `missing_qualifications`
   strings, and that `upskill_resources` entries each have a
   `missing_item` and `resource_name`.
5. `render_job_fit_analysis_md(analysis)` renders the validated result
   as a Markdown report. When the job description did not separate its
   qualifications into distinct lists, `fit_assessments` has exactly
   one entry and the report is rendered flat (one fit score, one
   summary, one matched/missing pair). When it did (for example
   "Required" vs. "Preferred"), each list gets its own scored section
   under an overall summary. `_render_matched_and_missing_md()` is the
   shared helper that renders one assessment's matched and missing
   qualifications as Markdown bullet lists, reused by both branches at
   different heading levels.
6. The rendered report is printed to stdout (see the note in
   [Output formats](#output-formats) above about it not being written
   to a file).

## Parsing helpers shared across targets

`extract_json_object(raw)` and `extract_markdown(raw)` both exist to
tolerate a model that adds something extra around the response it was
asked for, despite being told not to:

* `extract_json_object()` finds the first `{` in the raw response and
  walks forward tracking brace depth until it finds the matching
  closing `}`, returning just that balanced substring - so stray prose
  or a markdown code fence around a JSON object does not break parsing.
* `extract_markdown()` strips a single wrapping ` ``` ` fence (with an
  optional language tag) if the model wrapped its entire Markdown or
  resume-template response in one, despite being told not to.
