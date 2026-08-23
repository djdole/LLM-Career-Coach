"""Tests for the --analyze job-fit-analysis feature: context trimming,
--analyze value resolution (text/file/URL), prompt/validation, the LLM
call (mocked, no network), and markdown rendering."""

import json
from unittest.mock import MagicMock

import httpx
import openai
import pytest

import generator


def _make_response(content):
    response = MagicMock()
    response.choices = [MagicMock()]
    response.choices[0].message.content = content
    return response


class TestBuildJobFitContext:
    def test_includes_skills_from_list_categories_only(self, sample_kb):
        context = generator.build_job_fit_context(sample_kb)
        categories = {s["category"] for s in context["skills"]}
        assert "Languages" in categories
        # skill_selection_guidance and skill_selection_guidance-like
        # non-list values must never show up as a "category".
        assert "Skill Selection Guidance" not in categories

    def test_work_experience_includes_both_variants_titles(self, sample_kb):
        context = generator.build_job_fit_context(sample_kb)
        job = context["work_experience"][0]
        assert job["titles"] == {"SDE": "Software Engineer", "SDET": "SDET"}

    def test_drops_alt_bullets(self, sample_kb):
        context = generator.build_job_fit_context(sample_kb)
        job = context["work_experience"][0]
        assert "Alternate phrasing, should be dropped." not in job["bullets"]
        assert "Built the widget service." in job["bullets"]

    def test_includes_both_summary_variants(self, sample_kb):
        context = generator.build_job_fit_context(sample_kb)
        assert context["summaries"] == {"SDE": "SDE summary.", "SDET": "SDET summary."}


class TestResolveJobDescription:
    def test_treats_non_path_string_as_literal_text(self):
        result = generator.resolve_job_description("We need a Python developer.")
        assert result == "We need a Python developer."

    def test_reads_existing_file(self, tmp_path):
        jd_file = tmp_path / "jd.txt"
        jd_file.write_text("Looking for a Rust engineer.", encoding="utf-8")
        result = generator.resolve_job_description(str(jd_file))
        assert result == "Looking for a Rust engineer."

    def test_raises_on_empty_literal_text(self):
        with pytest.raises(ValueError):
            generator.resolve_job_description("   ")

    def test_raises_on_file_with_no_extractable_text(self, tmp_path):
        jd_file = tmp_path / "empty.txt"
        jd_file.write_text("", encoding="utf-8")
        with pytest.raises(ValueError):
            generator.resolve_job_description(str(jd_file))

    def _mock_response(self, text, content_type):
        response = MagicMock()
        response.text = text
        response.headers = {"content-type": content_type}
        response.raise_for_status.return_value = None
        return response

    def test_fetches_plain_text_from_url(self, monkeypatch):
        response = self._mock_response("Need a Go developer.", "text/plain")
        monkeypatch.setattr(generator.httpx, "get", lambda *a, **k: response)
        result = generator.resolve_job_description("https://example.com/jobs/123")
        assert result == "Need a Go developer."

    def test_strips_html_from_url_response(self, monkeypatch):
        html_body = "<html><head><style>.x{color:red}</style></head><body><script>evil()</script><h1>Backend Engineer</h1><p>Must know Go &amp; Kubernetes.</p></body></html>"
        response = self._mock_response(html_body, "text/html; charset=utf-8")
        monkeypatch.setattr(generator.httpx, "get", lambda *a, **k: response)
        result = generator.resolve_job_description("https://example.com/jobs/123")
        assert "Backend Engineer" in result
        assert "Must know Go & Kubernetes." in result
        assert "evil()" not in result
        assert "<h1>" not in result

    def test_raises_on_url_connection_error(self, monkeypatch):
        def raise_error(*a, **k):
            raise httpx.ConnectError("boom")

        monkeypatch.setattr(generator.httpx, "get", raise_error)
        with pytest.raises(ValueError):
            generator.resolve_job_description("https://example.com/unreachable")

    def test_raises_on_url_http_status_error(self, monkeypatch):
        response = MagicMock()
        response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "404", request=MagicMock(), response=MagicMock(status_code=404)
        )
        monkeypatch.setattr(generator.httpx, "get", lambda *a, **k: response)
        with pytest.raises(ValueError):
            generator.resolve_job_description("https://example.com/missing")

    def test_raises_when_url_returns_no_extractable_text(self, monkeypatch):
        response = self._mock_response("   ", "text/plain")
        monkeypatch.setattr(generator.httpx, "get", lambda *a, **k: response)
        with pytest.raises(ValueError, match="no extractable text"):
            generator.resolve_job_description("https://example.com/blank")


