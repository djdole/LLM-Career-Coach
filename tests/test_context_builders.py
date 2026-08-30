"""Tests for build_baseline_context, build_readme_context, and the prompt
builder functions that wrap them."""

import generator


class TestBuildBaselineContext:
    def test_uses_variant_specific_summary(self, sample_kb):
        ctx_sde = generator.build_baseline_context(sample_kb, "SDE")
        ctx_sdet = generator.build_baseline_context(sample_kb, "SDET")
        assert ctx_sde["summary"] == "SDE summary."
        assert ctx_sdet["summary"] == "SDET summary."

    def test_skills_heading_by_variant(self, sample_kb):
        assert generator.build_baseline_context(sample_kb, "SDE")["skills_heading"] == "CORE TECHNICAL SKILLS"
        assert generator.build_baseline_context(sample_kb, "SDET")["skills_heading"] == "CORE SDET SKILLS"

    def test_skills_heading_falls_back_for_unlisted_variant(self, sample_kb):
        # Only SDE/SDET have custom wording in SKILLS_HEADING_BY_VARIANT -
        # any other VARIANTS entry (e.g. VARIANTS=SDE,SDET,SRE) should get
        # a generic heading instead of a KeyError.
        assert generator.build_baseline_context(sample_kb, "SRE")["skills_heading"] == "CORE SRE SKILLS"

    def test_output_rules_trimmed_to_two_keys(self, sample_kb):
        ctx = generator.build_baseline_context(sample_kb, "SDE")
        assert set(ctx["output_rules"].keys()) == {"never_fabricate", "never_use_em_dash"}

    def test_skills_use_known_category_label(self, sample_kb):
        ctx = generator.build_baseline_context(sample_kb, "SDE")
        categories = {s["category"]: s["items"] for s in ctx["skills"]}
        assert categories["Languages"] == ["Python", "Go"]

    def test_skills_fall_back_to_title_case_for_unknown_category(self, sample_kb):
        ctx = generator.build_baseline_context(sample_kb, "SDE")
        categories = [s["category"] for s in ctx["skills"]]
        assert "Operating Systems" in categories

    def test_non_list_skill_entries_are_excluded(self, sample_kb):
        ctx = generator.build_baseline_context(sample_kb, "SDE")
        categories = [s["category"] for s in ctx["skills"]]
        assert not any("guidance" in c.lower() for c in categories)

    def test_job_title_falls_back_when_variant_missing(self, sample_kb):
        # The second job in sample_kb only has an "SDE" title, no "SDET".
        ctx = generator.build_baseline_context(sample_kb, "SDET")
        beta_job = next(j for j in ctx["work_experience"] if j["company"] == "Beta Inc")
        assert beta_job["title"] == "Junior Engineer"

    def test_alt_bullets_are_dropped(self, sample_kb):
        ctx = generator.build_baseline_context(sample_kb, "SDE")
        acme_job = next(j for j in ctx["work_experience"] if j["company"] == "Acme Corp")
        assert acme_job["bullets"] == ["Built the widget service."]

    def test_team_context_defaults_to_empty_string(self, sample_kb):
        ctx = generator.build_baseline_context(sample_kb, "SDE")
        beta_job = next(j for j in ctx["work_experience"] if j["company"] == "Beta Inc")
        assert beta_job["team_context"] == ""

    def test_date_range_is_formatted(self, sample_kb):
        ctx = generator.build_baseline_context(sample_kb, "SDE")
        acme_job = next(j for j in ctx["work_experience"] if j["company"] == "Acme Corp")
        assert acme_job["date_range"] == "2020-01 - 2023-01"

    def test_education_graduation_date_renamed_to_date(self, sample_kb):
        ctx = generator.build_baseline_context(sample_kb, "SDE")
        assert ctx["education"][0]["date"] == "2015"
        assert "graduation date" not in ctx["education"][0]

    def test_includes_cover_letter_generic_template(self, sample_kb):
        ctx = generator.build_baseline_context(sample_kb, "SDE")
        assert ctx["cover_letter_generic_template"] == sample_kb["cover_letter_building_blocks"]["generic_fallback_template"]


