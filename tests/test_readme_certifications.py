"""Tests for putting every certification in the generated README's
Education section: build_certification_records, the README context, the
README template comment, ensure_readme_certifications, and the
call_llm_readme integration."""

import copy
from unittest.mock import MagicMock

import pytest

import generator

CERT = {
    "name": "JavaScript and Playwright Automation with AI Program",
    "issuer": "CYDEO",
    "type": "Certificate of Completion",
    "issue_date": "2026-09-01",
    "issue_date_display": "Sep 2026",
}
RECORD = {
    "name": CERT["name"], "issuer": "CYDEO", "type": "Certificate of Completion", "date": "Sep 2026",
    "degree": "JavaScript and Playwright Automation with AI Program (Certificate of Completion)",
}
EDU = "## \U0001f393 Education"


def readme(education_body="**BS in CS**<br>\nState University - Computer Science<br>\nGraduated 2015\n", trailer="---\n\n## \u2728 Career Highlights\nStuff\n"):
    return (
        "# Jane Doe\n\n---\n\n## \U0001f6e0\ufe0f Skills\nStuff\n\n---\n\n"
        "## \U0001f4bc Experience\n### Job\n\n---\n\n"
        f"{EDU}\n\n{education_body}\n{trailer}"
    )


@pytest.fixture
def cert_kb(sample_kb):
    sample_kb["certifications"] = [copy.deepcopy(CERT)]
    return sample_kb


class TestBuildCertificationRecords:
    def test_record_shape(self, cert_kb):
        assert generator.build_certification_records(cert_kb) == [RECORD]

    def test_resume_and_readme_flags_are_independent(self, cert_kb):
        cert_kb["certifications"][0]["include_in_resume_education"] = False
        assert generator.build_certification_records(cert_kb, "include_in_resume_education") == []
        assert generator.build_certification_records(cert_kb, "include_in_readme_education") == [RECORD]
        cert_kb["certifications"][0]["include_in_resume_education"] = True
        cert_kb["certifications"][0]["include_in_readme_education"] = False
        assert generator.build_certification_records(cert_kb, "include_in_readme_education") == []
        assert len(generator.build_certification_records(cert_kb, "include_in_resume_education")) == 1

    def test_resume_entries_still_built_from_records(self, cert_kb):
        assert generator.build_certification_education_entries(cert_kb) == [
            {"degree": RECORD["degree"], "institution": "CYDEO", "date": "Sep 2026"}
        ]

    def test_no_certifications(self, sample_kb):
        assert generator.build_certification_records(sample_kb) == []


class TestReadmeContext:
    def test_certification_follows_degrees_with_kind_and_label(self, cert_kb):
        edu = generator.build_readme_context(cert_kb)["education"]
        assert edu[0]["institution"] == "State University" and "kind" not in edu[0]
        assert edu[-1] == {
            "degree": RECORD["degree"], "institution": "CYDEO", "field_of_study": "",
            "graduation_date": "Sep 2026", "kind": "certification", "date_label": "Issued",
        }

    def test_readme_flag_false_leaves_it_out(self, cert_kb):
        cert_kb["certifications"][0]["include_in_readme_education"] = False
        assert len(generator.build_readme_context(cert_kb)["education"]) == 1

    def test_prompt_contains_the_certification(self, cert_kb):
        prompt = generator.build_readme_system_prompt(cert_kb, "template")
        assert "Certificate of Completion" in prompt and "CYDEO" in prompt

    def test_template_comment_covers_certifications(self, readme_template_text):
        edu = readme_template_text.split("## \U0001f393 Education", 1)[1].split("---", 1)[0]
        assert "certification" in edu.lower() and "Issued" in edu
        assert "**{{DEGREE}}**<br>" in edu  # existing degree format is unchanged


