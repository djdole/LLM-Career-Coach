"""Tests for small, pure helper functions in generator.py."""

import os

import pytest

import generator


class TestStripEmDashes:
    def test_replaces_em_dash_with_comma(self):
        assert generator.strip_em_dashes("before\u2014after") == "before,after"

    def test_no_em_dash_is_unchanged(self):
        assert generator.strip_em_dashes("nothing to see here") == "nothing to see here"

    def test_multiple_em_dashes(self):
        assert generator.strip_em_dashes("a\u2014b\u2014c") == "a,b,c"


class TestExtractMarkdown:
    def test_plain_text_is_unchanged(self):
        assert generator.extract_markdown("Hello world") == "Hello world"

    def test_strips_fenced_block_with_language(self):
        raw = "```markdown\n# Title\nBody text\n```"
        assert generator.extract_markdown(raw) == "# Title\nBody text"

    def test_strips_fenced_block_without_language(self):
        raw = "```\nHello\n```"
        assert generator.extract_markdown(raw) == "Hello"

    def test_strips_surrounding_whitespace(self):
        raw = "\n\n  Hello world  \n\n"
        assert generator.extract_markdown(raw) == "Hello world"


class TestExtractJsonObject:
    def test_extracts_object_with_no_surrounding_text(self):
        assert generator.extract_json_object('{"a": 1}') == '{"a": 1}'

    def test_extracts_object_with_surrounding_prose(self):
        raw = 'Sure, here you go:\n{"body": "hello"}\nHope that helps!'
        assert generator.extract_json_object(raw) == '{"body": "hello"}'

    def test_handles_nested_braces(self):
        raw = 'prefix {"outer": {"inner": 1}} suffix'
        assert generator.extract_json_object(raw) == '{"outer": {"inner": 1}}'

    def test_raises_when_no_opening_brace(self):
        with pytest.raises(ValueError, match="No '{' found"):
            generator.extract_json_object("no braces at all")

    def test_raises_when_unbalanced(self):
        with pytest.raises(ValueError, match="No balanced closing"):
            generator.extract_json_object("{unbalanced")


class TestRenderFilename:
    def test_basic_substitution(self):
        result = generator.render_filename(
            "{FirstName} {LastName} Resume ({JobAcronym}).{Extension}",
            "Jane Q. Doe", "SDE", "pdf",
        )
        assert result == "Jane Doe Resume (SDE).pdf"

    def test_uses_first_and_last_token_only(self):
        # A middle name/initial should be dropped.
        result = generator.render_filename("{FirstName}_{LastName}", "Dennis Jay Dole", "X", "txt")
        assert result == "Dennis_Dole"

    def test_two_token_name(self):
        result = generator.render_filename("{FirstName} {LastName}", "Jane Doe", "SDET", "docx")
        assert result == "Jane Doe"


class TestComputeJobColumnWidths:
    def test_widths_sum_to_total(self):
        jobs = [
            {"company": "Cosworth Tech Inc. / MAHLE Powertrain LLC", "date_range": "2020-01 - 2021-01"},
            {"company": "Acme", "date_range": "2019 - 2020"},
        ]
        title, employer, date = generator.compute_job_column_widths(jobs, body_pt=10.5, total_pt=500)
        assert title + employer + date == pytest.approx(500)
        assert employer > 0 and date > 0 and title > 0

    def test_longer_company_name_gets_wider_column(self):
        jobs_short = [{"company": "A", "date_range": "2020"}]
        jobs_long = [{"company": "A Very Long Company Name LLC", "date_range": "2020"}]
        _, employer_short, _ = generator.compute_job_column_widths(jobs_short, 10.5, 500)
        _, employer_long, _ = generator.compute_job_column_widths(jobs_long, 10.5, 500)
        assert employer_long > employer_short

    def test_title_floors_at_min_title_pt_for_long_employer(self):
        jobs = [{"company": "X" * 300, "date_range": "Y"}]
        title, _, _ = generator.compute_job_column_widths(jobs, 10.5, 100, min_title_pt=50)
        assert title == 50

    def test_multiple_jobs_uses_the_widest_value(self):
        jobs = [
            {"company": "Short", "date_range": "2020"},
            {"company": "A Very Long Company Name That Is Longest", "date_range": "2019"},
        ]
        _, employer, _ = generator.compute_job_column_widths(jobs, 10.5, 600)
        single_job_long = [{"company": "A Very Long Company Name That Is Longest", "date_range": "2020"}]
        _, employer_single, _ = generator.compute_job_column_widths(single_job_long, 10.5, 600)
        assert employer == employer_single


class TestLoadFileLocationSettings:
    def test_defaults_when_env_unset(self, monkeypatch):
        for key in (
            "OUTPUT_FOLDER", "KNOWLEDGE_BASE", "DATA", "README_TEMPLATE", "README_OUTPUT",
            "RESUME_TEMPLATE", "RESUME_NAMING_TEMPLATE", "COVERLETTER_NAMING_TEMPLATE",
        ):
            monkeypatch.delenv(key, raising=False)
        settings = generator.load_file_location_settings()
        assert settings["OUTPUT_FOLDER"] == "generated"
        assert settings["KNOWLEDGE_BASE"] == "data/resume_data.json"
        assert settings["DATA"] is None
        assert settings["README_TEMPLATE"] == "README.template.md"
        assert settings["README_OUTPUT"] == "README.md"
        assert settings["RESUME_TEMPLATE"] == "RESUME.template.md"
        assert settings["RESUME_NAMING_TEMPLATE"] == "{FirstName} {LastName} Resume ({JobAcronym}).{Extension}"
        assert settings["COVERLETTER_NAMING_TEMPLATE"] == "{FirstName} {LastName} Cover Letter ({JobAcronym}).{Extension}"

    def test_env_vars_override_defaults(self, monkeypatch):
        monkeypatch.setenv("OUTPUT_FOLDER", "custom_output")
        monkeypatch.setenv("README_OUTPUT", "custom_readme.md")
        settings = generator.load_file_location_settings()
        assert settings["OUTPUT_FOLDER"] == "custom_output"
        assert settings["README_OUTPUT"] == "custom_readme.md"


class TestBuildLlmClient:
    def test_exits_when_base_url_missing(self, monkeypatch):
        monkeypatch.delenv("LITELLM_BASE_URL", raising=False)
        monkeypatch.setenv("LITELLM_API_KEY", "key")
        with pytest.raises(SystemExit) as exc_info:
            generator.build_llm_client()
        assert exc_info.value.code == 1

    def test_exits_when_api_key_missing(self, monkeypatch):
        monkeypatch.setenv("LITELLM_BASE_URL", "http://example.com")
        monkeypatch.delenv("LITELLM_API_KEY", raising=False)
        with pytest.raises(SystemExit) as exc_info:
            generator.build_llm_client()
        assert exc_info.value.code == 1

#    def test_builds_client_with_v1_suffix(self, monkeypatch):
#        monkeypatch.setenv("LITELLM_BASE_URL", "http://example.com")
#        monkeypatch.setenv("LITELLM_API_KEY", "secret")
#        client = generator.build_llm_client()
#        assert str(client.base_url) == "http://example.com/v1"
#        assert client.api_key == "secret"

#    def test_strips_trailing_slash_before_appending_v1(self, monkeypatch):
#        monkeypatch.setenv("LITELLM_BASE_URL", "http://example.com/")
#        monkeypatch.setenv("LITELLM_API_KEY", "secret")
#        client = generator.build_llm_client()
#        assert str(client.base_url) == "http://example.com/v1"