class TestValidateJobFitAnalysis:
    def test_accepts_well_formed_analysis(self, sample_job_fit_analysis_dict):
        generator.validate_job_fit_analysis(sample_job_fit_analysis_dict)  # should not raise

    def test_raises_when_top_level_not_a_dict(self):
        with pytest.raises(ValueError, match="Expected a JSON object"):
            generator.validate_job_fit_analysis(["not", "a", "dict"])

    def test_accepts_well_formed_multi_assessment_analysis(self, sample_job_fit_analysis_multi_dict):
        generator.validate_job_fit_analysis(sample_job_fit_analysis_multi_dict)  # should not raise

    def test_accepts_empty_missing_and_resources(self):
        generator.validate_job_fit_analysis({
            "fit_assessments": [
                {
                    "list_label": "Overall Qualifications",
                    "fit_percentage": 100,
                    "assessment_summary": "Perfect match.",
                    "missing_qualifications": [],
                }
            ],
            "overall_summary": "Perfect match.",
            "upskill_resources": [],
        })

    def test_matched_qualifications_is_optional(self):
        generator.validate_job_fit_analysis({
            "fit_assessments": [
                {
                    "list_label": "Overall Qualifications",
                    "fit_percentage": 50,
                    "assessment_summary": "Partial match.",
                    "missing_qualifications": ["Rust"],
                }
            ],
            "overall_summary": "Partial match.",
            "upskill_resources": [{"missing_item": "Rust", "resource_name": "The Rust Book"}],
        })

    @pytest.mark.parametrize("missing_key", sorted(generator.REQUIRED_ANALYSIS_KEYS))
    def test_raises_on_missing_top_level_key(self, sample_job_fit_analysis_dict, missing_key):
        del sample_job_fit_analysis_dict[missing_key]
        with pytest.raises(ValueError):
            generator.validate_job_fit_analysis(sample_job_fit_analysis_dict)

    def test_raises_on_empty_fit_assessments(self, sample_job_fit_analysis_dict):
        sample_job_fit_analysis_dict["fit_assessments"] = []
        with pytest.raises(ValueError):
            generator.validate_job_fit_analysis(sample_job_fit_analysis_dict)

    def test_raises_when_fit_assessments_not_a_list(self, sample_job_fit_analysis_dict):
        sample_job_fit_analysis_dict["fit_assessments"] = "not a list"
        with pytest.raises(ValueError):
            generator.validate_job_fit_analysis(sample_job_fit_analysis_dict)

    def test_raises_when_assessment_entry_not_a_dict(self, sample_job_fit_analysis_dict):
        sample_job_fit_analysis_dict["fit_assessments"] = ["not a dict"]
        with pytest.raises(ValueError, match="must be an object"):
            generator.validate_job_fit_analysis(sample_job_fit_analysis_dict)

    @pytest.mark.parametrize("missing_key", sorted(generator.REQUIRED_ASSESSMENT_KEYS))
    def test_raises_on_missing_assessment_key(self, sample_job_fit_analysis_dict, missing_key):
        del sample_job_fit_analysis_dict["fit_assessments"][0][missing_key]
        with pytest.raises(ValueError):
            generator.validate_job_fit_analysis(sample_job_fit_analysis_dict)

    @pytest.mark.parametrize("bad_pct", [-1, 101, "72", True])
    def test_raises_on_invalid_fit_percentage(self, sample_job_fit_analysis_dict, bad_pct):
        sample_job_fit_analysis_dict["fit_assessments"][0]["fit_percentage"] = bad_pct
        with pytest.raises(ValueError):
            generator.validate_job_fit_analysis(sample_job_fit_analysis_dict)

    def test_raises_on_one_bad_assessment_among_several(self, sample_job_fit_analysis_multi_dict):
        sample_job_fit_analysis_multi_dict["fit_assessments"][1]["fit_percentage"] = 150
        with pytest.raises(ValueError):
            generator.validate_job_fit_analysis(sample_job_fit_analysis_multi_dict)

    def test_raises_on_empty_list_label(self, sample_job_fit_analysis_dict):
        sample_job_fit_analysis_dict["fit_assessments"][0]["list_label"] = "   "
        with pytest.raises(ValueError):
            generator.validate_job_fit_analysis(sample_job_fit_analysis_dict)

    def test_raises_on_empty_assessment_summary(self, sample_job_fit_analysis_dict):
        sample_job_fit_analysis_dict["fit_assessments"][0]["assessment_summary"] = "   "
        with pytest.raises(ValueError):
            generator.validate_job_fit_analysis(sample_job_fit_analysis_dict)

    def test_raises_on_empty_overall_summary(self, sample_job_fit_analysis_dict):
        sample_job_fit_analysis_dict["overall_summary"] = "   "
        with pytest.raises(ValueError):
            generator.validate_job_fit_analysis(sample_job_fit_analysis_dict)

    def test_raises_when_missing_qualifications_not_a_list_of_strings(self, sample_job_fit_analysis_dict):
        sample_job_fit_analysis_dict["fit_assessments"][0]["missing_qualifications"] = [{"not": "a string"}]
        with pytest.raises(ValueError):
            generator.validate_job_fit_analysis(sample_job_fit_analysis_dict)

    def test_raises_when_matched_qualifications_not_a_list_of_strings(self, sample_job_fit_analysis_dict):
        sample_job_fit_analysis_dict["fit_assessments"][0]["matched_qualifications"] = [{"not": "a string"}]
        with pytest.raises(ValueError):
            generator.validate_job_fit_analysis(sample_job_fit_analysis_dict)

    def test_raises_when_upskill_resources_not_a_list(self, sample_job_fit_analysis_dict):
        sample_job_fit_analysis_dict["upskill_resources"] = "not a list"
        with pytest.raises(ValueError):
            generator.validate_job_fit_analysis(sample_job_fit_analysis_dict)

    def test_raises_when_resource_entry_not_a_dict(self, sample_job_fit_analysis_dict):
        sample_job_fit_analysis_dict["upskill_resources"] = ["not a dict"]
        with pytest.raises(ValueError, match="must be an object"):
            generator.validate_job_fit_analysis(sample_job_fit_analysis_dict)

    def test_raises_when_resource_missing_required_key(self, sample_job_fit_analysis_dict):
        sample_job_fit_analysis_dict["upskill_resources"] = [{"missing_item": "Kubernetes"}]
        with pytest.raises(ValueError):
            generator.validate_job_fit_analysis(sample_job_fit_analysis_dict)

    def test_resource_url_and_is_free_are_optional(self, sample_job_fit_analysis_dict):
        sample_job_fit_analysis_dict["upskill_resources"] = [
            {"missing_item": "Kubernetes", "resource_name": "Kubernetes Basics"}
        ]
        generator.validate_job_fit_analysis(sample_job_fit_analysis_dict)  # should not raise


