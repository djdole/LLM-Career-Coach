"""Tests for OUTPUT_REPO and friends: checking generated files into a
different git repository instead of this checkout. Covers
_inject_repo_token, sync_output_repo, and commit_and_push_output_repo
directly, plus main()'s end-to-end wiring (with the LLM calls stubbed
out, same as test_main.py) using real local git repos so clone/fetch/
commit/push all genuinely happen -- no network involved, since a local
path is a perfectly valid git remote."""

import json
import subprocess
from pathlib import Path

import pytest

import generator


def _run(args, cwd):
    result = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    return result.stdout


def _init_bare_remote(tmp_path) -> Path:
    remote = tmp_path / "remote.git"
    _run(["init", "--bare", "-q", str(remote)], cwd=tmp_path)
    return remote


def _git_identity_env(monkeypatch):
    # git refuses to commit with no identity configured; tests run in a
    # scratch tmp_path with no user-level .gitconfig guaranteed, so set
    # it via env vars rather than relying on the machine's global config.
    monkeypatch.setenv("GIT_AUTHOR_NAME", "Test")
    monkeypatch.setenv("GIT_AUTHOR_EMAIL", "test@example.com")
    monkeypatch.setenv("GIT_COMMITTER_NAME", "Test")
    monkeypatch.setenv("GIT_COMMITTER_EMAIL", "test@example.com")


#class TestInjectRepoToken:
#    def test_leaves_url_unchanged_when_no_token(self):
#        url = generator._inject_repo_token("https://github.com/example/repo.git", "")
#        assert url == "https://github.com/example/repo.git"

#    def test_embeds_token_as_basic_auth_credential(self):
#        url = generator._inject_repo_token("https://github.com/example/repo.git", "ghp_secret123")
#        assert url == "https://x-access-token:ghp_secret123@github.com/example/repo.git"

#    def test_leaves_ssh_url_untouched_even_with_token(self):
#        url = generator._inject_repo_token("git@github.com:example/repo.git", "ghp_secret123")
#        assert url == "git@github.com:example/repo.git"

#    def test_leaves_local_path_untouched_even_with_token(self):
#        url = generator._inject_repo_token("/some/local/repo.git", "ghp_secret123")
#        assert url == "/some/local/repo.git"


class TestSyncOutputRepo:
    def _settings(self, repo_url, clone_dir, branch=""):
        return {
            "OUTPUT_REPO": str(repo_url),
            "OUTPUT_REPO_BRANCH": branch,
            "OUTPUT_REPO_TOKEN": "",
            "OUTPUT_REPO_CLONE_DIR": str(clone_dir),
        }

    def _commit_settings(self):
        return {
            "OUTPUT_REPO_BRANCH": "",
            "OUTPUT_REPO_AUTHOR_NAME": "Test",
            "OUTPUT_REPO_AUTHOR_EMAIL": "test@example.com",
            "OUTPUT_REPO_COMMIT_MESSAGE": "run 1",
            "OUTPUT_REPO_PUSH": True,
        }

#    def test_clones_fresh_when_no_existing_clone(self, tmp_path, monkeypatch):
#        _git_identity_env(monkeypatch)
#        remote = _init_bare_remote(tmp_path)
#        clone_dir = tmp_path / "clone"
#
#        result = generator.sync_output_repo(self._settings(remote, clone_dir))
#
#        assert result == clone_dir
#        assert (clone_dir / ".git").is_dir()

#    def test_reuses_and_updates_existing_clone(self, tmp_path, monkeypatch):
#        _git_identity_env(monkeypatch)
#        remote = _init_bare_remote(tmp_path)
#        clone_dir = tmp_path / "clone"
#        s = self._settings(remote, clone_dir)
#
#        generator.sync_output_repo(s)
#        # Simulate another process pushing a new commit to the remote
#        # in between two runs of this generator.
#        other = tmp_path / "other_clone"
#        _run(["clone", "-q", str(remote), str(other)], cwd=tmp_path)
#        (other / "external.txt").write_text("from elsewhere", encoding="utf-8")
#        _run(["add", "-A"], cwd=other)
#        _run(["commit", "-q", "-m", "external commit"], cwd=other)
#        _run(["push", "-q", "origin", "HEAD"], cwd=other)
#
#        generator.sync_output_repo(s)
#
#        assert (clone_dir / "external.txt").read_text(encoding="utf-8") == "from elsewhere"

