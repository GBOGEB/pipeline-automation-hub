"""Dry-run tests for Restack-Pr.ps1 against a throwaway repo.

Each test builds a bare "origin" and a clone under the temp folder, puts a fake `gh` first on PATH
that prints a fixed `gh pr view --json` answer, and runs the script WITHOUT -Apply. It checks the
printed replay plan, that refs/heads/* (clone and origin) is unchanged, and the refusal paths.
Skipped when pwsh or git >= 2.40 is missing. Never passes -Apply.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
import uuid
from pathlib import Path

SCRIPT = Path(__file__).with_name("Restack-Pr.ps1")
PWSH = shutil.which("pwsh")


def _git_ok() -> bool:
    try:
        out = subprocess.run(["git", "--version"], capture_output=True, text=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        return False
    m = re.search(r"(\d+)\.(\d+)", out)
    return bool(m) and (int(m.group(1)), int(m.group(2))) >= (2, 40)


@unittest.skipUnless(PWSH and _git_ok(), "needs pwsh and git >= 2.40")
class RestackPrDryRun(unittest.TestCase):
    def setUp(self) -> None:
        # Not TemporaryDirectory: owner-only folders can block git on Windows (AGENTS.md).
        self.root = Path(tempfile.gettempdir()) / f"restack-pr-test-{uuid.uuid4().hex[:12]}"
        os.makedirs(self.root)
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        empty_cfg = self.root / "gitconfig"
        empty_cfg.write_text("", encoding="utf-8")
        self.env = dict(os.environ)
        for k in ("GITHUB_TOKEN", "GH_TOKEN", "GIT_AUTHOR_NAME", "GIT_AUTHOR_EMAIL", "GIT_AUTHOR_DATE"):
            self.env.pop(k, None)
        self.env.update(
            GIT_CONFIG_NOSYSTEM="1",
            GIT_CONFIG_GLOBAL=str(empty_cfg),
            GIT_COMMITTER_NAME="Restack Test",
            GIT_COMMITTER_EMAIL="restack@example.invalid",
        )
        self.origin = self.root / "origin.git"
        self.clone = self.root / "clone"
        self.seed = self.root / "seed"
        self.bin = self.root / "bin"
        os.makedirs(self.bin)
        self.git(self.root, "init", "-q", "--bare", "-b", "master", str(self.origin))
        self.git(self.root, "clone", "-q", str(self.origin), str(self.seed))

    # helpers -------------------------------------------------------------------------------
    def git(self, cwd: Path, *args: str, author: str = "Alice Author <alice@example.invalid>") -> str:
        name, email = author[:-1].split(" <")
        env = dict(self.env, GIT_AUTHOR_NAME=name, GIT_AUTHOR_EMAIL=email)
        return subprocess.run(
            ["git", *args], cwd=cwd, env=env, capture_output=True, text=True, check=True
        ).stdout.strip()

    def commit(self, path: str, text: str, subject: str, **kw: str) -> str:
        (self.seed / path).write_text(text, encoding="utf-8", newline="\n")
        self.git(self.seed, "add", path)
        self.git(self.seed, "commit", "-q", "-m", subject, **kw)
        return self.git(self.seed, "rev-parse", "HEAD")

    def fake_gh(self, head_ref: str, head_oid: str) -> None:
        answer = {
            "baseRefName": "master",
            "headRefName": head_ref,
            "headRefOid": head_oid,
            "isCrossRepository": False,
            "state": "OPEN",
        }
        (self.bin / "pr.json").write_text(json.dumps(answer), encoding="utf-8")
        if sys.platform == "win32":
            (self.bin / "gh.cmd").write_text('@type "%~dp0pr.json"\r\n', encoding="ascii")
        else:
            gh = self.bin / "gh"
            gh.write_text('#!/bin/sh\ncat "$(dirname "$0")/pr.json"\n', encoding="ascii")
            gh.chmod(0o755)

    def refs(self, repo: Path, prefix: str) -> str:
        return self.git(repo, "for-each-ref", "--format=%(refname) %(objectname)", prefix)

    def run_script(self, *extra: str) -> subprocess.CompletedProcess[str]:
        env = dict(self.env, PATH=str(self.bin) + os.pathsep + self.env.get("PATH", ""))
        args = [PWSH, "-NoProfile", "-NonInteractive", "-File", str(SCRIPT),
                "-Clone", str(self.clone), "-Repo", "example/repo", "-Pr", "7", *extra]
        self.assertNotIn("-Apply", args)
        return subprocess.run(args, env=env, capture_output=True, text=True, timeout=120)

    def stack(self, conflict: bool = False) -> str:
        """master: base + one later commit; feature: two commits plus a regen commit."""
        self.commit("a.txt", "one\n", "base")
        self.commit("b.txt", "base b\n", "base b")
        self.git(self.seed, "push", "-q", "origin", "master")
        self.git(self.seed, "switch", "-q", "-c", "feature")
        self.commit("c.txt", "feature c\n", "feat: add c", author="Bob Builder <bob@example.invalid>")
        self.commit("gen.json", '{"sha": "old"}\n', "chore: regen launcher")
        self.commit("a.txt", "one\nfeature line\n" if not conflict else "feature wins\n", "feat: edit a")
        head = self.git(self.seed, "rev-parse", "HEAD")
        self.git(self.seed, "push", "-q", "origin", "feature")
        self.git(self.seed, "switch", "-q", "master")
        if conflict:
            self.commit("a.txt", "master wins\n", "master: rewrite a")
        else:
            self.commit("b.txt", "master moved b\n", "master: move b")
        self.git(self.seed, "push", "-q", "origin", "master")
        self.git(self.root, "clone", "-q", str(self.origin), str(self.clone))
        return head

    # tests ---------------------------------------------------------------------------------
    def test_dry_run_prints_plan_and_leaves_heads_untouched(self) -> None:
        head = self.stack()
        self.fake_gh("feature", head)
        before = (self.refs(self.clone, "refs/heads"), self.refs(self.origin, "refs/heads"))

        res = self.run_script("-Drop", "^chore: regen")
        out = res.stdout + res.stderr
        self.assertEqual(res.returncode, 0, out)

        self.assertIn("DRY RUN", out)
        self.assertRegex(out, r"#7 plan: replay 3 commit\(s\) of feature \([0-9a-f]{9}\) onto master")
        self.assertRegex(out, r"pick [0-9a-f]+ feat: add c")
        self.assertRegex(out, r"drop [0-9a-f]+ chore: regen launcher")
        self.assertRegex(out, r"pick [0-9a-f]+ feat: edit a")
        self.assertIn("#7 CLEAN", out)
        self.assertNotRegex(out, r"(?m)^\s+pushed ")

        self.assertEqual(before, (self.refs(self.clone, "refs/heads"), self.refs(self.origin, "refs/heads")))
        self.assertEqual(self.git(self.origin, "rev-parse", "refs/heads/feature"), head)

        rebased = self.git(self.clone, "rev-parse", "refs/restack/7/rebased")
        onto = self.git(self.clone, "rev-parse", "refs/restack/7/onto")
        self.assertEqual(self.git(self.clone, "rev-list", "--count", f"{onto}..{rebased}"), "2")
        self.assertEqual(self.git(self.clone, "merge-base", onto, rebased), onto)
        self.assertEqual(self.git(self.clone, "ls-tree", "--name-only", rebased, "gen.json"), "")
        self.assertEqual(
            self.git(self.clone, "log", "--format=%an|%s", f"{onto}..{rebased}").splitlines(),
            ["Alice Author|feat: edit a", "Bob Builder|feat: add c"],
        )

    def test_head_moved_is_refused(self) -> None:
        self.stack()
        self.fake_gh("feature", "0" * 40)
        res = self.run_script()
        out = res.stdout + res.stderr
        self.assertEqual(res.returncode, 0, out)
        self.assertIn("branch moved since gh read it", out)
        self.assertNotIn("plan:", out)
        self.assertEqual(self.refs(self.clone, "refs/restack/7/rebased"), "")

    def test_conflict_is_reported_with_files(self) -> None:
        head = self.stack(conflict=True)
        self.fake_gh("feature", head)
        before = self.refs(self.origin, "refs/heads")
        res = self.run_script()
        out = res.stdout + res.stderr
        self.assertEqual(res.returncode, 0, out)
        self.assertRegex(out, r"#7 CONFLICT at [0-9a-f]+ feat: edit a")
        self.assertRegex(out, r"(?m)^\s+a\.txt\s*$")
        self.assertEqual(self.refs(self.clone, "refs/restack/7/rebased"), "")
        self.assertEqual(before, self.refs(self.origin, "refs/heads"))

    def test_gh_failure_aborts_batch(self) -> None:
        self.stack()
        if sys.platform == "win32":
            (self.bin / "gh.cmd").write_text("@exit /b 1\r\n", encoding="ascii")
        else:
            gh = self.bin / "gh"
            gh.write_text("#!/bin/sh\nexit 1\n", encoding="ascii")
            gh.chmod(0o755)
        res = self.run_script()
        out = res.stdout + res.stderr
        self.assertNotEqual(res.returncode, 0, out)
        self.assertIn("batch aborted", out)
        self.assertNotIn("plan:", out)

    def test_caller_author_env_is_restored(self) -> None:
        head = self.stack()
        self.fake_gh("feature", head)
        env = dict(self.env, PATH=str(self.bin) + os.pathsep + self.env.get("PATH", ""))
        cmd = (
            "$env:GIT_AUTHOR_NAME='Keep Me'; $env:GIT_AUTHOR_EMAIL='keep@example.invalid'; "
            f"& '{SCRIPT}' -Clone '{self.clone}' -Repo example/repo -Pr 7; "
            "Write-Output \"AFTER=$env:GIT_AUTHOR_NAME|$env:GIT_AUTHOR_EMAIL|$([bool]$env:GIT_AUTHOR_DATE)\""
        )
        res = subprocess.run([PWSH, "-NoProfile", "-NonInteractive", "-Command", cmd],
                             env=env, capture_output=True, text=True, timeout=120)
        out = res.stdout + res.stderr
        self.assertIn("#7 CLEAN", out)
        self.assertIn("AFTER=Keep Me|keep@example.invalid|False", out)
        rebased = self.git(self.clone, "rev-parse", "refs/restack/7/rebased")
        self.assertEqual(self.git(self.clone, "log", "-1", "--format=%an", rebased), "Alice Author")


if __name__ == "__main__":
    unittest.main(verbosity=2)