class TestBuildJobFitPrompt:
    def test_substitutes_job_description(self, sample_kb, analysis_prompt_template_text):
        prompt = generator.build_job_fit_prompt(sample_kb, "Unique JD marker text.", analysis_prompt_template_text)
        assert "Unique JD marker text." in prompt

    def test_substitutes_candidate_data_and_output_rules(self, sample_kb, analysis_prompt_template_text):
        prompt = generator.build_job_fit_prompt(sample_kb, "Need a Go dev.", analysis_prompt_template_text)
        # Candidate data (from build_job_fit_context) should be embedded as JSON.
        assert "Software Engineer" in prompt
        # never_fabricate output rules should be embedded too.
        assert "never_fabricate" in prompt

    def test_leaves_literal_braces_in_json_schema_example_untouched(self, sample_kb, analysis_prompt_template_text):
        # string.Template substitution must not choke on, or mangle, the
        # template's literal JSON-schema example braces.
        prompt = generator.build_job_fit_prompt(sample_kb, "Need a Go dev.", analysis_prompt_template_text)
        assert '"fit_percentage"' in prompt
        assert '"upskill_resources"' in prompt

    def test_custom_template_text_is_honored(self, sample_kb):
        custom_template = "CUSTOM PROMPT. Rules: $output_rules JD: $job_description Data: $candidate_data"
        prompt = generator.build_job_fit_prompt(sample_kb, "Need a Go dev.", custom_template)
        assert prompt.startswith("CUSTOM PROMPT.")
        assert "Need a Go dev." in prompt


