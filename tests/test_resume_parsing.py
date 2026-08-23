"""Tests for parse_filled_resume(), which turns a filled-in RESUME_TEMPLATE
back into the structured dict the renderers expect (see
build_resume_fill_prompt / RESUME.template.md for the expected shape)."""

import pytest

import generator

VALID_RESUME_TEXT = (
    "Jane Doe\n"
    "jane@example.com \u00b7 555-1234 \u00b7 linkedin.com/in/jane \u00b7 example.com/jane\n"
    "\n"
    "SUMMARY\n"
    "Great engineer who ships things.\n"
    "\n"
    "CORE TECHNICAL SKILLS\n"
    "Languages: Python, Go\n"
    "Operating Systems: Linux, macOS\n"
    "\n"
    "WORK EXPERIENCE\n"
    "Software Engineer | Acme Corp | 2020-01 - 2023-01\n"
    "Team Widgets, Platform Squad\n"
    "\u25cf Built the widget service.\n"
    "\u25cf Did another thing.\n"
    "\n"
    "Junior Engineer | Beta Inc | 2018-01 - 2020-01\n"
    "\u25cf Maintained the beta system.\n"
    "\n"
    "EDUCATION\n"
    "BS in Computer Science | State University | 2015\n"
)


class TestParseFilledResumeHappyPath:
    def test_parses_name_and_contact_line(self):
        r = generator.parse_filled_resume(VALID_RESUME_TEXT)
        assert r["name"] == "Jane Doe"
        assert r["contact_line"] == "jane@example.com \u00b7 555-1234 \u00b7 linkedin.com/in/jane \u00b7 example.com/jane"

    def test_parses_summary(self):
        r = generator.parse_filled_resume(VALID_RESUME_TEXT)
        assert r["summary"] == "Great engineer who ships things."

    def test_parses_skills_heading_and_categories(self):
        r = generator.parse_filled_resume(VALID_RESUME_TEXT)
        assert r["skills_heading"] == "CORE TECHNICAL SKILLS"
        assert r["skills"] == [
            {"category": "Languages", "items": ["Python", "Go"]},
            {"category": "Operating Systems", "items": ["Linux", "macOS"]},
        ]

    def test_parses_both_jobs(self):
        r = generator.parse_filled_resume(VALID_RESUME_TEXT)
        assert [j["title"] for j in r["work_experience"]] == ["Software Engineer", "Junior Engineer"]
        assert [j["company"] for j in r["work_experience"]] == ["Acme Corp", "Beta Inc"]
        assert r["work_experience"][0]["date_range"] == "2020-01 - 2023-01"

    def test_job_with_team_context_line(self):
        r = generator.parse_filled_resume(VALID_RESUME_TEXT)
        assert r["work_experience"][0]["team_context"] == "Team Widgets, Platform Squad"
        assert r["work_experience"][0]["bullets"] == ["Built the widget service.", "Did another thing."]

    def test_job_without_team_context_line(self):
        r = generator.parse_filled_resume(VALID_RESUME_TEXT)
        assert r["work_experience"][1]["team_context"] == ""
        assert r["work_experience"][1]["bullets"] == ["Maintained the beta system."]

    def test_parses_education(self):
        r = generator.parse_filled_resume(VALID_RESUME_TEXT)
        assert r["education"] == [
            {"degree": "BS in Computer Science", "institution": "State University", "date": "2015"}
        ]

    def test_tolerates_extra_blank_lines_between_sections(self):
        spaced = VALID_RESUME_TEXT.replace("\n\nWORK EXPERIENCE", "\n\n\n\nWORK EXPERIENCE")
        r = generator.parse_filled_resume(spaced)
        assert len(r["work_experience"]) == 2

    def test_single_job_single_education_entry(self):
        text = (
            "Jane Doe\ncontact\n\nSUMMARY\nSummary text.\n\nSKILLS HEADING\nLanguages: Python\n\n"
            "WORK EXPERIENCE\nTitle | Company | Date\n\u25cf Only bullet.\n\n"
            "EDUCATION\nDegree | School | 2020\n"
        )
        r = generator.parse_filled_resume(text)
        assert len(r["work_experience"]) == 1
        assert len(r["education"]) == 1

    def test_multiple_education_entries(self):
        text = (
            "Jane Doe\ncontact\n\nSUMMARY\nSummary text.\n\nSKILLS HEADING\nLanguages: Python\n\n"
            "WORK EXPERIENCE\nTitle | Company | Date\n\u25cf Only bullet.\n\n"
            "EDUCATION\nBS | School A | 2020\nMS | School B | 2022\n"
        )
        r = generator.parse_filled_resume(text)
        assert len(r["education"]) == 2
        assert r["education"][1] == {"degree": "MS", "institution": "School B", "date": "2022"}


