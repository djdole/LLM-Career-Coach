"""Tests for the --generate resume_data workflow: build_source_file_list,
extract_text_from_source_file, validate_resume_data_draft, and the
generate_resume_data_draft orchestrator (with the LLM call itself
stubbed)."""

import json
from pathlib import Path

import pytest

import generator


class TestBuildSourceFileList:
    def test_missing_data_dir_returns_empty(self, tmp_path):
        result = generator.build_source_file_list(
            tmp_path / "nope", tmp_path / "kb.json", tmp_path / "kb.draft.json"
        )
        assert result == []

    def test_empty_data_dir_returns_empty(self, tmp_path):
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        assert generator.build_source_file_list(data_dir, tmp_path / "kb.json", tmp_path / "kb.draft.json") == []

    def test_excludes_knowledge_base_file(self, tmp_path):
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        kb_path = data_dir / "resume_data.json"
        kb_path.write_text("{}", encoding="utf-8")
        assert generator.build_source_file_list(data_dir, kb_path, data_dir / "resume_data.json") == []

    def test_excludes_existing_draft_file(self, tmp_path):
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        draft_path = data_dir / "resume_data.json"
        draft_path.write_text("{}", encoding="utf-8")
        assert generator.build_source_file_list(data_dir, data_dir / "resume_data.json", draft_path) == []

    def test_includes_other_files_only(self, tmp_path):
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        kb_path = data_dir / "resume_data.json"
        kb_path.write_text("{}", encoding="utf-8")
        draft_path = data_dir / "resume_data.json"
        new_resume = data_dir / "old_resume.txt"
        new_resume.write_text("some text", encoding="utf-8")
        hidden = data_dir / ".hidden"
        hidden.write_text("nope", encoding="utf-8")
        result = generator.build_source_file_list(data_dir, kb_path, draft_path)
        assert result == [new_resume]


class TestExtractTextFromSourceFile:
    def test_reads_txt(self, tmp_path):
        p = tmp_path / "notes.txt"
        p.write_text("hello world", encoding="utf-8")
        assert generator.extract_text_from_source_file(p) == "hello world"

    def test_reads_json(self, tmp_path):
        p = tmp_path / "data.json"
        p.write_text('{"a": 1}', encoding="utf-8")
        assert generator.extract_text_from_source_file(p) == '{"a": 1}'

    def test_reads_xml(self, tmp_path):
        p = tmp_path / "data.xml"
        p.write_text("<root><a>1</a></root>", encoding="utf-8")
        assert "root" in generator.extract_text_from_source_file(p)

    def test_unsupported_extension_returns_empty(self, tmp_path):
        p = tmp_path / "data.exe"
        p.write_bytes(b"\x00\x01")
        assert generator.extract_text_from_source_file(p) == ""


class TestValidateResumeDataDraft:
    def test_accepts_valid_new_draft(self):
        draft = {"personal_info": {}, "education": [], "skills": {}, "work_experience": []}
        generator.validate_resume_data_draft(draft, None)  # no exception

    def test_rejects_missing_required_section(self):
        draft = {"personal_info": {}, "education": [], "skills": {}}
        with pytest.raises(ValueError, match="missing required section"):
            generator.validate_resume_data_draft(draft, None)

    def test_rejects_non_dict(self):
        with pytest.raises(ValueError):
            generator.validate_resume_data_draft(["not", "a", "dict"], None)

    def test_rejects_dropped_top_level_section_on_update(self, sample_kb):
        draft = {"personal_info": {}, "education": [], "skills": {}, "work_experience": []}
        with pytest.raises(ValueError, match="non-destructive"):
            generator.validate_resume_data_draft(draft, sample_kb)

    def test_accepts_update_that_keeps_all_sections(self, sample_kb):
        draft = dict(sample_kb)
        draft["skills"] = {**draft["skills"], "new_category": ["Something"]}
        generator.validate_resume_data_draft(draft, sample_kb)  # no exception


