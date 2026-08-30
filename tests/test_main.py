"""Integration tests for main(): the LLM calls (call_llm_fill_resume,
call_llm_cover_letter, call_llm_readme) and build_llm_client are stubbed
out, so these tests exercise everything main() does around them --
reading the knowledge base and templates, creating the output directory,
naming files, and calling every renderer - without making a network
call."""

import json
import runpy
import subprocess
import sys
from pathlib import Path

import pytest

import generator


@pytest.fixture
def main_env(tmp_path, monkeypatch, sample_kb):
    """Sets up a scratch working directory with profile.json and the
    template files main() reads, chdir'd into it, with LITELLM_* env
    vars set so build_llm_client() doesn't exit."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "profile.json").write_text(json.dumps(sample_kb), encoding="utf-8")
    (tmp_path / "RESUME.template.md").write_text("dummy resume template", encoding="utf-8")
    (tmp_path / "README.template.md").write_text("dummy readme template", encoding="utf-8")
    (tmp_path / "ANALYSIS_PROMPT.template.txt").write_text(
        "Rules: $output_rules\nData: $candidate_data\nJD: $job_description", encoding="utf-8"
    )
    monkeypatch.setenv("LITELLM_BASE_URL", "http://example.com")
    monkeypatch.setenv("LITELLM_API_KEY", "secret")
    monkeypatch.delenv("OUTPUT_FOLDER", raising=False)
    monkeypatch.delenv("DATA", raising=False)
    monkeypatch.delenv("VARIANTS", raising=False)
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


@pytest.fixture
def stub_analyze_call(monkeypatch, sample_job_fit_analysis_dict):
    """Replaces call_llm_analyze_fit with a stub returning fixed,
    already-valid data, so main()'s --analyze file-writing logic is what's
    under test here."""
    monkeypatch.setattr(
        generator,
        "call_llm_analyze_fit",
        lambda client, kb, job_description, prompt_template_text: sample_job_fit_analysis_dict,
    )
    return sample_job_fit_analysis_dict


class TestMain:
    def test_creates_output_directory(self, main_env, stub_llm_calls):
        generator.main()
        assert (main_env / "generated").is_dir()

    def test_writes_all_five_resume_formats_per_variant(self, main_env, stub_llm_calls):
        generator.main()
        out_dir = main_env / "generated"
        for variant in generator.load_file_location_settings()["VARIANTS"]:
            for ext in ("json", "txt", "md", "pdf", "docx"):
                assert (out_dir / f"Jane Doe Resume ({variant}).{ext}").exists()

    def test_writes_all_three_cover_letter_formats_per_variant(self, main_env, stub_llm_calls):
        generator.main()
        out_dir = main_env / "generated"
        for variant in generator.load_file_location_settings()["VARIANTS"]:
            for ext in ("txt", "docx", "pdf"):
                assert (out_dir / f"Jane Doe Cover Letter ({variant}).{ext}").exists()

    def test_resume_json_matches_stubbed_data(self, main_env, stub_llm_calls, sample_resume_dict):
        generator.main()
        out_path = main_env / "generated" / "Jane Doe Resume (SDE).json"
        assert json.loads(out_path.read_text(encoding="utf-8")) == sample_resume_dict

    def test_writes_readme_from_call_llm_readme(self, main_env, stub_llm_calls):
        generator.main()
        assert (main_env / "README.md").read_text(encoding="utf-8") == stub_llm_calls

    def test_respects_variants_override(self, main_env, monkeypatch, stub_llm_calls):
        monkeypatch.setenv("VARIANTS", "SDE")
        generator.main()
        out_dir = main_env / "generated"
        assert (out_dir / "Jane Doe Resume (SDE).json").exists()
        assert not (out_dir / "Jane Doe Resume (SDET).json").exists()

    def test_variants_override_can_add_a_new_variant(self, main_env, monkeypatch, stub_llm_calls):
        monkeypatch.setenv("VARIANTS", "SDE,SDET,SRE")
        generator.main()
        out_dir = main_env / "generated"
        for variant in ("SDE", "SDET", "SRE"):
            assert (out_dir / f"Jane Doe Resume ({variant}).json").exists()

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

    def test_warns_when_resume_still_exceeds_two_pages_at_smallest_tier(
        self, main_env, stub_llm_calls, monkeypatch, capsys
    ):
        # render_resume_pdf returns (pages, body_pt); main() should warn,
        # rather than silently accept it, when even the smallest font
        # tier couldn't fit the resume in 2 pages.
        monkeypatch.setattr(generator, "render_resume_pdf", lambda r, path, max_pages=2: (3, 8))
        generator.main(["--generate", "resume"])
        out = capsys.readouterr().out
        assert "WARNING" in out
        assert "3 pages" in out
        assert "8pt" in out


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

    def test_profile_not_included_in_default_run(self, main_env, monkeypatch, stub_llm_calls):
        called = []
        monkeypatch.setattr(generator, "generate_profile_draft", lambda client, s: called.append(True))
        generator.main([])
        assert called == []

    def test_profile_flag_invokes_workflow_without_requiring_knowledge_base(self, main_env, monkeypatch, stub_llm_calls):
        # Knowledge base file that main_env's fixture wrote is removed here
        # to prove --generate profile alone doesn't require it to
        # exist (unlike resume/cover_letter/readme).
        (main_env / "data" / "profile.json").unlink()
        called = []
        monkeypatch.setattr(generator, "generate_profile_draft", lambda client, s: called.append(s))
        generator.main(["--generate", "profile"])
        assert len(called) == 1
        assert called[0]["KNOWLEDGE_BASE"] == "data/profile.json"


class TestMainEntryPoint:
    """Runs generator.py as a real subprocess -- a genuine end-to-end
    smoke test of the CLI, but NOT what gives `if __name__ ==
    "__main__":` line coverage: a child process's coverage.py tracing
    isn't visible to the pytest-cov instance running in this process.
    See test_running_as_main_invokes_main for that."""

    def test_help_flag_exits_zero_via_subprocess(self):
        result = subprocess.run(
            [sys.executable, str(Path(generator.__file__)), "--help"],
            capture_output=True, text=True, timeout=30,
        )
        assert result.returncode == 0
        assert "--generate" in result.stdout
        assert "--analyze" in result.stdout

    def test_running_as_main_invokes_main(self, monkeypatch, capsys):
        # runpy executes generator.py's module-level code (including the
        # `if __name__ == "__main__":` guard) for real, IN this process
        # and under this test's coverage tracer -- unlike the subprocess
        # test above. --help gives a clean, expected SystemExit(0) to
        # assert on rather than needing to fake anything.
        monkeypatch.setattr(sys, "argv", ["generator.py", "--help"])
        with pytest.raises(SystemExit) as exc_info:
            runpy.run_path(generator.__file__, run_name="__main__")
        assert exc_info.value.code == 0
        assert "--analyze" in capsys.readouterr().out


class TestMainAnalyzeFlag:
    def test_not_run_when_flag_absent(self, main_env, stub_llm_calls, monkeypatch):
        called = []
        monkeypatch.setattr(generator, "call_llm_analyze_fit", lambda client, kb, jd, template: called.append(jd))
        generator.main([])
        assert called == []

    def test_bare_analyze_does_not_also_run_default_generate_targets(self, main_env, stub_analyze_call, capsys):
        # --analyze alone (no --generate) should do ONLY the analysis, not
        # also silently fall back to --generate's "omitted means generate
        # everything" default.
        generator.main(["--analyze", "Need a Python developer."])
        out_dir = main_env / "generated"
        assert not (out_dir / "Jane Doe Resume (SDE).json").exists()
        assert not (out_dir / "Jane Doe Cover Letter (SDE).txt").exists()
        assert "Fit score: 72%" in capsys.readouterr().out

    def test_bare_flag_with_no_value_errors(self, main_env):
        # --analyze's value IS the job description, so it's a required
        # argument to the flag itself: argparse errors with exit code 2
        # if it's omitted.
        with pytest.raises(SystemExit) as exc_info:
            generator.main(["--analyze"])
        assert exc_info.value.code == 2

    def test_exits_when_analyze_value_resolves_to_nothing(self, main_env, capsys):
        # An all-whitespace --analyze value makes resolve_job_description
        # raise ValueError; main() must catch it, print a [analyze]-
        # prefixed message to stderr, and exit(1) -- not crash.
        with pytest.raises(SystemExit) as exc_info:
            generator.main(["--analyze", "   "])
        assert exc_info.value.code == 1
        assert "[analyze]" in capsys.readouterr().err

    def test_generate_analyze_is_not_a_valid_generate_value(self, main_env, stub_llm_calls):
        # analyze is triggered by its own --analyze flag now, not as a
        # --generate target - "--generate analyze" should be rejected
        # the same as any other unknown --generate value.
        with pytest.raises(SystemExit):
            generator.main(["--generate", "analyze"])

    def test_prints_analysis_report_to_stdout(self, main_env, stub_analyze_call, capsys):
        generator.main(["--analyze", "Need a Python developer."])
        out = capsys.readouterr().out
        assert "# Job Fit Analysis" in out
        assert "Fit score: 72%" in out
        assert stub_analyze_call["overall_summary"] in out

    def test_does_not_write_any_analysis_report_file(self, main_env, stub_analyze_call):
        # --analyze's report is stdout-only; it must not write anything
        # to OUTPUT_FOLDER (or anywhere else).
        generator.main(["--analyze", "Need a Python developer."])
        assert not (main_env / "generated").exists()

    def test_analyze_value_can_be_a_file_path(self, main_env, stub_analyze_call, monkeypatch):
        jd_file = main_env / "jd.txt"
        jd_file.write_text("Need a Rust developer.", encoding="utf-8")
        captured = {}

        def fake_analyze(client, kb, job_description, prompt_template_text):
            captured["jd"] = job_description
            return stub_analyze_call

        monkeypatch.setattr(generator, "call_llm_analyze_fit", fake_analyze)
        generator.main(["--analyze", str(jd_file)])
        assert captured["jd"] == "Need a Rust developer."

    def test_does_not_generate_resume_or_cover_letter(self, main_env, stub_analyze_call):
        generator.main(["--analyze", "Need a Python developer."])
        out_dir = main_env / "generated"
        assert not (out_dir / "Jane Doe Resume (SDE).json").exists()
        assert not (out_dir / "Jane Doe Cover Letter (SDE).txt").exists()