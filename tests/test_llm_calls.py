"""Tests for the three functions that drive a chat-completion call and
validate/retry its output: call_llm_fill_resume, call_llm_cover_letter,
and call_llm_readme. The OpenAI-compatible client is mocked throughout --
these tests never make a network call."""

from unittest.mock import MagicMock

import openai
import pytest

import generator

GOOD_RESUME_TEXT = (
    "Jane Doe\ncontact\n\nSUMMARY\nGreat.\n\nCORE TECHNICAL SKILLS\nLanguages: Python\n\n"
    "WORK EXPERIENCE\nSWE | Acme Corp | 2020-01 - 2023-01\n\u25cf Did X.\n\n"
    "EDUCATION\nBS in Computer Science | State University | 2015\n"
)

GOOD_README_TEXT = (
    "# Jane Doe\n\n## \U0001f6e0\ufe0f Skills\nStuff\n\n"
    "## \U0001f4bc Experience\n### Acme Corp\n\n"
    "## \U0001f393 Education\nStuff\n\n## \u2728 Career Highlights\nStuff"
)


def _make_response(content):
    response = MagicMock()
    response.choices = [MagicMock()]
    response.choices[0].message.content = content
    return response


@pytest.fixture
def llm_kb(sample_kb):
    """sample_kb, trimmed to a single job so GOOD_RESUME_TEXT's single job
    block matches the expected job count."""
    sample_kb["work_experience"] = [sample_kb["work_experience"][0]]
    sample_kb["work_experience"][0]["title_by_variant"] = {"SDE": "SWE", "SDET": "SWE"}
    return sample_kb


class TestCallLlmFillResume:
    def test_succeeds_on_first_attempt(self, llm_kb):
        client = MagicMock()
        client.chat.completions.create.return_value = _make_response(GOOD_RESUME_TEXT)
        result = generator.call_llm_fill_resume(client, llm_kb, "SDE", "template text")
        assert result["name"] == "Jane Doe"
        assert client.chat.completions.create.call_count == 1

    def test_retries_once_on_malformed_output_then_succeeds(self, llm_kb):
        client = MagicMock()
        client.chat.completions.create.side_effect = [
            _make_response("not a valid resume"),
            _make_response(GOOD_RESUME_TEXT),
        ]
        result = generator.call_llm_fill_resume(client, llm_kb, "SDE", "template text")
        assert result["name"] == "Jane Doe"
        assert client.chat.completions.create.call_count == 2

    def test_retries_when_job_count_does_not_match(self, llm_kb):
        wrong_count_text = GOOD_RESUME_TEXT.replace(
            "\u25cf Did X.\n\nEDUCATION",
            "\u25cf Did X.\n\nOther Title | Other Co | 2019 - 2020\n\u25cf Did Y.\n\nEDUCATION",
        )
        client = MagicMock()
        client.chat.completions.create.side_effect = [
            _make_response(wrong_count_text),
            _make_response(GOOD_RESUME_TEXT),
        ]
        result = generator.call_llm_fill_resume(client, llm_kb, "SDE", "template text")
        assert len(result["work_experience"]) == 1
        assert client.chat.completions.create.call_count == 2

    def test_exits_after_exhausting_retries(self, llm_kb):
        client = MagicMock()
        client.chat.completions.create.return_value = _make_response("garbage")
        with pytest.raises(SystemExit) as exc_info:
            generator.call_llm_fill_resume(client, llm_kb, "SDE", "template text")
        assert exc_info.value.code == 1
        assert client.chat.completions.create.call_count == 2

    def test_exits_on_connection_error(self, llm_kb):
        client = MagicMock()
        client.chat.completions.create.side_effect = openai.APIConnectionError(
            request=MagicMock(), message="unreachable"
        )
        with pytest.raises(SystemExit) as exc_info:
            generator.call_llm_fill_resume(client, llm_kb, "SDE", "template text")
        assert exc_info.value.code == 1

    def test_exits_on_api_status_error(self, llm_kb):
        client = MagicMock()
        client.chat.completions.create.side_effect = openai.APIStatusError(
            message="server error",
            response=MagicMock(status_code=500),
            body={"error": "server error"},
        )
        with pytest.raises(SystemExit) as exc_info:
            generator.call_llm_fill_resume(client, llm_kb, "SDE", "template text")
        assert exc_info.value.code == 1


