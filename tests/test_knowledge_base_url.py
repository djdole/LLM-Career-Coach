"""Tests for KNOWLEDGE_BASE being an http(s) URL instead of a local path:
fetch_knowledge_base_json, load_knowledge_base, and how main() and
generate_profile_draft() use them."""

import json
from unittest.mock import MagicMock

import httpx
import pytest

import generator


def _mock_json_response(payload, status_code=200):
    response = MagicMock()
    response.status_code = status_code
    response.json.return_value = payload
    response.raise_for_status.return_value = None
    return response


class TestFetchKnowledgeBaseJson:
    def test_returns_parsed_json_on_success(self, monkeypatch):
        payload = {"personal_info": {"full_name": "Jane Doe"}}
        monkeypatch.setattr(generator.httpx, "get", lambda *a, **k: _mock_json_response(payload))
        result = generator.fetch_knowledge_base_json("https://example.com/profile.json")
        assert result == payload

    def test_sends_no_auth_header_when_token_unset(self, monkeypatch):
        captured = {}

        def fake_get(url, **kwargs):
            captured["headers"] = kwargs.get("headers", {})
            return _mock_json_response({})

        monkeypatch.delenv("KNOWLEDGE_BASE_URL_TOKEN", raising=False)
        monkeypatch.setattr(generator.httpx, "get", fake_get)
        generator.fetch_knowledge_base_json("https://example.com/profile.json")
        assert "Authorization" not in captured["headers"]

    def test_sends_token_as_authorization_header_when_set(self, monkeypatch):
        captured = {}

        def fake_get(url, **kwargs):
            captured["headers"] = kwargs.get("headers", {})
            return _mock_json_response({})

        monkeypatch.setenv("KNOWLEDGE_BASE_URL_TOKEN", "ghp_secret123")
        monkeypatch.setattr(generator.httpx, "get", fake_get)
        generator.fetch_knowledge_base_json("https://example.com/profile.json")
        assert captured["headers"]["Authorization"] == "token ghp_secret123"

    def test_raises_on_connection_error(self, monkeypatch):
        def raise_error(*a, **k):
            raise httpx.ConnectError("boom")

        monkeypatch.setattr(generator.httpx, "get", raise_error)
        with pytest.raises(ValueError):
            generator.fetch_knowledge_base_json("https://example.com/unreachable")

    def test_raises_on_http_status_error(self, monkeypatch):
        response = MagicMock()
        response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "404", request=MagicMock(), response=MagicMock(status_code=404)
        )
        monkeypatch.setattr(generator.httpx, "get", lambda *a, **k: response)
        with pytest.raises(ValueError):
            generator.fetch_knowledge_base_json("https://example.com/missing.json")

    def test_raises_on_invalid_json(self, monkeypatch):
        response = MagicMock()
        response.raise_for_status.return_value = None
        response.json.side_effect = ValueError("not json")
        monkeypatch.setattr(generator.httpx, "get", lambda *a, **k: response)
        with pytest.raises(ValueError):
            generator.fetch_knowledge_base_json("https://example.com/not_json.txt")