@pytest.fixture
def resume_data_env(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("LITELLM_BASE_URL", "http://example.com")
    monkeypatch.setenv("LITELLM_API_KEY", "secret")
    return tmp_path


class TestGenerateResumeDataDraft:
    def test_noop_when_data_env_unset(self, resume_data_env, monkeypatch):
        monkeypatch.delenv("DATA", raising=False)
        settings = generator.load_file_location_settings()
        generator.generate_resume_data_draft(client=None, s=settings)
        assert not (resume_data_env / "data").exists()

    def test_noop_when_data_folder_missing(self, resume_data_env, monkeypatch):
        monkeypatch.setenv("DATA", "data")
        settings = generator.load_file_location_settings()
        generator.generate_resume_data_draft(client=None, s=settings)
        assert not (resume_data_env / "data" / "resume_data.json").exists()

    def test_noop_when_data_folder_empty(self, resume_data_env, monkeypatch):
        monkeypatch.setenv("DATA", "data")
        (resume_data_env / "data").mkdir()
        settings = generator.load_file_location_settings()
        generator.generate_resume_data_draft(client=None, s=settings)
        assert not (resume_data_env / "data" / "resume_data.json").exists()

    def test_noop_when_only_knowledge_base_present(self, resume_data_env, monkeypatch, sample_kb):
        monkeypatch.setenv("DATA", "data")
        data_dir = resume_data_env / "data"
        data_dir.mkdir()
        (data_dir / "resume_data.json").write_text(json.dumps(sample_kb), encoding="utf-8")
        settings = generator.load_file_location_settings()
        generator.generate_resume_data_draft(client=None, s=settings)
        assert (data_dir / "resume_data.json").exists()

    def test_builds_new_draft_when_knowledge_base_missing(self, resume_data_env, monkeypatch):
        monkeypatch.setenv("DATA", "data")
        data_dir = resume_data_env / "data"
        data_dir.mkdir()
        source = data_dir / "old_resume.txt"
        source.write_text("Jane Doe, Software Engineer at Acme", encoding="utf-8")
        settings = generator.load_file_location_settings()

        new_kb = {"personal_info": {"full_name": "Jane Doe"}, "education": [], "skills": {}, "work_experience": []}
        monkeypatch.setattr(
            generator, "call_llm_update_resume_data",
            lambda client, existing_kb, source_texts: new_kb if existing_kb is None else (_ for _ in ()).throw(AssertionError("expected no existing kb")),
        )

        generator.generate_resume_data_draft(client=object(), s=settings)

        draft_path = data_dir / "resume_data.json"
        assert json.loads(draft_path.read_text(encoding="utf-8")) == new_kb
        assert not source.exists()  # consumed source file removed

    def test_updates_draft_non_destructively_when_knowledge_base_exists(self, resume_data_env, monkeypatch, sample_kb):
        monkeypatch.setenv("DATA", "data")
        data_dir = resume_data_env / "data"
        data_dir.mkdir()
        (data_dir / "resume_data.json").write_text(json.dumps(sample_kb), encoding="utf-8")
        source = data_dir / "new_job.txt"
        source.write_text("Started a new role at Beta Corp", encoding="utf-8")
        settings = generator.load_file_location_settings()

        updated_kb = dict(sample_kb)
        captured = {}

        def fake_call(client, existing_kb, source_texts):
            captured["existing_kb"] = existing_kb
            captured["source_texts"] = source_texts
            return updated_kb

        monkeypatch.setattr(generator, "call_llm_update_resume_data", fake_call)

        generator.generate_resume_data_draft(client=object(), s=settings)

        assert captured["existing_kb"] == sample_kb
        assert "new_job.txt" in captured["source_texts"]
        draft_path = data_dir / "resume_data.json"
        assert json.loads(draft_path.read_text(encoding="utf-8")) == updated_kb
        assert not source.exists()  # consumed
        assert (data_dir / "resume_data.json").exists()  # knowledge base itself untouched

    def test_leaves_existing_draft_alone_when_no_new_sources(self, resume_data_env, monkeypatch, sample_kb):
        monkeypatch.setenv("DATA", "data")
        data_dir = resume_data_env / "data"
        data_dir.mkdir()
        (data_dir / "resume_data.json").write_text(json.dumps(sample_kb), encoding="utf-8")
        stale_draft = data_dir / "resume_data.json"
        stale_draft.write_text('{"stale": true}', encoding="utf-8")
        settings = generator.load_file_location_settings()

        generator.generate_resume_data_draft(client=None, s=settings)

        # No new source files besides the stale draft/kb -> untouched.
        assert json.loads(stale_draft.read_text(encoding="utf-8")) == {"stale": True}
