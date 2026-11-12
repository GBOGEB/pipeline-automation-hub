"""Tests for the PUSH-ME triage and the worktree prune of Invoke-WorkspaceAudit.ps1 (issue #1167).

Unit cases dot-source the script, which loads its helpers and stops before the audit runs, and call
Get-PushTriage / Invoke-WorktreePrune with fake git, gh and attrib runners. One end-to-end case runs the
audit report-only against a throwaway root. No case passes -Apply to the audit.
Skipped when pwsh or git is missing.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import unittest
import uuid
from pathlib import Path

SCRIPT = Path(__file__).with_name("Invoke-WorkspaceAudit.ps1")
PWSH = shutil.which("pwsh")
GIT = shutil.which("git")

HEAD = "a" * 40
OLD = "b" * 40
TWIN = "c" * 40

# Fake runners. $global:GitMap maps 'joined git args' -> @{Code; Out; Err}; unknown calls fail (exit 1).
# Every call is logged so a test can assert what ran and what did not.
HARNESS = r"""
$ErrorActionPreference = 'Stop'
. '__SCRIPT__'
$global:Calls = [System.Collections.Generic.List[string]]::new()
$cfg = Get-Content -Raw -LiteralPath '__CFG__' | ConvertFrom-Json -AsHashtable
$global:GitMap = $cfg.git; $global:GhMap = $cfg.gh
$global:GitSeq = @{}
$fakeGit = {
    param($Dir, $GitArgs)
    $k = $GitArgs -join ' '
    $global:Calls.Add("git $k")
    $v = $global:GitMap[$k]
    if ($v -is [System.Collections.IList]) {   # a list answers successive calls in order
        $n = [int]$global:GitSeq[$k]; $global:GitSeq[$k] = $n + 1
        $v = $v[[math]::Min($n, $v.Count - 1)]
    }
    if ($null -eq $v) { return [pscustomobject]@{ Code = 1; Out = @(); Err = '' } }
    [pscustomobject]@{ Code = [int]$v.Code; Out = @($v.Out); Err = [string]$v.Err }
}
$fakeGh = {
    param($Arguments)
    $k = $Arguments -join ' '
    $global:Calls.Add("gh $k")
    $v = $global:GhMap[$k]
    if ($null -eq $v) { return [pscustomobject]@{ ExitCode = 1; Out = ''; Err = 'HTTP 422' } }
    [pscustomobject]@{ ExitCode = 0; Out = [string]$v; Err = '' }
}
$fakeAttrib = { param($Path) $global:Calls.Add("attrib $Path"); [pscustomobject]@{ Code = 0; Out = '' } }
$a = $cfg.args
if ($cfg.fn -eq 'triage') {
    $state = [pscustomobject]$a.state
    $r = Get-PushTriage -Dir 'X:\repo' -State $state -Slug $a.slug -DefaultRef 'origin/master' -Git $fakeGit -Gh $fakeGh
    $out = [ordered]@{ Class = $r.Class; NeverPush = $r.NeverPush; Reasons = @($r.Reasons) }
}
else {
    $rows = Invoke-WorktreePrune -Repo $a.repo -Fix:([bool]$a.fix) -Git $fakeGit -Attrib $fakeAttrib
    $out = [ordered]@{ Rows = @($rows | ForEach-Object { [ordered]@{ Action = $_.Action; Detail = $_.Detail } }) }
}
$out.Calls = @($global:Calls)
$out | ConvertTo-Json -Depth 6 -Compress
"""

PUSH_STATE = {"Head": HEAD, "Branch": "feature", "Upstream": None, "Unpushed": 2, "Ahead": 0}
FMT = "--format=%H%x09%at%x09%ae%x09%s"


def ok(*lines: str) -> dict:
    return {"Code": 0, "Out": list(lines), "Err": ""}


@unittest.skipUnless(PWSH and GIT, "needs pwsh and git")
class WorkspaceAuditTriage(unittest.TestCase):
    def setUp(self) -> None:
        # Not TemporaryDirectory: owner-only folders can block git on Windows (AGENTS.md).
        self.root = Path(tempfile.gettempdir()) / f"ws-audit-test-{uuid.uuid4().hex[:12]}"
        os.makedirs(self.root)
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        self.env = {k: v for k, v in os.environ.items() if k not in ("GITHUB_TOKEN", "GH_TOKEN")}

    def run_fn(self, fn: str, args: dict, git: dict | None = None, gh: dict | None = None) -> dict:
        cfg = self.root / f"cfg-{uuid.uuid4().hex[:6]}.json"
        cfg.write_text(json.dumps({"fn": fn, "args": args, "git": git or {}, "gh": gh or {}}), encoding="utf-8")
        ps1 = self.root / "harness.ps1"
        ps1.write_text(HARNESS.replace("__SCRIPT__", str(SCRIPT)).replace("__CFG__", str(cfg)), encoding="utf-8")
        res = subprocess.run([PWSH, "-NoProfile", "-NonInteractive", "-File", str(ps1)],
                             capture_output=True, text=True, timeout=120, env=self.env)
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        return json.loads(res.stdout.strip().splitlines()[-1])

    def triage(self, git: dict, gh: dict | None = None, state: dict | None = None, slug: str = "o/r") -> dict:
        return self.run_fn("triage", {"state": state or PUSH_STATE, "slug": slug}, git, gh)

    # (1) detached HEAD checked against the remote --------------------------------------------
    def test_detached_head_on_remote_branch_is_landed(self) -> None:
        r = self.triage({"branch -r --contains HEAD": ok("  origin/fix/jade-topo-layers")},
                        state=dict(PUSH_STATE, Branch="(detached)"))
        self.assertEqual(r["Class"], "LANDED")
        self.assertIn("origin/fix/jade-topo-layers", r["Reasons"][0])

    def test_detached_head_equal_to_remote_tip_without_tracking_refs_is_landed(self) -> None:
        r = self.triage({"ls-remote --heads origin": ok(f"{HEAD}\trefs/heads/fix/x", f"{OLD}\trefs/heads/master")},
                        state=dict(PUSH_STATE, Branch="(detached)"))
        self.assertEqual(r["Class"], "LANDED")
        self.assertIn("origin/fix/x", r["Reasons"][0])

    # (2) merged PR / tree-identical twin ------------------------------------------------------
    def test_head_in_merged_pr_is_landed(self) -> None:
        jq = '[.[] | select(.merged_at != null) | "#\\(.number)"] | join(",")'
        r = self.triage({}, gh={f"api repos/o/r/commits/{HEAD}/pulls --jq {jq}": "#1047"})
        self.assertEqual(r["Class"], "LANDED")
        self.assertEqual(r["Reasons"], ["in merged PR #1047"])

    def test_tree_identical_twin_is_landed(self) -> None:
        r = self.triage({"diff --quiet --no-renames --no-ext-diff HEAD origin/feature --": ok()})
        self.assertEqual(r["Class"], "LANDED")
        self.assertEqual(r["Reasons"], ["tree identical to origin/feature"])

    # (3) pre-purge history --------------------------------------------------------------------
    def test_pre_purge_history_is_stale_and_never_push(self) -> None:
        line = "\t1729000000\tdev@example.invalid\tA10 phase b"
        r = self.triage({
            f"log --reverse {FMT} HEAD --not --remotes": ok(OLD + line, HEAD + "\t1730000000\tdev@example.invalid\tlater"),
            f"log {FMT} origin/master": ok(TWIN + "\t1731000000\tx@example.invalid\tnewer", TWIN[:39] + "d" + line),
        })
        self.assertEqual(r["Class"], "STALE")
        self.assertTrue(r["NeverPush"])
        self.assertIn("never push", r["Reasons"][0])

    def test_same_subject_other_author_date_is_not_stale(self) -> None:
        r = self.triage({
            f"log --reverse {FMT} HEAD --not --remotes": ok(OLD + "\t1729000000\tdev@example.invalid\tA10"),
            f"log {FMT} origin/master": ok(TWIN + "\t1729000001\tdev@example.invalid\tA10"),
        })
        self.assertEqual(r["Class"], "PUSH-ME")

    # (4) public repo guard --------------------------------------------------------------------
    def office_git(self) -> dict:
        return {
            "-c core.quotePath=false ls-files": ok("README.md", "contracts/QPS Addendum.docx", "scan.PDF"),
            "-c core.quotePath=false ls-tree -r --name-only origin/master": ok("README.md", "scan.PDF"),
        }

    def test_public_remote_missing_office_files_is_public_risk(self) -> None:
        r = self.triage(self.office_git(), gh={"api repos/o/r --jq .private": "false"})
        self.assertEqual(r["Class"], "PUBLIC-RISK")
        self.assertTrue(r["NeverPush"])
        self.assertIn("1 office/PDF file(s)", r["Reasons"][0])
        self.assertIn("QPS Addendum.docx", r["Reasons"][0])

    def test_private_remote_with_office_files_stays_push_me(self) -> None:
        r = self.triage(self.office_git(), gh={"api repos/o/r --jq .private": "true"})
        self.assertEqual(r["Class"], "PUSH-ME")
        self.assertFalse(r["NeverPush"])

    def test_real_unlanded_work_stays_push_me(self) -> None:
        r = self.triage({})
        self.assertEqual(r["Class"], "PUSH-ME")
        self.assertIn("real unlanded work", r["Reasons"][-1])

    # (5) worktree prune -----------------------------------------------------------------------
    def prune_repo(self) -> tuple[Path, Path]:
        repo = self.root / "Documents"
        admin = repo / ".git" / "worktrees" / "recursing-mayer"
        os.makedirs(admin / "fsmonitor--daemon")
        return repo, admin

    def denied(self, repo: Path) -> dict:
        err = "error: failed to delete '.git/worktrees/recursing-mayer/fsmonitor--daemon': Permission denied"
        return {
            "worktree prune": [{"Code": 0, "Out": [], "Err": err}, ok()],
            "rev-parse --path-format=absolute --git-common-dir": ok(str(repo / ".git")),
        }

    def test_prune_ok_reports_one_row(self) -> None:
        r = self.run_fn("prune", {"repo": "X:\\r", "fix": True}, {"worktree prune": ok()})
        self.assertEqual([x["Action"] for x in r["Rows"]], ["worktree prune"])

    def test_prune_permission_denied_with_fix_clears_readonly_on_that_folder_and_retries(self) -> None:
        repo, admin = self.prune_repo()
        r = self.run_fn("prune", {"repo": str(repo), "fix": True}, self.denied(repo))
        self.assertEqual([x["Action"] for x in r["Rows"]], ["prune failed", "attrib -R", "worktree prune (retry)"])
        self.assertIn("Permission denied", r["Rows"][0]["Detail"])
        self.assertEqual([c for c in r["Calls"] if c.startswith("attrib")], [f"attrib {admin}"])
        self.assertEqual(r["Calls"].count("git worktree prune"), 2)

    def test_prune_permission_denied_without_fix_only_reports(self) -> None:
        repo, admin = self.prune_repo()
        r = self.run_fn("prune", {"repo": str(repo), "fix": False}, self.denied(repo))
        self.assertEqual([x["Action"] for x in r["Rows"]], ["prune failed", "prune not fixed"])
        self.assertIn(str(admin), r["Rows"][1]["Detail"])
        self.assertFalse([c for c in r["Calls"] if c.startswith("attrib")])
        self.assertEqual(r["Calls"].count("git worktree prune"), 1)

    def test_prune_refuses_a_name_outside_worktrees(self) -> None:
        repo, _ = self.prune_repo()
        git = self.denied(repo)
        git["worktree prune"][0]["Err"] = "error: failed to delete '.git/worktrees/..': Permission denied"
        r = self.run_fn("prune", {"repo": str(repo), "fix": True}, git)
        self.assertFalse([c for c in r["Calls"] if c.startswith("attrib")])
        self.assertEqual(r["Rows"][1]["Action"], "prune not fixed")

    def test_prune_other_error_is_reported_not_fixed(self) -> None:
        r = self.run_fn("prune", {"repo": "X:\\r", "fix": True},
                        {"worktree prune": {"Code": 128, "Out": [], "Err": "fatal: not a git repository"}})
        self.assertEqual([x["Action"] for x in r["Rows"]], ["prune failed"])
        self.assertFalse([c for c in r["Calls"] if c.startswith("attrib")])

    # end to end, report-only ------------------------------------------------------------------
    def test_report_only_audit_marks_pushed_detached_head_landed(self) -> None:
        cfg = self.root / "gitconfig"
        cfg.write_text("", encoding="utf-8")
        env = dict(self.env, GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=str(cfg),
                   GIT_AUTHOR_NAME="T", GIT_AUTHOR_EMAIL="t@example.invalid",
                   GIT_COMMITTER_NAME="T", GIT_COMMITTER_EMAIL="t@example.invalid")

        def git(cwd: Path, *a: str) -> str:
            return subprocess.run(["git", *a], cwd=cwd, env=env, capture_output=True, text=True, check=True).stdout.strip()

        origin, seed, work = self.root / "origin.git", self.root / "seed", self.root / "work"
        os.makedirs(work)
        git(self.root, "init", "-q", "--bare", "-b", "master", str(origin))
        git(self.root, "clone", "-q", str(origin), str(seed))
        (seed / "a.txt").write_text("a\n", encoding="utf-8")
        git(seed, "add", "a.txt")
        git(seed, "commit", "-q", "-m", "base")
        git(seed, "push", "-q", "origin", "master")
        clone = work / "recursing-mayer"
        git(self.root, "clone", "-q", "--single-branch", "-b", "master", str(origin), str(clone))
        (clone / "b.txt").write_text("b\n", encoding="utf-8")
        git(clone, "add", "b.txt")
        git(clone, "commit", "-q", "-m", "feature")
        git(clone, "push", "-q", "origin", "HEAD:refs/heads/fix/landed")   # no tracking ref: single-branch
        git(clone, "checkout", "-q", "--detach")
        git(clone, "branch", "-q", "-f", "master", "origin/master")

        args = [PWSH, "-NoProfile", "-NonInteractive", "-File", str(SCRIPT), "-Root", str(work),
                "-PushAfterHours", "0", "-ReportPath", str(self.root / "report"), "-SkipSize", "-SkipTokenCheck"]
        self.assertNotIn("-Apply", args)
        res = subprocess.run(args, capture_output=True, text=True, timeout=180, env=env)
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        report = json.loads(next((self.root / "report").glob("workspace-audit-*.json")).read_text(encoding="utf-8-sig"))
        entry = report["Entries"][0] if isinstance(report["Entries"], list) else report["Entries"]
        self.assertEqual(entry["Class"], "LANDED", entry)
        self.assertIn("origin/fix/landed", entry["Triage"])
        self.assertEqual(report["Summary"]["PushMe"], 0)
        self.assertEqual(report["Actions"], [])


if __name__ == "__main__":
    unittest.main()
