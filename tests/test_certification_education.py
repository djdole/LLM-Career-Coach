"""Tests for putting every certification in the resume's Education
section: build_certification_education_entries / build_education_entries,
format_certification_date, reconcile_resume_education, the
call_llm_fill_resume enforcement, and the renderers' handling of
certification entries."""

import copy
from unittest.mock import MagicMock

import pytest
from docx import Document
from pypdf import PdfReader

import generator

CYDEO = {
    "name": "JavaScript and Playwright Automation with AI Program",
    "issuer": "CYDEO",
    "type": "Certificate of Completion",
    "issue_date": "2026-09-01",
    "issue_date_display": "Sep 2026",
}
CYDEO_ENTRY = {
    "degree": "JavaScript and Playwright Automation with AI Program (Certificate of Completion)",
    "institution": "CYDEO",
    "date": "Sep 2026",
}


@pytest.fixture
def cert_kb(sample_kb):
    sample_kb["certifications"] = [copy.deepcopy(CYDEO)]
    return sample_kb


class TestFormatCertificationDate:
    def test_prefers_display_value(self):
        assert generator.format_certification_date({"issue_date": "2026-09-01", "issue_date_display": "Fall 2026"}) == "Fall 2026"

    @pytest.mark.parametrize("raw,expected", [
        ("2026-09-01", "Sep 2026"), ("2024-01", "Jan 2024"), ("2023-12-31", "Dec 2023"),
        ("2022", "2022"), ("2022-13", "2022"), ("", ""), (None, ""), ("soon", ""),
    ])
    def test_formats_issue_date(self, raw, expected):
        assert generator.format_certification_date({"issue_date": raw}) == expected

    def test_missing_fields(self):
        assert generator.format_certification_date({}) == ""


class TestBuildCertificationEducationEntries:
    def test_entry_shape_with_type(self, cert_kb):
        assert generator.build_certification_education_entries(cert_kb) == [CYDEO_ENTRY]

    def test_no_certifications_key_or_empty(self, sample_kb):
        assert generator.build_certification_education_entries(sample_kb) == []
        sample_kb["certifications"] = []
        assert generator.build_certification_education_entries(sample_kb) == []

    def test_without_type_has_no_parentheses(self, cert_kb):
        del cert_kb["certifications"][0]["type"]
        entry = generator.build_certification_education_entries(cert_kb)[0]
        assert entry["degree"] == "JavaScript and Playwright Automation with AI Program"

    def test_newest_first_and_undated_last(self, cert_kb):
        cert_kb["certifications"] = [
            {"name": "Old", "issuer": "A", "issue_date": "2019-05"},
            {"name": "Undated", "issuer": "C"},
            {"name": "New", "issuer": "B", "issue_date": "2025-01"},
        ]
        names = [e["degree"] for e in generator.build_certification_education_entries(cert_kb)]
        assert names == ["New", "Old", "Undated"]

    def test_include_false_is_skipped(self, cert_kb):
        cert_kb["certifications"][0]["include_in_resume_education"] = False
        assert generator.build_certification_education_entries(cert_kb) == []

    def test_include_true_and_default_are_kept(self, cert_kb):
        cert_kb["certifications"][0]["include_in_resume_education"] = True
        assert len(generator.build_certification_education_entries(cert_kb)) == 1

    @pytest.mark.parametrize("cert", [{"issuer": "X"}, {"name": "X"}, {"name": " ", "issuer": "X"}, "not a dict", None])
    def test_incomplete_entries_are_skipped(self, cert_kb, cert):
        cert_kb["certifications"] = [cert]
        assert generator.build_certification_education_entries(cert_kb) == []

    def test_pipe_characters_are_replaced(self, cert_kb):
        cert_kb["certifications"] = [{"name": "A | B", "issuer": "C | D", "issue_date": "2020"}]
        entry = generator.build_certification_education_entries(cert_kb)[0]
        assert "|" not in entry["degree"] and "|" not in entry["institution"]


class TestBuildEducationEntries:
    def test_degrees_then_certifications(self, cert_kb):
        entries = generator.build_education_entries(cert_kb)
        assert entries[0]["institution"] == "State University"
        assert entries[0]["date"] == "2015"
        assert entries[-1] == CYDEO_ENTRY

    def test_without_certifications_matches_old_behavior(self, sample_kb):
        assert generator.build_education_entries(sample_kb) == [
            {"degree": "Bachelor of Science in Computer Science", "institution": "State University", "date": "2015"}
        ]

    @pytest.mark.parametrize("variant", ["SDE", "SDET", "GENERIC"])
    def test_baseline_context_includes_certifications_for_every_variant(self, cert_kb, variant):
        cert_kb["summary_variants"]["GENERIC"] = "g"
        assert CYDEO_ENTRY in generator.build_baseline_context(cert_kb, variant)["education"]


