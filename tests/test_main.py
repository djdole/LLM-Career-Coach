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
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "resume_data.json").write_text(json.dumps(sample_kb), encoding="utf-8")
    (tmp_path / "RESUME.template.md").write_text("dummy resume template", encoding="utf-8")
    (tmp_path / "README.template.md").write_text("dummy readme template", encoding="utf-8")
    monkeypatch.setenv("LITELLM_BASE_URL", "http://example.com")
    monkeypatch.setenv("LITELLM_API_KEY", "secret")
    monkeypatch.delenv("OUTPUT_FOLDER", raising=False)
    monkeypatch.delenv("DATA", raising=False)
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


class TestMainGenerateFlag:
    def test_no_flag_generates_everything(self, main_env, stub_llm_calls):
        generator.main([])
        out_dir = main_env / "generated"
        assert (out_dir / "Jane Doe Resume (SDE).json").exists()
        assert (out_dir / "Jane Doe Cover Letter (SDE).txt").exists()
        assert (main_env / "README.md").exists()

    def test_bare_flag_generates_nothing(self, main_env, stub_llm_calls):
        generator.main(["--generate"])
        assert not (main_env / "generated").exists()
        assert not (main_env / "README.md").exists()

    def test_single_value_generates_only_that_target(self, main_env, stub_llm_calls):
        generator.main(["--generate", "resume"])
        out_dir = main_env / "generated"
        assert (out_dir / "Jane Doe Resume (SDE).json").exists()
        assert not (out_dir / "Jane Doe Cover Letter (SDE).txt").exists()
        assert not (main_env / "README.md").exists()

    def test_comma_separated_values(self, main_env, stub_llm_calls):
        generator.main(["--generate", "resume,coverletter"])
        out_dir = main_env / "generated"
        assert (out_dir / "Jane Doe Resume (SDE).json").exists()
        assert (out_dir / "Jane Doe Cover Letter (SDE).txt").exists()
        assert not (main_env / "README.md").exists()

    def test_cover_letter_underscore_spelling_accepted(self, main_env, stub_llm_calls):
        generator.main(["--generate", "cover_letter"])
        out_dir = main_env / "generated"
        assert (out_dir / "Jane Doe Cover Letter (SDE).txt").exists()
        assert not (out_dir / "Jane Doe Resume (SDE).json").exists()

    def test_repeated_flag_unions_targets(self, main_env, stub_llm_calls):
        generator.main(["--generate", "resume", "--generate", "coverletter", "--generate", "readme"])
        out_dir = main_env / "generated"
        assert (out_dir / "Jane Doe Resume (SDE).json").exists()
        assert (out_dir / "Jane Doe Cover Letter (SDE).txt").exists()
        assert (main_env / "README.md").exists()

    def test_readme_only_does_not_create_output_dir(self, main_env, stub_llm_calls):
        generator.main(["--generate", "readme"])
        assert (main_env / "README.md").exists()
        assert not (main_env / "generated").exists()

    def test_unknown_value_exits(self, main_env, stub_llm_calls):
        with pytest.raises(SystemExit):
            generator.main(["--generate", "bogus"])

    def test_resume_data_not_included_in_default_run(self, main_env, monkeypatch, stub_llm_calls):
        called = []
        monkeypatch.setattr(generator, "generate_resume_data_draft", lambda client, s: called.append(True))
        generator.main([])
        assert called == []

    def test_resume_data_flag_invokes_workflow_without_requiring_knowledge_base(self, main_env, monkeypatch, stub_llm_calls):
        # Knowledge base file that main_env's fixture wrote is removed here
        # to prove --generate resume_data alone doesn't require it to
        # exist (unlike resume/cover_letter/readme).
        (main_env / "data" / "resume_data.json").unlink()
        called = []
        monkeypatch.setattr(generator, "generate_resume_data_draft", lambda client, s: called.append(s))
        generator.main(["--generate", "resume_data"])
        assert len(called) == 1
        assert called[0]["KNOWLEDGE_BASE"] == "data/resume_data.json"