class TestCallLlmAnalyzeFit:
    def test_succeeds_on_first_attempt(self, sample_kb, sample_job_fit_analysis_dict, analysis_prompt_template_text):
        client = MagicMock()
        client.chat.completions.create.return_value = _make_response(json.dumps(sample_job_fit_analysis_dict))
        result = generator.call_llm_analyze_fit(
            client, sample_kb, "Need a Python dev.", analysis_prompt_template_text
        )
        assert result == sample_job_fit_analysis_dict
        assert client.chat.completions.create.call_count == 1

    def test_retries_on_unparsable_json_then_succeeds(
        self, sample_kb, sample_job_fit_analysis_dict, analysis_prompt_template_text
    ):
        client = MagicMock()
        client.chat.completions.create.side_effect = [
            _make_response("not json at all"),
            _make_response(json.dumps(sample_job_fit_analysis_dict)),
        ]
        result = generator.call_llm_analyze_fit(
            client, sample_kb, "Need a Python dev.", analysis_prompt_template_text
        )
        assert result == sample_job_fit_analysis_dict
        assert client.chat.completions.create.call_count == 2

    def test_retries_when_required_key_missing(
        self, sample_kb, sample_job_fit_analysis_dict, analysis_prompt_template_text
    ):
        bad = {"fit_percentage": 50}
        client = MagicMock()
        client.chat.completions.create.side_effect = [
            _make_response(json.dumps(bad)),
            _make_response(json.dumps(sample_job_fit_analysis_dict)),
        ]
        result = generator.call_llm_analyze_fit(
            client, sample_kb, "Need a Python dev.", analysis_prompt_template_text
        )
        assert result == sample_job_fit_analysis_dict

    def test_exits_after_exhausting_retries(self, sample_kb, analysis_prompt_template_text):
        client = MagicMock()
        client.chat.completions.create.return_value = _make_response('{"wrong_key": "x"}')
        with pytest.raises(SystemExit) as exc_info:
            generator.call_llm_analyze_fit(client, sample_kb, "Need a Python dev.", analysis_prompt_template_text)
        assert exc_info.value.code == 1

    def test_falls_back_when_response_format_unsupported(
        self, sample_kb, sample_job_fit_analysis_dict, analysis_prompt_template_text
    ):
        client = MagicMock()
        client.chat.completions.create.side_effect = [
            openai.BadRequestError(
                message="response_format not supported",
                response=MagicMock(status_code=400),
                body={"error": "response_format not supported"},
            ),
            _make_response(json.dumps(sample_job_fit_analysis_dict)),
        ]
        result = generator.call_llm_analyze_fit(
            client, sample_kb, "Need a Python dev.", analysis_prompt_template_text
        )
        assert result == sample_job_fit_analysis_dict
        assert client.chat.completions.create.call_count == 2

    def test_exits_on_connection_error(self, sample_kb, analysis_prompt_template_text):
        client = MagicMock()
        client.chat.completions.create.side_effect = openai.APIConnectionError(
            request=MagicMock(), message="unreachable"
        )
        with pytest.raises(SystemExit) as exc_info:
            generator.call_llm_analyze_fit(client, sample_kb, "Need a Python dev.", analysis_prompt_template_text)
        assert exc_info.value.code == 1

    def test_exits_on_api_status_error(self, sample_kb, analysis_prompt_template_text):
        client = MagicMock()
        client.chat.completions.create.side_effect = openai.APIStatusError(
            message="server error",
            response=MagicMock(status_code=500),
            body={"error": "server error"},
        )
        with pytest.raises(SystemExit) as exc_info:
            generator.call_llm_analyze_fit(client, sample_kb, "Need a Python dev.", analysis_prompt_template_text)
        assert exc_info.value.code == 1


