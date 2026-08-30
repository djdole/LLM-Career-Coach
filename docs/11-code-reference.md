# Code Reference (`generator.py`)

## TODO Documentation Tasks

This file should become a function-by-function reference for
`generator.py` (roughly 2200 lines, single-file script). Read each
function's full body before documenting it, not just its signature -
the goal is a reader being able to understand what a function does and
why without opening the source. Group functions under the headings
below, matching their order of appearance in `generator.py`, and for
each function document: purpose (one or two sentences), parameters
and return value in plain language, and any side effects (file writes,
network calls, process exits).

- **CLI and argument parsing**
  - `build_arg_parser()`
  - `parse_generate_targets()`
- **LLM client setup**
  - `build_llm_client()` - document the required-setting exit behavior
    here specifically (missing `LITELLM_BASE_URL`/`LITELLM_API_KEY`).
- **Resume generation**
  - `compute_job_column_widths()`
  - `strip_em_dashes()`
  - `build_baseline_context()`
  - `build_resume_fill_prompt()`
  - `parse_filled_resume()`
  - `call_llm_fill_resume()`
  - `extract_json_object()`
- **Cover letter generation**
  - `build_cover_letter_prompt()`
  - `call_llm_cover_letter()`
- **Rendering (text/Markdown/DOCX/PDF)**
  - `render_resume_txt()`, `render_resume_md()`
  - `render_cover_letter_txt()`, `render_cover_letter_md()`
  - `_tight()` (DOCX paragraph spacing helper)
  - `render_resume_docx()`, `render_cover_letter_docx()`
  - `_build_resume_story()` (shared PDF story-building helper)
  - `render_resume_pdf()`, `render_cover_letter_pdf()`
- **GitHub profile README generation**
  - `build_tagged_email()`
  - `build_readme_context()`
  - `build_readme_system_prompt()`
  - `extract_markdown()`
  - `validate_readme()`
  - `call_llm_readme()`
- **Knowledge base maintenance (`--generate profile`)**
  - `extract_text_from_source_file()`
  - `build_source_file_list()`
  - `build_profile_prompt()`
  - `validate_profile_draft()`
  - `call_llm_update_profile()`
  - `fetch_knowledge_base_json()`
  - `load_knowledge_base()`
  - `generate_profile_draft()`
- **Job-fit analysis (`--analyze`)**
  - `_strip_html()`
  - `_fetch_job_description_from_url()`
  - `resolve_job_description()`
  - `build_job_fit_context()`
  - `build_job_fit_prompt()`
  - `validate_job_fit_analysis()`
  - `call_llm_analyze_fit()`
  - `render_job_fit_analysis_md()`
  - `_render_matched_and_missing_md()`
- **Settings, naming templates, and file locations**
  - `parse_variants_env()`
  - `load_file_location_settings()`
  - `_NowPlaceholder` (class) - explain what problem this class solves
    for `{datetime.now}`-style placeholders specifically.
  - `render_filename()`
  - `ensure_parent_dir_exists()`
- **Output repository (`OUTPUT_REPO`) git operations**
  - `_run_git()`
  - `_inject_repo_token()`
  - `_resolve_output_repo_target_ref()`
  - `sync_output_repo()`
  - `commit_and_push_output_repo()`
- **Entry point**
  - `main()` - document the overall control flow: settings loading,
    knowledge base loading, dispatch to each requested `--generate`
    target and/or `--analyze`, and where `OUTPUT_REPO` sync/commit
    fits into that sequence.

Once every function above has a real entry, add a short "module
constants" subsection documenting any top-level constants read while
writing the functions above (for example `SKILLS_HEADING_BY_VARIANT`,
referenced from `03-configuration.md`'s `VARIANTS` explanation).