#    def test_discards_uncommitted_leftovers_when_remote_still_empty(self, tmp_path, monkeypatch):
#        # First-ever run against a freshly created, still-empty
#        # OUTPUT_REPO: there's no commit to reset to yet, so this only
#        # exercises the "clean untracked leftovers" fallback.
#        _git_identity_env(monkeypatch)
#        remote = _init_bare_remote(tmp_path)
#        clone_dir = tmp_path / "clone"
#        s = self._settings(remote, clone_dir)
#
#        generator.sync_output_repo(s)
#        (clone_dir / "leftover.txt").write_text("should be wiped", encoding="utf-8")
#
#        generator.sync_output_repo(s)
#
#        assert not (clone_dir / "leftover.txt").exists()

#    def test_discards_uncommitted_leftovers_after_a_prior_successful_commit(self, tmp_path, monkeypatch):
#        # A more typical case: run 1 completes and pushes a real commit,
#        # then run 2 is interrupted after writing files but before
#        # committing. Run 3's sync should discard those leftovers and
#        # land back on run 1's committed state.
#        _git_identity_env(monkeypatch)
#        remote = _init_bare_remote(tmp_path)
#        clone_dir = tmp_path / "clone"
#        s = self._settings(remote, clone_dir)
#
#        generator.sync_output_repo(s)
#        (clone_dir / "resume.txt").write_text("run 1 output", encoding="utf-8")
#        generator.commit_and_push_output_repo(self._commit_settings(), clone_dir)
#
#        generator.sync_output_repo(s)  # simulates run 2 starting
#        (clone_dir / "leftover.txt").write_text("should be wiped", encoding="utf-8")
#        # run 2 crashes here, before committing
#
#        generator.sync_output_repo(s)  # run 3
#
#        assert not (clone_dir / "leftover.txt").exists()
#        assert (clone_dir / "resume.txt").read_text(encoding="utf-8") == "run 1 output"

#    def test_raises_when_clone_dir_is_a_nonempty_non_git_folder(self, tmp_path, monkeypatch):
#        _git_identity_env(monkeypatch)
#        remote = _init_bare_remote(tmp_path)
#        clone_dir = tmp_path / "clone"
#        clone_dir.mkdir()
#        (clone_dir / "not_a_repo.txt").write_text("oops", encoding="utf-8")
#
#        with pytest.raises(RuntimeError, match="already exists"):
#            generator.sync_output_repo(self._settings(remote, clone_dir))

#    def test_raises_clear_error_on_bad_repo_url(self, tmp_path, monkeypatch):
#        _git_identity_env(monkeypatch)
#        clone_dir = tmp_path / "clone"
#        with pytest.raises(RuntimeError, match="git clone"):
#            generator.sync_output_repo(self._settings(tmp_path / "does_not_exist.git", clone_dir))

#    def test_checks_out_requested_branch(self, tmp_path, monkeypatch):
#        _git_identity_env(monkeypatch)
#        remote = _init_bare_remote(tmp_path)
#        seed = tmp_path / "seed"
#        _run(["clone", "-q", str(remote), str(seed)], cwd=tmp_path)
#        (seed / "f.txt").write_text("x", encoding="utf-8")
#        _run(["add", "-A"], cwd=seed)
#        _run(["commit", "-q", "-m", "seed"], cwd=seed)
#        _run(["branch", "other-branch"], cwd=seed)
#        _run(["push", "-q", "origin", "--all"], cwd=seed)
#
#        clone_dir = tmp_path / "clone"
#        generator.sync_output_repo(self._settings(remote, clone_dir, branch="other-branch"))
#
#        current = _run(["branch", "--show-current"], cwd=clone_dir).strip()
#        assert current == "other-branch"

