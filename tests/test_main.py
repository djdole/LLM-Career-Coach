"""Integration tests for main(): the LLM calls (call_llm_fill_resume,
call_llm_cover_letter, call_llm_readme) and build_llm_client are stubbed
out, so these tests exercise everything main() does around them --
reading the knowledge base and templates, creating the output directory,
naming files, and calling every renderer -- without making a network
call."""

import json
from pathlib import Path

import pytest

import generator


@pytest.fixture
def main_env(tmp_path, monkeypatch, sample_kb):
    """Sets up a scratch working directory with resume_data.json and the
    two template files main() reads, chdir'd into it, with LITELLM_* env
    vars set so build_llm_client() doesn't exit."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "resume_data.json").write_text(json.dumps(sample_kb), encoding="utf-8")
    (tmp_path / "RESUME.template.md").write_text("dummy resume template", encoding="utf-8")
    (tmp_path / "README.template.md").write_text("dummy readme template", encoding="utf-8")
    monkeypatch.setenv("LITELLM_BASE_URL", "http://example.com")
    monkeypatch.setenv("LITELLM_API_KEY", "secret")
    monkeypatch.delenv("OUTPUT_FOLDER", raising=False)
    return tmp_path


@pytest.fixture
def stub_llm_calls(monkeypatch, sample_resume_dict, sample_cover_letter_dict):
    """Replaces the three LLM-calling functions main() uses with stubs
    that return fixed, already-valid data, so main()'s own file-writing
    logic is what's under test here."""
    readme_markdown = "# Jane Doe\n\nfull profile here"
    monkeypatch.setattr(generator, "call_llm_fill_resume", lambda client, kb, variant, template: sample_resume_dict)
    monkeypatch.setattr(generator, "call_llm_cover_letter", lambda client, kb, variant: sample_cover_letter_dict)
    monkeypatch.setattr(generator, "call_llm_readme", lambda client, kb, template: readme_markdown)
    return readme_markdown


class TestMain:
    def test_creates_output_directory(self, main_env, stub_llm_calls):
        generator.main()
        assert (main_env / "generated").is_dir()

    def test_writes_all_five_resume_formats_per_variant(self, main_env, stub_llm_calls):
        generator.main()
        out_dir = main_env / "generated"
        for variant in generator.VARIANTS:
            for ext in ("json", "txt", "md", "pdf", "docx"):
                assert (out_dir / f"Jane Doe Resume ({variant}).{ext}").exists()

    def test_writes_all_three_cover_letter_formats_per_variant(self, main_env, stub_llm_calls):
        generator.main()
        out_dir = main_env / "generated"
        for variant in generator.VARIANTS:
            for ext in ("txt", "docx", "pdf"):
                assert (out_dir / f"Jane Doe Cover Letter ({variant}).{ext}").exists()

    def test_resume_json_matches_stubbed_data(self, main_env, stub_llm_calls, sample_resume_dict):
        generator.main()
        out_path = main_env / "generated" / "Jane Doe Resume (SDE).json"
        assert json.loads(out_path.read_text(encoding="utf-8")) == sample_resume_dict

    def test_writes_readme_from_call_llm_readme(self, main_env, stub_llm_calls):
        generator.main()
        assert (main_env / "README.md").read_text(encoding="utf-8") == stub_llm_calls

    def test_drops_middle_name_from_filenames(self, main_env, stub_llm_calls):
        # sample_kb's personal_info.full_name is "Jane Q. Doe" (see conftest);
        # render_filename should use only the first and last tokens.
        generator.main()
        out_dir = main_env / "generated"
        assert (out_dir / "Jane Doe Resume (SDE).json").exists()
        assert not any("Q." in p.name for p in out_dir.iterdir())

    def test_respects_output_folder_override(self, main_env, monkeypatch, stub_llm_calls):
        monkeypatch.setenv("OUTPUT_FOLDER", "custom_output")
        generator.main()
        assert (main_env / "custom_output" / "Jane Doe Resume (SDE).json").exists()
        assert not (main_env / "generated").exists()