class TestRenderJobFitAnalysisMd:
    def test_includes_fit_percentage_and_summary(self, sample_job_fit_analysis_dict):
        md = generator.render_job_fit_analysis_md(sample_job_fit_analysis_dict)
        assert "72%" in md
        assert sample_job_fit_analysis_dict["overall_summary"] in md

    def test_includes_missing_qualifications_and_resources(self, sample_job_fit_analysis_dict):
        md = generator.render_job_fit_analysis_md(sample_job_fit_analysis_dict)
        assert "Kubernetes" in md
        assert "Kubernetes Basics" in md
        assert "https://kubernetes.io/docs/tutorials/kubernetes-basics/" in md

    def test_handles_no_missing_qualifications(self):
        analysis = {
            "fit_assessments": [
                {
                    "list_label": "Overall Qualifications",
                    "fit_percentage": 100,
                    "assessment_summary": "Perfect match.",
                    "missing_qualifications": [],
                }
            ],
            "overall_summary": "Perfect match.",
            "upskill_resources": [],
        }
        md = generator.render_job_fit_analysis_md(analysis)
        assert "None found" in md

    def test_single_assessment_renders_flat_without_a_breakdown_section(self, sample_job_fit_analysis_dict):
        md = generator.render_job_fit_analysis_md(sample_job_fit_analysis_dict)
        assert "## Fit Scores" not in md
        assert "## Matched Qualifications" in md
        assert "## Missing Qualifications" in md
        # The summary shouldn't be duplicated under a redundant per-list section.
        assert md.count(sample_job_fit_analysis_dict["overall_summary"]) == 1

    def test_multi_assessment_shows_a_score_per_list(self, sample_job_fit_analysis_multi_dict):
        md = generator.render_job_fit_analysis_md(sample_job_fit_analysis_multi_dict)
        assert "## Fit Scores" in md
        assert "Required Qualifications" in md
        assert "Preferred Qualifications" in md
        assert "90%" in md
        assert "40%" in md

    def test_multi_assessment_includes_each_lists_own_matched_and_missing(self, sample_job_fit_analysis_multi_dict):
        md = generator.render_job_fit_analysis_md(sample_job_fit_analysis_multi_dict)
        assert "PostgreSQL" in md
        assert "Terraform" in md
        assert "REST APIs" in md

    def test_multi_assessment_includes_overall_summary(self, sample_job_fit_analysis_multi_dict):
        md = generator.render_job_fit_analysis_md(sample_job_fit_analysis_multi_dict)
        assert sample_job_fit_analysis_multi_dict["overall_summary"] in md