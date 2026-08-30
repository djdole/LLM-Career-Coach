# Generation Targets and Output Formats

## TODO Documentation Tasks

- Add the "Output formats" table from `USAGE.md`: for each target
  (`resume`, `cover_letter`, `readme`, `profile`, `analyze`), how many
  files per variant, and which formats. Verify current formats by
  reading the render functions in `generator.py`
  (`render_resume_txt`, `render_resume_md`, `render_resume_docx`,
  `render_resume_pdf`, and the resume JSON output path in `main()`;
  `render_cover_letter_txt`, `render_cover_letter_md` note - confirm
  whether cover letter Markdown is actually written to disk anywhere
  in `main()` or only used internally, since `USAGE.md` lists cover
  letters as pdf/docx/txt only).
- Document the **resume** target end to end:
  - Inputs: `KNOWLEDGE_BASE`, `RESUME_TEMPLATE`, the active `VARIANTS`
    list.
  - Pipeline: `build_baseline_context()` -> `build_resume_fill_prompt()`
    -> `call_llm_fill_resume()` -> `parse_filled_resume()` -> one
    `render_resume_*()` call per output format. Read each of these
    functions in `generator.py` and summarize what each stage actually
    does in a sentence or two, not just its name.
  - Explain `compute_job_column_widths()`'s role in the PDF/DOCX
    layout (column sizing for the work-experience table) at a level a
    non-Python-reader can follow.
  - Explain `strip_em_dashes()`'s purpose: the LLM's raw output is
    post-processed to remove em dashes from generated text.
- Document the **cover_letter** target the same way:
  `build_cover_letter_prompt()` -> `call_llm_cover_letter()` -> render
  functions. Note it reuses the same `VARIANTS` list as resumes.
- Document the **readme** target: `build_readme_context()` ->
  `build_readme_system_prompt()` -> `call_llm_readme()` ->
  `validate_readme()` (explain what it checks, for example the
  expected job count) -> written to `README_OUTPUT`. Mention
  `build_tagged_email()`'s role here specifically (plus-addressing the
  mailto link only).
- Document the **profile** target (`--generate profile`), which is the
  knowledge-base maintenance workflow:
  - Requires `DATA` to be set; a no-op otherwise.
  - `build_source_file_list()` scans `DATA`'s immediate contents for
    source documents (pdf/txt/json/xml/docx).
  - `extract_text_from_source_file()` pulls text out of each supported
    format - list which formats and any format-specific caveats found
    in that function.
  - `build_profile_prompt()` -> `call_llm_update_profile()` ->
    `validate_profile_draft()` -> written to `KNOWLEDGE_BASE_DRAFT`.
  - Explain precisely what "non-destructive" means here (from
    `USAGE.md`): the merge is structure-preserving (no top-level
    section in the existing knowledge base can disappear from the
    draft), but this does NOT mean the original file on disk is left
    untouched - with default settings the draft overwrites
    `KNOWLEDGE_BASE` directly, unless `KNOWLEDGE_BASE_DRAFT` points
    elsewhere.
  - Read `generate_profile_draft()` (around line 1307) for the full
    orchestration of this target and describe it step by step.
- Document the **analyze** target's output rendering: `build_job_fit_context()`
  -> `build_job_fit_prompt()` -> `call_llm_analyze_fit()` ->
  `validate_job_fit_analysis()` -> `render_job_fit_analysis_md()` (and
  its helper `_render_matched_and_missing_md()`). Cross-reference
  `04-cli-usage.md` for the `--analyze` flag's input-resolution rules
  instead of repeating them here.
- Add a short section on `extract_json_object()` and `extract_markdown()`:
  explain in plain terms that these strip an LLM response down to just
  the JSON object or Markdown body expected, tolerating extra prose or
  code fences the model might add around it.