class TestCallLlmCoverLetter:
    def test_succeeds_with_json_response_format(self, llm_kb):
        client = MagicMock()
        client.chat.completions.create.return_value = _make_response('{"body": "Dear Hiring Manager, thanks."}')
        result = generator.call_llm_cover_letter(client, llm_kb, "SDE")
        assert result == {"body": "Dear Hiring Manager, thanks."}
        assert client.chat.completions.create.call_count == 1

    def test_falls_back_when_response_format_unsupported(self, llm_kb):
        client = MagicMock()
        client.chat.completions.create.side_effect = [
            openai.BadRequestError(
                message="response_format not supported",
                response=MagicMock(status_code=400),
                body={"error": "response_format not supported"},
            ),
            _make_response('{"body": "fallback body"}'),
        ]
        result = generator.call_llm_cover_letter(client, llm_kb, "SDE")
        assert result == {"body": "fallback body"}
        assert client.chat.completions.create.call_count == 2

    def test_retries_on_unparsable_json_then_succeeds(self, llm_kb):
        client = MagicMock()
        client.chat.completions.create.side_effect = [
            _make_response("not json at all"),
            _make_response('{"body": "ok"}'),
        ]
        result = generator.call_llm_cover_letter(client, llm_kb, "SDE")
        assert result == {"body": "ok"}

    def test_retries_when_required_key_missing(self, llm_kb):
        client = MagicMock()
        client.chat.completions.create.side_effect = [
            _make_response('{"wrong_key": "x"}'),
            _make_response('{"body": "ok"}'),
        ]
        result = generator.call_llm_cover_letter(client, llm_kb, "SDE")
        assert result == {"body": "ok"}

    def test_exits_after_exhausting_retries(self, llm_kb):
        client = MagicMock()
        client.chat.completions.create.return_value = _make_response('{"wrong_key": "x"}')
        with pytest.raises(SystemExit) as exc_info:
            generator.call_llm_cover_letter(client, llm_kb, "SDE")
        assert exc_info.value.code == 1

    def test_exits_on_api_status_error(self, llm_kb):
        client = MagicMock()
        client.chat.completions.create.side_effect = openai.APIStatusError(
            message="server error",
            response=MagicMock(status_code=500),
            body={"error": "server error"},
        )
        with pytest.raises(SystemExit) as exc_info:
            generator.call_llm_cover_letter(client, llm_kb, "SDE")
        assert exc_info.value.code == 1


class TestCallLlmReadme:
    def test_succeeds_on_first_attempt(self, llm_kb):
        client = MagicMock()
        client.chat.completions.create.return_value = _make_response(GOOD_README_TEXT)
        result = generator.call_llm_readme(client, llm_kb, "template text")
        assert result == GOOD_README_TEXT

    def test_retries_on_malformed_output_then_succeeds(self, llm_kb):
        client = MagicMock()
        client.chat.completions.create.side_effect = [
            _make_response("not a valid readme"),
            _make_response(GOOD_README_TEXT),
        ]
        result = generator.call_llm_readme(client, llm_kb, "template text")
        assert result == GOOD_README_TEXT
        assert client.chat.completions.create.call_count == 2

    def test_exits_after_exhausting_retries(self, llm_kb):
        client = MagicMock()
        client.chat.completions.create.return_value = _make_response("still not valid")
        with pytest.raises(SystemExit) as exc_info:
            generator.call_llm_readme(client, llm_kb, "template text")
        assert exc_info.value.code == 1

    def test_exits_on_connection_error(self, llm_kb):
        client = MagicMock()
        client.chat.completions.create.side_effect = openai.APIConnectionError(
            request=MagicMock(), message="unreachable"
        )
        with pytest.raises(SystemExit) as exc_info:
            generator.call_llm_readme(client, llm_kb, "template text")
        assert exc_info.value.code == 1