class TestParseFilledResumeErrors:
    def test_raises_when_output_too_short(self):
        with pytest.raises(ValueError, match="too short"):
            generator.parse_filled_resume("onlyoneline")

    def test_raises_when_summary_header_missing(self):
        with pytest.raises(ValueError, match="Expected 'SUMMARY' header"):
            generator.parse_filled_resume("Name\nContact\nNOT_SUMMARY")

    def test_raises_when_skills_line_unparsable(self):
        text = "Name\nContact\n\nSUMMARY\nSummary text\n\nSKILLS HEADING\nbadline_no_colon\n"
        with pytest.raises(ValueError, match="Could not parse skills line"):
            generator.parse_filled_resume(text)

    def test_raises_when_work_experience_header_missing(self):
        text = "Name\nContact\n\nSUMMARY\nSummary text\n\nSKILLS HEADING\nLanguages: Python\n\nNOT_WORK\n"
        with pytest.raises(ValueError, match="Expected 'WORK EXPERIENCE' header"):
            generator.parse_filled_resume(text)

    def test_raises_when_job_header_not_pipe_delimited(self):
        text = (
            "Name\nContact\n\nSUMMARY\nSummary text\n\nSKILLS HEADING\nLanguages: Python\n\n"
            "WORK EXPERIENCE\nBadHeaderNoParts\n\nEDUCATION\n"
        )
        with pytest.raises(ValueError, match="not in 'Title \\| Company \\| Dates' shape"):
            generator.parse_filled_resume(text)

    def test_raises_when_job_has_no_bullets(self):
        text = (
            "Name\nContact\n\nSUMMARY\nSummary text\n\nSKILLS HEADING\nLanguages: Python\n\n"
            "WORK EXPERIENCE\nTitle | Co | Date\n\nEDUCATION\n"
        )
        with pytest.raises(ValueError, match="has no bullets"):
            generator.parse_filled_resume(text)

    def test_raises_when_education_header_missing_at_eof(self):
        text = (
            "Name\nContact\n\nSUMMARY\nSummary text\n\nSKILLS HEADING\nLanguages: Python\n\n"
            "WORK EXPERIENCE\nTitle | Co | Date\n\u25cf bullet\n"
        )
        with pytest.raises(ValueError, match="Expected 'EDUCATION' header"):
            generator.parse_filled_resume(text)

    def test_raises_when_skills_heading_missing_at_eof(self):
        text = "Name\nContact\n\nSUMMARY\nSummary text\n"
        with pytest.raises(ValueError, match="Output ended before a skills_heading line"):
            generator.parse_filled_resume(text)

    def test_raises_when_education_line_not_pipe_delimited(self):
        text = (
            "Name\nContact\n\nSUMMARY\nSummary text\n\nSKILLS HEADING\nLanguages: Python\n\n"
            "WORK EXPERIENCE\nTitle | Co | Date\n\u25cf bullet\n\n"
            "EDUCATION\nBadEduLineNoParts\n"
        )
        with pytest.raises(ValueError, match="not in 'Degree \\| Institution \\| Date' shape"):
            generator.parse_filled_resume(text)