class TestLoadKnowledgeBase:
    def test_reads_local_file(self, tmp_path):
        kb_file = tmp_path / "profile.json"
        kb_file.write_text(json.dumps({"personal_info": {"full_name": "Jane Doe"}}), encoding="utf-8")
        result = generator.load_knowledge_base(str(kb_file))
        assert result == {"personal_info": {"full_name": "Jane Doe"}}

    def test_fetches_https_url(self, monkeypatch):
        payload = {"personal_info": {"full_name": "Jane Doe"}}
        monkeypatch.setattr(generator.httpx, "get", lambda *a, **k: _mock_json_response(payload))
        result = generator.load_knowledge_base("https://example.com/profile.json")
        assert result == payload

    def test_fetches_plain_http_url_too(self, monkeypatch):
        payload = {"personal_info": {"full_name": "Jane Doe"}}
        monkeypatch.setattr(generator.httpx, "get", lambda *a, **k: _mock_json_response(payload))
        result = generator.load_knowledge_base("http://example.com/profile.json")
        assert result == payload

    def test_raises_file_not_found_for_missing_local_path(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            generator.load_knowledge_base(str(tmp_path / "does_not_exist.json"))

    def test_windows_style_path_is_not_mistaken_for_a_url(self, tmp_path):
        # urlparse gives a single-letter scheme like "c" for "C:\\..." on
        # some inputs; make sure that's not misread as http(s) and routed
        # to a network fetch. (Only matters if the "URL" branch would
        # crash before reaching an unrelated error, so this is really a
        # regression guard rather than a Windows compatibility claim.)
        result_path = tmp_path / "profile.json"
        result_path.write_text(json.dumps({"ok": True}), encoding="utf-8")
        assert generator.load_knowledge_base(str(result_path)) == {"ok": True}


class TestMainWithUrlKnowledgeBase:
    def test_loads_kb_from_url_for_resume_target(self, tmp_path, monkeypatch, sample_kb, sample_resume_dict):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "RESUME.template.md").write_text("dummy resume template", encoding="utf-8")
        (tmp_path / "README.template.md").write_text("dummy readme template", encoding="utf-8")
        monkeypatch.setenv("LITELLM_BASE_URL", "http://example.com")
        monkeypatch.setenv("LITELLM_API_KEY", "secret")
        monkeypatch.setenv("KNOWLEDGE_BASE", "https://example.com/profile.json")
        monkeypatch.delenv("OUTPUT_FOLDER", raising=False)

        monkeypatch.setattr(generator.httpx, "get", lambda *a, **k: _mock_json_response(sample_kb))
        monkeypatch.setattr(
            generator, "call_llm_fill_resume", lambda client, kb, variant, template: sample_resume_dict
        )

        generator.main(["--generate", "resume"])

        out_dir = tmp_path / "generated"
        assert (out_dir / "Jane Doe Resume (SDE).json").exists()

    def test_exits_cleanly_when_url_kb_unreachable(self, tmp_path, monkeypatch, capsys):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "RESUME.template.md").write_text("dummy resume template", encoding="utf-8")
        (tmp_path / "README.template.md").write_text("dummy readme template", encoding="utf-8")
        monkeypatch.setenv("LITELLM_BASE_URL", "http://example.com")
        monkeypatch.setenv("LITELLM_API_KEY", "secret")
        monkeypatch.setenv("KNOWLEDGE_BASE", "https://example.com/profile.json")

        def raise_error(*a, **k):
            raise httpx.ConnectError("boom")

        monkeypatch.setattr(generator.httpx, "get", raise_error)

        with pytest.raises(SystemExit) as exc_info:
            generator.main(["--generate", "resume"])
        assert exc_info.value.code == 1
        assert "[KNOWLEDGE_BASE]" in capsys.readouterr().err