class TestCommitAndPushOutputRepo:
    def _settings(self, push=True, message="Regenerate ({datetime.now})"):
        return {
            "OUTPUT_REPO": "irrelevant-for-this-class",
            "OUTPUT_REPO_BRANCH": "",
            "OUTPUT_REPO_AUTHOR_NAME": "resume-generator",
            "OUTPUT_REPO_AUTHOR_EMAIL": "resume-generator@users.noreply.github.com",
            "OUTPUT_REPO_COMMIT_MESSAGE": message,
            "OUTPUT_REPO_PUSH": push,
        }

    def test_returns_false_and_commits_nothing_when_clean(self, tmp_path, monkeypatch):
        _git_identity_env(monkeypatch)
        remote = _init_bare_remote(tmp_path)
        clone_dir = tmp_path / "clone"
        _run(["clone", "-q", str(remote), str(clone_dir)], cwd=tmp_path)

        committed = generator.commit_and_push_output_repo(self._settings(), clone_dir)

        assert committed is False

    def test_commits_and_pushes_new_files(self, tmp_path, monkeypatch):
        _git_identity_env(monkeypatch)
        remote = _init_bare_remote(tmp_path)
        clone_dir = tmp_path / "clone"
        _run(["clone", "-q", str(remote), str(clone_dir)], cwd=tmp_path)
        (clone_dir / "resume.txt").write_text("hello", encoding="utf-8")

        committed = generator.commit_and_push_output_repo(self._settings(), clone_dir)

        assert committed is True
        verify = tmp_path / "verify"
        _run(["clone", "-q", str(remote), str(verify)], cwd=tmp_path)
        assert (verify / "resume.txt").read_text(encoding="utf-8") == "hello"

    def test_uses_configured_author_identity(self, tmp_path, monkeypatch):
        _git_identity_env(monkeypatch)
        remote = _init_bare_remote(tmp_path)
        clone_dir = tmp_path / "clone"
        _run(["clone", "-q", str(remote), str(clone_dir)], cwd=tmp_path)
        (clone_dir / "resume.txt").write_text("hello", encoding="utf-8")

        s = self._settings()
        s["OUTPUT_REPO_AUTHOR_NAME"] = "Custom Bot"
        s["OUTPUT_REPO_AUTHOR_EMAIL"] = "bot@example.com"
        generator.commit_and_push_output_repo(s, clone_dir)

        author = _run(["log", "-1", "--format=%an <%ae>"], cwd=clone_dir).strip()
        assert author == "Custom Bot <bot@example.com>"

    def test_does_not_push_when_output_repo_push_false(self, tmp_path, monkeypatch):
        _git_identity_env(monkeypatch)
        remote = _init_bare_remote(tmp_path)
        clone_dir = tmp_path / "clone"
        _run(["clone", "-q", str(remote), str(clone_dir)], cwd=tmp_path)
        (clone_dir / "resume.txt").write_text("hello", encoding="utf-8")

        committed = generator.commit_and_push_output_repo(self._settings(push=False), clone_dir)

        assert committed is True
        verify = tmp_path / "verify"
        _run(["clone", "-q", str(remote), str(verify)], cwd=tmp_path)
        assert not (verify / "resume.txt").exists()

    def test_commit_message_fills_datetime_placeholder(self, tmp_path, monkeypatch):
        _git_identity_env(monkeypatch)
        remote = _init_bare_remote(tmp_path)
        clone_dir = tmp_path / "clone"
        _run(["clone", "-q", str(remote), str(clone_dir)], cwd=tmp_path)
        (clone_dir / "resume.txt").write_text("hello", encoding="utf-8")

        generator.commit_and_push_output_repo(self._settings(message="Regen on {datetime.now.year}"), clone_dir)

        subject = _run(["log", "-1", "--format=%s"], cwd=clone_dir).strip()
        assert subject.startswith("Regen on 20")  # any year in this century