class TestBuildReadmeContext:
    def test_uses_sde_titles_regardless_of_variant(self, sample_kb):
        ctx = generator.build_readme_context(sample_kb)
        acme_job = next(j for j in ctx["work_experience"] if j["company"] == "Acme Corp")
        assert acme_job["title"] == "Software Engineer"

    def test_falls_back_to_first_variant_when_sde_missing(self, sample_kb):
        sample_kb["work_experience"][0]["title_by_variant"] = {"SDET": "SDET Only Title"}
        ctx = generator.build_readme_context(sample_kb)
        acme_job = next(j for j in ctx["work_experience"] if j["company"] == "Acme Corp")
        assert acme_job["title"] == "SDET Only Title"

    def test_includes_field_of_study_and_graduation_date(self, sample_kb):
        ctx = generator.build_readme_context(sample_kb)
        edu = ctx["education"][0]
        assert edu["field_of_study"] == "Computer Science"
        assert edu["graduation_date"] == "2015"

    def test_career_highlights_present(self, sample_kb):
        ctx = generator.build_readme_context(sample_kb)
        assert ctx["career_highlights"] == ["Ships fast.", "Deep testing background."]

    def test_career_highlights_defaults_to_empty_list_when_absent(self, sample_kb):
        del sample_kb["career_narrative_notes"]
        ctx = generator.build_readme_context(sample_kb)
        assert ctx["career_highlights"] == []

    def test_missing_field_of_study_defaults_to_empty_string(self, sample_kb):
        del sample_kb["education"][0]["field of study"]
        ctx = generator.build_readme_context(sample_kb)
        assert ctx["education"][0]["field_of_study"] == ""

    def test_email_mailto_matches_email_when_tag_address_unset(self, sample_kb, monkeypatch):
        monkeypatch.delenv("EMAIL_TAG_ADDRESS", raising=False)
        ctx = generator.build_readme_context(sample_kb)
        assert ctx["personal_info"]["email_mailto"] == ctx["personal_info"]["email"] == "jane@example.com"

    def test_email_mailto_gets_tag_when_email_tag_address_set(self, sample_kb, monkeypatch):
        monkeypatch.setenv("EMAIL_TAG_ADDRESS", "resume")
        ctx = generator.build_readme_context(sample_kb)
        assert ctx["personal_info"]["email_mailto"] == "jane+resume@example.com"
        # The displayed email is untouched.
        assert ctx["personal_info"]["email"] == "jane@example.com"

    def test_does_not_mutate_the_original_knowledge_base_dict(self, sample_kb, monkeypatch):
        monkeypatch.setenv("EMAIL_TAG_ADDRESS", "resume")
        generator.build_readme_context(sample_kb)
        assert "email_mailto" not in sample_kb["personal_info"]


class TestBuildResumeFillPrompt:
    def test_includes_template_text_verbatim(self, sample_kb, resume_template_text):
        prompt = generator.build_resume_fill_prompt(sample_kb, "SDE", resume_template_text)
        assert resume_template_text in prompt

    def test_includes_serialized_candidate_data(self, sample_kb, resume_template_text):
        prompt = generator.build_resume_fill_prompt(sample_kb, "SDE", resume_template_text)
        assert '"skills_heading": "CORE TECHNICAL SKILLS"' in prompt
        assert "Acme Corp" in prompt

    def test_mentions_variant(self, sample_kb, resume_template_text):
        prompt = generator.build_resume_fill_prompt(sample_kb, "SDET", resume_template_text)
        assert "SDET" in prompt


class TestBuildCoverLetterPrompt:
    def test_includes_output_rules_and_template(self, sample_kb):
        prompt = generator.build_cover_letter_prompt(sample_kb, "SDE")
        assert "never_fabricate" in prompt
        assert sample_kb["cover_letter_building_blocks"]["generic_fallback_template"] in prompt

    def test_requests_json_object_shape(self, sample_kb):
        prompt = generator.build_cover_letter_prompt(sample_kb, "SDE")
        assert '{"body"' in prompt


class TestBuildReadmeSystemPrompt:
    def test_includes_template_text_verbatim(self, sample_kb, readme_template_text):
        prompt = generator.build_readme_system_prompt(sample_kb, readme_template_text)
        assert readme_template_text in prompt

    def test_includes_career_highlights_instruction(self, sample_kb, readme_template_text):
        prompt = generator.build_readme_system_prompt(sample_kb, readme_template_text)
        assert "career_highlights" in prompt

    def test_includes_email_and_email_mailto_disambiguation_instruction(self, sample_kb, readme_template_text):
        prompt = generator.build_readme_system_prompt(sample_kb, readme_template_text)
        assert "email_mailto" in prompt

    def test_serialized_candidate_data_includes_both_email_fields(self, sample_kb, readme_template_text, monkeypatch):
        monkeypatch.setenv("EMAIL_TAG_ADDRESS", "resume")
        prompt = generator.build_readme_system_prompt(sample_kb, readme_template_text)
        assert '"email": "jane@example.com"' in prompt
        assert '"email_mailto": "jane+resume@example.com"' in prompt