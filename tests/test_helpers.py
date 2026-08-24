"""Tests for small, pure helper functions in generator.py."""

import datetime
import os
import re

import pytest

import generator


class TestBuildTaggedEmail:
    def test_no_tag_when_tag_address_unset(self):
        assert generator.build_tagged_email("jane@example.com", "") == "jane@example.com"

    def test_no_tag_when_tag_address_none(self):
        assert generator.build_tagged_email("jane@example.com", None) == "jane@example.com"

    def test_no_tag_when_tag_address_whitespace_only(self):
        assert generator.build_tagged_email("jane@example.com", "   ") == "jane@example.com"

    def test_inserts_tag_before_at_sign(self):
        assert generator.build_tagged_email("jane@example.com", "resume") == "jane+resume@example.com"

    def test_strips_whitespace_around_tag_address(self):
        assert generator.build_tagged_email("jane@example.com", "  resume  ") == "jane+resume@example.com"

    def test_email_without_at_sign_returned_unchanged(self):
        assert generator.build_tagged_email("not-an-email", "resume") == "not-an-email"

    def test_preserves_subdomain_and_dots_in_local_part(self):
        assert generator.build_tagged_email("jane.doe@mail.example.com", "readme") == "jane.doe+readme@mail.example.com"


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

    def test_empty_full_name_renders_first_and_last_as_empty_string(self):
        assert generator.render_filename("[{FirstName}][{LastName}]", "", "SDE", "json") == "[][]"

    def test_none_full_name_renders_first_and_last_as_empty_string(self):
        assert generator.render_filename("[{FirstName}][{LastName}]", None, "SDE", "json") == "[][]"

    def test_job_acronym_can_nest_output_under_a_subfolder(self):
        result = generator.render_filename(
            "{JobAcronym}/{FirstName} {LastName} Resume.{Extension}", "Jane Doe", "SDE", "pdf",
        )
        assert result == "SDE/Jane Doe Resume.pdf"

    def test_email_placeholder(self):
        result = generator.render_filename("{Email}.{Extension}", "Jane Doe", "SDE", "json", email="jane@example.com")
        assert result == "jane@example.com.json"

    def test_email_defaults_to_empty_string(self):
        result = generator.render_filename("[{Email}]", "Jane Doe", "SDE", "json")
        assert result == "[]"

    def test_bare_datetime_now_is_filesystem_safe(self):
        result = generator.render_filename("data/{datetime.now}/profile.json", "", "", "json")
        # No ':' or ' ' -- safe as a single path segment on every OS.
        assert re.fullmatch(r"data/\d{4}-\d{2}-\d{2}_\d{6}/profile\.json", result)

    def test_datetime_now_year_month_day_are_real_ints(self):
        now = datetime.datetime.now()
        result = generator.render_filename(
            "{datetime.now.year}-{datetime.now.month:02d}-{datetime.now.day:02d}", "", "", "",
        )
        assert result == f"{now.year}-{now.month:02d}-{now.day:02d}"

    def test_datetime_now_bare_and_attribute_access_share_one_instant(self):
        # Both {datetime.now} and {datetime.now.year} in the SAME template
        # must come from the same underlying datetime.now() call, not two
        # separate calls that could straddle a rollover.
        result = generator.render_filename("{datetime.now}_{datetime.now.year}", "", "", "")
        bare, year = result.rsplit("_", 1)
        assert bare.startswith(year)


class TestNowPlaceholder:
    def test_str_value_is_filesystem_safe_format(self):
        dt = datetime.datetime(2026, 3, 5, 9, 7, 2)
        assert str(generator._NowPlaceholder(dt)) == "2026-03-05_090702"

    def test_known_datetime_attributes_pass_through(self):
        dt = datetime.datetime(2026, 3, 5, 9, 7, 2)
        placeholder = generator._NowPlaceholder(dt)
        assert placeholder.year == 2026
        assert placeholder.month == 3
        assert placeholder.day == 5
        assert placeholder.hour == 9

    def test_unrelated_attribute_still_raises_attribute_error(self):
        placeholder = generator._NowPlaceholder(datetime.datetime.now())
        with pytest.raises(AttributeError):
            placeholder.not_a_real_attribute


class TestEnsureParentDirExists:
    def test_creates_missing_parent_directory(self, tmp_path):
        target = tmp_path / "a" / "b" / "c" / "file.txt"
        assert not target.parent.exists()
        result = generator.ensure_parent_dir_exists(target)
        assert result == target
        assert target.parent.is_dir()

    def test_is_a_noop_when_parent_already_exists(self, tmp_path):
        target = tmp_path / "file.txt"
        result = generator.ensure_parent_dir_exists(target)
        assert result == target
        assert target.parent.is_dir()


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
        assert settings["KNOWLEDGE_BASE"] == "data/profile.json"
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

    def test_builds_client_with_v1_suffix(self, monkeypatch):
        monkeypatch.setenv("LITELLM_BASE_URL", "http://example.com")
        monkeypatch.setenv("LITELLM_API_KEY", "secret")
        client = generator.build_llm_client()
        # openai.OpenAI normalizes base_url to always end with "/".
        assert str(client.base_url) == "http://example.com/v1/"
        assert client.api_key == "secret"

    def test_strips_trailing_slash_before_appending_v1(self, monkeypatch):
        monkeypatch.setenv("LITELLM_BASE_URL", "http://example.com/")
        monkeypatch.setenv("LITELLM_API_KEY", "secret")
        client = generator.build_llm_client()
        # Without the strip, this would become ".../v1" -- confirms the
        # trailing slash on LITELLM_BASE_URL doesn't produce "...//v1".
        assert str(client.base_url) == "http://example.com/v1/"