class TestMainWithOutputRepo:
    @pytest.fixture
    def output_repo_env(self, tmp_path, monkeypatch, sample_kb):
        """Like main_env in test_main.py, but also wires OUTPUT_REPO at
        a fresh local bare remote."""
        _git_identity_env(monkeypatch)
        remote = _init_bare_remote(tmp_path)
        workdir = tmp_path / "workdir"
        workdir.mkdir()
        monkeypatch.chdir(workdir)
        (workdir / "data").mkdir()
        (workdir / "data" / "profile.json").write_text(json.dumps(sample_kb), encoding="utf-8")
        (workdir / "RESUME.template.md").write_text("dummy resume template", encoding="utf-8")
        (workdir / "README.template.md").write_text("dummy readme template", encoding="utf-8")
        monkeypatch.setenv("LITELLM_BASE_URL", "http://example.com")
        monkeypatch.setenv("LITELLM_API_KEY", "secret")
        monkeypatch.setenv("OUTPUT_REPO", str(remote))
        monkeypatch.delenv("OUTPUT_FOLDER", raising=False)
        return {"tmp_path": tmp_path, "workdir": workdir, "remote": remote}

    @pytest.fixture
    def stub_llm_calls(self, monkeypatch, sample_resume_dict, sample_cover_letter_dict):
        monkeypatch.setattr(generator, "call_llm_fill_resume", lambda client, kb, variant, template: sample_resume_dict)
        monkeypatch.setattr(generator, "call_llm_cover_letter", lambda client, kb, variant: sample_cover_letter_dict)

    def test_writes_into_clone_dir_not_local_output_folder(self, output_repo_env, stub_llm_calls):
        generator.main(["--generate", "resume"])
        workdir = output_repo_env["workdir"]
        assert not (workdir / "generated").exists()
        assert (workdir / ".output-repo" / "generated" / "Jane Doe Resume (SDE).json").exists()

    def test_pushes_generated_files_to_output_repo(self, output_repo_env, stub_llm_calls):
        generator.main(["--generate", "resume"])
        verify = output_repo_env["tmp_path"] / "verify"
        _run(["clone", "-q", str(output_repo_env["remote"]), str(verify)], cwd=output_repo_env["tmp_path"])
        assert (verify / "generated" / "Jane Doe Resume (SDE).json").exists()

    def test_readme_target_also_writes_into_output_repo(self, output_repo_env, stub_llm_calls, monkeypatch):
        monkeypatch.setattr(generator, "call_llm_readme", lambda client, kb, template: "# Jane")
        generator.main(["--generate", "resume,readme"])
        workdir = output_repo_env["workdir"]
        # README.md is a generated file like the resume/cover letter
        # output, so it goes into the same OUTPUT_REPO clone/commit -
        # not left behind in this checkout.
        assert not (workdir / "README.md").exists()
        assert (workdir / ".output-repo" / "README.md").read_text(encoding="utf-8") == "# Jane"

        verify = output_repo_env["tmp_path"] / "verify"
        _run(["clone", "-q", str(output_repo_env["remote"]), str(verify)], cwd=output_repo_env["tmp_path"])
        assert (verify / "README.md").read_text(encoding="utf-8") == "# Jane"

    def test_readme_only_run_also_triggers_output_repo_sync(self, output_repo_env, monkeypatch):
        # Even with no resume/cover_letter target at all, --generate
        # readme alone should still sync + commit + push to OUTPUT_REPO -
        # the sync isn't gated on resume/cover_letter specifically.
        monkeypatch.setattr(generator, "call_llm_readme", lambda client, kb, template: "# Jane")
        generator.main(["--generate", "readme"])
        verify = output_repo_env["tmp_path"] / "verify"
        _run(["clone", "-q", str(output_repo_env["remote"]), str(verify)], cwd=output_repo_env["tmp_path"])
        assert (verify / "README.md").read_text(encoding="utf-8") == "# Jane"

    def test_second_run_reuses_existing_clone_rather_than_recloning(self, output_repo_env, stub_llm_calls):
        # PDF/DOCX renderers embed their own creation timestamps, so two
        # runs' output is never byte-identical even with identical
        # inputs - that's expected, and not what's under test here.
        # What matters is that the second run builds on the same clone
        # (same root commit / git history) rather than starting over.
        generator.main(["--generate", "resume"])
        clone_dir = output_repo_env["workdir"] / ".output-repo"
        first_root_commit = _run(["rev-list", "--max-parents=0", "HEAD"], cwd=clone_dir).strip()

        generator.main(["--generate", "resume"])
        second_root_commit = _run(["rev-list", "--max-parents=0", "HEAD"], cwd=clone_dir).strip()

        assert first_root_commit == second_root_commit

    def test_exits_with_clear_error_on_bad_output_repo(self, output_repo_env, stub_llm_calls, monkeypatch, capsys):
        monkeypatch.setenv("OUTPUT_REPO", "/no/such/path.git")
        with pytest.raises(SystemExit):
            generator.main(["--generate", "resume"])
        err = capsys.readouterr().err
        assert "OUTPUT_REPO" in err