class TestReconcileResumeEducation:
    EXPECTED = [
        {"degree": "BS", "institution": "School", "date": "2015"},
        dict(CYDEO_ENTRY),
    ]

    def test_matching_entries_returned_untouched(self):
        parsed = [dict(e) for e in self.EXPECTED]
        assert generator.reconcile_resume_education(parsed, self.EXPECTED) is parsed

    def test_case_and_spacing_differences_are_ignored(self):
        parsed = [{"degree": " bs ", "institution": "SCHOOL", "date": "2015"}, dict(CYDEO_ENTRY)]
        assert generator.reconcile_resume_education(parsed, self.EXPECTED) is parsed

    def test_dropped_certification_is_restored(self, capsys):
        parsed = [dict(self.EXPECTED[0])]
        result = generator.reconcile_resume_education(parsed, self.EXPECTED, "SDE")
        assert result == self.EXPECTED
        assert "[SDE]" in capsys.readouterr().err

    def test_reworded_entry_is_replaced(self):
        parsed = [dict(self.EXPECTED[0]), {**CYDEO_ENTRY, "degree": "Playwright cert"}]
        assert generator.reconcile_resume_education(parsed, self.EXPECTED) == self.EXPECTED

    def test_extra_entry_is_removed(self):
        parsed = [dict(e) for e in self.EXPECTED] + [{"degree": "Invented", "institution": "X", "date": "2000"}]
        assert generator.reconcile_resume_education(parsed, self.EXPECTED) == self.EXPECTED

    def test_result_is_a_copy_of_expected(self):
        result = generator.reconcile_resume_education([], self.EXPECTED)
        result[0]["degree"] = "changed"
        assert self.EXPECTED[0]["degree"] == "BS"


def _response(text):
    r = MagicMock()
    r.choices = [MagicMock()]
    r.choices[0].message.content = text
    return r


RESUME_WITHOUT_CERT = (
    "Jane Doe\ncontact\n\nSUMMARY\nGreat.\n\nCORE TECHNICAL SKILLS\nLanguages: Python\n\n"
    "WORK EXPERIENCE\nSWE | Acme Corp | 2020-01 - 2023-01\n\u25cf Did X.\n\n"
    "EDUCATION\nBachelor of Science in Computer Science | State University | 2015\n"
)


class TestCallLlmFillResumeKeepsCertifications:
    def test_certification_dropped_by_model_is_restored(self, cert_kb):
        cert_kb["work_experience"] = [cert_kb["work_experience"][0]]
        cert_kb["work_experience"][0]["title_by_variant"] = {"SDE": "SWE"}
        client = MagicMock()
        client.chat.completions.create.return_value = _response(RESUME_WITHOUT_CERT)
        result = generator.call_llm_fill_resume(client, cert_kb, "SDE", "template")
        assert client.chat.completions.create.call_count == 1  # no wasted retry
        assert result["education"][-1] == CYDEO_ENTRY
        assert len(result["education"]) == 2

    def test_prompt_data_includes_the_certification(self, cert_kb):
        prompt = generator.build_resume_fill_prompt(cert_kb, "SDE", "template")
        assert "JavaScript and Playwright Automation with AI Program (Certificate of Completion)" in prompt
        assert "CYDEO" in prompt


class TestRenderersWithCertifications:
    @pytest.fixture
    def resume(self, sample_resume_dict):
        r = copy.deepcopy(sample_resume_dict)
        r["education"] = r["education"] + [dict(CYDEO_ENTRY)]
        return r

    def test_txt(self, resume):
        out = generator.render_resume_txt(resume)
        assert CYDEO_ENTRY["degree"] in out and "CYDEO (Sep 2026)" in out

    def test_md(self, resume):
        out = generator.render_resume_md(resume)
        assert f"- {CYDEO_ENTRY['degree']}, CYDEO (Sep 2026)" in out

    def test_docx(self, resume, tmp_path):
        path = tmp_path / "r.docx"
        generator.render_resume_docx(resume, path, body_pt=10.5)
        texts = [p.text for p in Document(str(path)).paragraphs]
        assert f"{CYDEO_ENTRY['degree']}, CYDEO (Sep 2026)" in texts

    def test_pdf(self, resume, tmp_path):
        path = tmp_path / "r.pdf"
        generator.render_resume_pdf(resume, path)
        text = " ".join(" ".join((pg.extract_text() or "").split()) for pg in PdfReader(str(path)).pages)
        assert "Certificate of Completion), CYDEO (Sep 2026)" in text

    def test_entry_without_date_has_no_empty_parentheses(self, resume):
        resume["education"][-1]["date"] = ""
        assert "()" not in generator.render_resume_txt(resume)
        assert "()" not in generator.render_resume_md(resume)
        assert generator._education_line(resume["education"][-1]).endswith("CYDEO")

    def test_degree_entries_render_as_before(self, sample_resume_dict):
        ed = sample_resume_dict["education"][0]
        assert generator._education_line(ed) == f"{ed['degree']}, {ed['institution']} ({ed['date']})"


class TestResumeTemplate:
    def test_template_mentions_certifications_in_education_instruction(self, resume_template_text):
        edu = resume_template_text.split("EDUCATION", 1)[1]
        assert "certification" in edu.lower()
        assert "{{DEGREE}} | {{INSTITUTION}} | {{GRADUATION_DATE}}" in edu