class TestGenerateProfileDraftWithUrlKnowledgeBase:
    @pytest.fixture
    def profile_env(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("LITELLM_BASE_URL", "http://example.com")
        monkeypatch.setenv("LITELLM_API_KEY", "secret")
        monkeypatch.setenv("DATA", "data")
        return tmp_path

    def test_fetches_existing_kb_from_url_and_writes_draft_locally(self, profile_env, monkeypatch, sample_kb):
        data_dir = profile_env / "data"
        data_dir.mkdir()
        source = data_dir / "new_job.txt"
        source.write_text("Started a new role at Beta Corp", encoding="utf-8")

        monkeypatch.setenv("KNOWLEDGE_BASE", "https://example.com/profile.json")
        monkeypatch.setattr(generator.httpx, "get", lambda *a, **k: _mock_json_response(sample_kb))

        updated_kb = dict(sample_kb)
        captured = {}

        def fake_call(client, existing_kb, source_texts):
            captured["existing_kb"] = existing_kb
            return updated_kb

        monkeypatch.setattr(generator, "call_llm_update_profile", fake_call)

        settings = generator.load_file_location_settings()
        generator.generate_profile_draft(client=object(), s=settings)

        assert captured["existing_kb"] == sample_kb  # fetched from the URL, not read from disk
        draft_path = data_dir / "profile.json"
        assert json.loads(draft_path.read_text(encoding="utf-8")) == updated_kb
        assert not source.exists()  # consumed

    def test_prints_manual_promotion_note_when_kb_is_a_url(self, profile_env, monkeypatch, sample_kb, capsys):
        data_dir = profile_env / "data"
        data_dir.mkdir()
        (data_dir / "new_job.txt").write_text("Started a new role", encoding="utf-8")

        monkeypatch.setenv("KNOWLEDGE_BASE", "https://example.com/profile.json")
        monkeypatch.setattr(generator.httpx, "get", lambda *a, **k: _mock_json_response(sample_kb))
        monkeypatch.setattr(generator, "call_llm_update_profile", lambda client, existing_kb, source_texts: sample_kb)

        settings = generator.load_file_location_settings()
        generator.generate_profile_draft(client=object(), s=settings)

        assert "was NOT pushed there" in capsys.readouterr().err

    def test_does_not_exclude_any_local_file_as_the_remote_kb(self, profile_env, monkeypatch, sample_kb):
        # With a URL KNOWLEDGE_BASE there's no local file to exclude by
        # path -- build_source_file_list should just treat every non-draft
        # file in DATA/ as a source, never mistake one for "the KB".
        data_dir = profile_env / "data"
        data_dir.mkdir()
        source = data_dir / "profile.json"  # same name a local KB might have
        source.write_text("Started a new role at Beta Corp", encoding="utf-8")

        monkeypatch.setenv("KNOWLEDGE_BASE", "https://example.com/profile.json")
        monkeypatch.setattr(generator.httpx, "get", lambda *a, **k: _mock_json_response(sample_kb))
        monkeypatch.setenv("KNOWLEDGE_BASE_DRAFT", "data/draft_output.json")

        monkeypatch.setattr(generator, "call_llm_update_profile", lambda client, existing_kb, source_texts: sample_kb)

        settings = generator.load_file_location_settings()
        generator.generate_profile_draft(client=object(), s=settings)

        # The local file (which happens to share a name with a typical
        # local KB) was treated as a real source and consumed.
        assert not source.exists()
        assert (data_dir / "draft_output.json").exists()

    def test_exits_when_url_kb_fetch_fails_and_there_are_source_files(self, profile_env, monkeypatch):
        data_dir = profile_env / "data"
        data_dir.mkdir()
        source = data_dir / "old_resume.txt"
        source.write_text("Jane Doe, Software Engineer at Acme", encoding="utf-8")

        monkeypatch.setenv("KNOWLEDGE_BASE", "https://example.com/profile.json")

        def raise_error(*a, **k):
            raise httpx.ConnectError("boom")

        monkeypatch.setattr(generator.httpx, "get", raise_error)

        settings = generator.load_file_location_settings()
        with pytest.raises(SystemExit) as exc_info:
            generator.generate_profile_draft(client=object(), s=settings)
        assert exc_info.value.code == 1

    def test_noop_when_url_kb_fetch_fails_but_no_source_files(self, profile_env, monkeypatch):
        # Speculative naming-template read failing shouldn't crash a run
        # that has no source files to process anyway.
        monkeypatch.setenv("KNOWLEDGE_BASE", "https://example.com/profile.json")

        def raise_error(*a, **k):
            raise httpx.ConnectError("boom")

        monkeypatch.setattr(generator.httpx, "get", raise_error)

        settings = generator.load_file_location_settings()
        generator.generate_profile_draft(client=object(), s=settings)  # must not raise