class TestEnsureReadmeCertifications:
    def test_appends_missing_certification_after_last_entry(self):
        out = generator.ensure_readme_certifications(readme(), [RECORD])
        assert (
            "Graduated 2015\n\n"
            f"**{RECORD['degree']}**<br>\nCYDEO<br>\nIssued Sep 2026\n"
        ) in out
        assert out.index("Issued Sep 2026") < out.index("## \u2728 Career Highlights")

    def test_block_sits_inside_education_before_the_rule(self):
        out = generator.ensure_readme_certifications(readme(), [RECORD])
        section = out.split(EDU, 1)[1].split("\n---", 1)[0]
        assert "CYDEO" in section

    def test_already_present_is_left_alone(self):
        md = readme(f"**BS**<br>\nSchool<br>\nGraduated 2015\n\n**{RECORD['degree']}**<br>\nCYDEO<br>\nIssued Sep 2026\n")
        assert generator.ensure_readme_certifications(md, [RECORD]) == md

    def test_name_match_ignores_case_and_spacing(self):
        md = readme("**javascript  and PLAYWRIGHT automation with ai program**<br>\nCYDEO\n")
        assert generator.ensure_readme_certifications(md, [RECORD]) == md

    def test_only_the_missing_one_is_added(self):
        other = {**RECORD, "name": "Other Course", "degree": "Other Course (Certificate)", "issuer": "Acme", "date": "Jan 2020"}
        md = readme(f"**{RECORD['degree']}**<br>\nCYDEO<br>\nIssued Sep 2026\n")
        out = generator.ensure_readme_certifications(md, [RECORD, other])
        assert out.count("JavaScript and Playwright") == 1
        assert "**Other Course (Certificate)**<br>\nAcme<br>\nIssued Jan 2020" in out

    def test_undated_certification_has_no_issued_line(self):
        undated = {**RECORD, "date": ""}
        out = generator.ensure_readme_certifications(readme(), [undated])
        assert "Issued" not in out and "\nCYDEO\n" in out

    def test_no_records_returns_unchanged(self):
        assert generator.ensure_readme_certifications(readme(), []) == readme()

    def test_no_education_section_returns_unchanged(self):
        md = "# Jane\n\n## Other\nstuff\n"
        assert generator.ensure_readme_certifications(md, [RECORD]) == md

    def test_section_ending_at_next_heading_without_rule(self):
        md = readme(trailer="## \u2728 Career Highlights\nStuff\n")
        out = generator.ensure_readme_certifications(md, [RECORD])
        assert out.index("CYDEO") < out.index("## \u2728 Career Highlights")

    def test_section_at_end_of_document(self):
        md = "# J\n\n" + EDU + "\n\n**BS**<br>\nSchool<br>\nGraduated 2015"
        out = generator.ensure_readme_certifications(md, [RECORD])
        assert out.endswith("Issued Sep 2026")

    def test_notes_what_it_added_on_stderr(self, capsys):
        generator.ensure_readme_certifications(readme(), [RECORD])
        assert "Added 1 certification" in capsys.readouterr().err

    def test_no_em_dash_introduced(self):
        assert "\u2014" not in generator.ensure_readme_certifications(readme(), [RECORD])


def _response(text):
    r = MagicMock(); r.choices = [MagicMock()]; r.choices[0].message.content = text
    return r


class TestCallLlmReadmeKeepsCertifications:
    def test_certification_dropped_by_model_is_added(self, cert_kb):
        cert_kb["work_experience"] = [cert_kb["work_experience"][0]]
        client = MagicMock()
        client.chat.completions.create.return_value = _response(readme())
        out = generator.call_llm_readme(client, cert_kb, "template")
        assert client.chat.completions.create.call_count == 1  # no wasted retry
        assert RECORD["degree"] in out

    def test_readme_flag_false_is_not_added(self, cert_kb):
        cert_kb["work_experience"] = [cert_kb["work_experience"][0]]
        cert_kb["certifications"][0]["include_in_readme_education"] = False
        client = MagicMock()
        client.chat.completions.create.return_value = _response(readme())
        assert "CYDEO" not in generator.call_llm_readme(client, cert_kb, "template")

    def test_without_certifications_output_is_unchanged(self, sample_kb):
        sample_kb["work_experience"] = [sample_kb["work_experience"][0]]
        client = MagicMock()
        client.chat.completions.create.return_value = _response(readme())
        assert generator.call_llm_readme(client, sample_kb, "template") == readme().strip()
