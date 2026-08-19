"""Tests for validate_readme(), the structural check run on the LLM's
filled-in README before it's accepted (see call_llm_readme)."""

import pytest

import generator

GOOD_README = (
    "# Jane Doe\n\n"
    "## \U0001f6e0\ufe0f Skills\nStuff\n\n"
    "## \U0001f4bc Experience\n### Job One\n### Job Two\n\n"
    "## \U0001f393 Education\nStuff\n\n"
    "## \u2728 Career Highlights\nStuff\n"
)


class TestValidateReadme:
    def test_valid_readme_does_not_raise(self):
        generator.validate_readme(GOOD_README, expected_job_count=2)

    def test_raises_when_required_section_missing(self):
        with pytest.raises(ValueError, match="missing required section"):
            generator.validate_readme("# Title\nno sections here", expected_job_count=0)

    def test_raises_when_placeholder_token_left_in(self):
        bad = GOOD_README.replace("Jane Doe", "{{FULL_NAME}}")
        with pytest.raises(ValueError, match="placeholder"):
            generator.validate_readme(bad, expected_job_count=2)

    def test_raises_when_em_dash_present(self):
        bad = GOOD_README + "\u2014"
        with pytest.raises(ValueError, match="em dash"):
            generator.validate_readme(bad, expected_job_count=2)

    def test_raises_when_job_count_does_not_match(self):
        with pytest.raises(ValueError, match="job entries"):
            generator.validate_readme(GOOD_README, expected_job_count=3)

    def test_raises_when_job_count_is_zero_but_headers_present(self):
        with pytest.raises(ValueError, match="job entries"):
            generator.validate_readme(GOOD_README, expected_job_count=0)

    def test_accepts_zero_job_headers_when_zero_expected(self):
        no_jobs = GOOD_README.replace("### Job One\n### Job Two\n", "")
        generator.validate_readme(no_jobs, expected_job_count=0)
