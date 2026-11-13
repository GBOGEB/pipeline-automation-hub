"""rex.py: catalog integrity, mining coverage, diff parsing and the offline detectors. No network."""
import importlib.util
import json
import shutil
import subprocess
import tempfile
import unittest
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("maroon_rex", HERE / "rex.py")
R = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(R)

CAT = R.load_catalog()


def entry(rid):
    return next(e for e in CAT["entries"] if e["rex_id"] == rid)


class Catalog(unittest.TestCase):
    def test_entries_are_complete_and_known_kinds(self):
        kinds = set(R.DETECTORS) | {"ruff"}
        for e in CAT["entries"]:
            self.assertRegex(e["rex_id"], r"^REX-\d{3}$")
            self.assertIn(e["detector"]["kind"], kinds, e["rex_id"])
            self.assertIn(e["mode"], {"fix", "autofix"}, e["rex_id"])
            self.assertTrue(e["known_fix"].strip() and e["review_match"], e["rex_id"])

    def test_ruff_codes_are_not_shared_between_entries(self):
        seen = {}
        for e in CAT["entries"]:
            for c in e["detector"].get("codes", []):
                self.assertNotIn(c, seen, f"{c} in {seen.get(c)} and {e['rex_id']}")
                seen[c] = e["rex_id"]

    def test_duplicate_ids_are_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "c.json"
            p.write_text(json.dumps({"schema": R.SCHEMA, "entries": [{"rex_id": "REX-001"}, {"rex_id": "REX-001"}]}),
                         encoding="utf-8", newline="\n")
            with self.assertRaises(SystemExit):
                R.load_catalog(p)


class Mine(unittest.TestCase):
    def test_first_line_strips_badges_and_joins_bare_scanner_header(self):
        self.assertEqual(R.first_line("## Bandit / \n\nUse of assert detected. The enclosed code"),
                         "Bandit / Use of assert detected. The enclosed code")
        badge = "**<sub><sub>![P1 Badge](https://x/y.svg)</sub></sub>  Regenerate the governed workflow inventory**\n\nbody"
        self.assertEqual(R.first_line(badge), "Regenerate the governed workflow inventory")

    def test_coverage_counts_comments_and_distinct_prs_and_skips_replies(self):
        rule = "## Semgrep OSS / Semgrep Finding: yaml.github-actions.security.github-actions-mutable-action-tag"
        rows = [{"repo": "r", "pr": 1, "body": rule}, {"repo": "r", "pr": 1, "body": rule},
                {"repo": "r", "pr": 2, "body": rule}, {"repo": "r", "pr": 2, "body": rule, "reply": True}]
        rows += [{"repo": "r", "pr": n, "body": "Some brand new recurring reviewer theme here"} for n in (1, 2, 3)]
        rep = R.mine(CAT, rows, min_prs=3)
        self.assertEqual(rep["comments"], 6)
        self.assertEqual(rep["entries"]["REX-001"], {"comments": 3, "prs": 2})
        self.assertEqual(rep["coverage"], 0.5)
        self.assertEqual([c["prs"] for c in rep["candidates"]], [3])

    def test_write_evidence_round_trips(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "c.json"
            shutil.copy(R.CATALOG, p)
            R.write_evidence(p, {"entries": {"REX-001": {"comments": 9, "prs": 4}}, "comments": 10, "coverage": 0.9}, "t")
            back = R.load_catalog(p)
            self.assertEqual(back["entries"][0]["evidence"], {"comments": 9, "prs": 4})
            self.assertEqual(back["entries"][1]["evidence"], {"comments": 0, "prs": 0})
            self.assertNotIn(b"\r\n", p.read_bytes())


class Diff(unittest.TestCase):
    def test_added_lines_numbers_new_side_only(self):
        diff = ("diff --git a/x.py b/x.py\n--- a/x.py\n+++ b/x.py\n@@ -3,0 +4,2 @@\n+a\n+b\n"
                "@@ -10 +12 @@\n-old\n+new\n--- a/gone.py\n+++ /dev/null\n@@ -1 +0,0 @@\n-x\n")
        self.assertEqual(R.added_lines(diff), {"x.py": {4: "a", 5: "b", 12: "new"}})


class Detectors(unittest.TestCase):
    def setUp(self):
        # Not mkdtemp: on Windows it sets an owner-only ACL that child processes (git, ruff) may not read.
        self.root = Path(tempfile.gettempdir()) / f"rex_test_{uuid.uuid4().hex}"
        self.root.mkdir()
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)

    def put(self, rel, text):
        p = self.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8", newline="\n")
        return {i: s for i, s in enumerate(text.splitlines(), 1)}

    def run_kind(self, rid, files):
        return list(R.DETECTORS[entry(rid)["detector"]["kind"]](entry(rid), files, self.root))

    def test_unpinned_action_tag_flags_tags_not_shas_or_local(self):
        sha = "b4ffde65f46336ab88eb53be808477a3936bae11"
        lines = {1: "      - uses: actions/checkout@v4", 2: f"      - uses: actions/checkout@{sha} # v4",
                 3: "      - uses: ./.github/actions/local", 4: "    uses: org/repo/.github/workflows/x.yml@main"}
        hits = self.run_kind("REX-001", {".github/workflows/ci.yml": lines})
        self.assertEqual([h[1] for h in hits], [1, 4])
        self.assertEqual(self.run_kind("REX-001", {"docs/ci.yml": lines}), [])

    def test_write_text_without_newline_by_ast(self):
        lines = self.put("g.py", "from pathlib import Path\np = Path('x')\np.write_text('a', encoding='utf-8')\n"
                                 "p.write_text(p.read_text(encoding='ascii').rstrip(), newline='\\n')\n")
        self.assertEqual([h[1] for h in self.run_kind("REX-017", {"g.py": lines})], [3])
        self.assertEqual(self.run_kind("REX-017", {"g.py": {4: lines[4]}}), [])

    def test_dual_import_needs_an_added_line(self):
        lines = self.put("m.py", "import json\nfrom json import dumps\nimport os\n")
        self.assertEqual([h[1] for h in self.run_kind("REX-005", {"m.py": {2: lines[2]}})], [2])
        self.assertEqual(self.run_kind("REX-005", {"m.py": {3: lines[3]}}), [])

    def test_workflow_without_permissions(self):
        self.put(".github/workflows/a.yml", "on: push\njobs: {}\n")
        self.put(".github/workflows/b.yml", "on: push\npermissions:\n  contents: read\njobs: {}\n")
        files = {".github/workflows/a.yml": {1: "on: push"}, ".github/workflows/b.yml": {1: "on: push"}}
        self.assertEqual([h[0] for h in self.run_kind("REX-006", files)], [".github/workflows/a.yml"])

    def test_companion_fires_only_when_owner_tool_exists_and_output_untouched(self):
        files = {".github/workflows/x.yml": {1: "on: push"}}
        self.assertEqual(self.run_kind("REX-015", files), [])
        self.put("ci/governance/audit_ci_workflows.py", "")
        self.assertEqual(len(self.run_kind("REX-015", files)), 1)
        files["docs/ci/WORKFLOW_RATIONALIZATION.md"] = {1: "x"}
        self.assertEqual(self.run_kind("REX-015", files), [])

    def test_pinned_oid_companion_reuses_hints_regex(self):
        self.put("mission-control/jade_temple/tools/cicd_dag.py", "")
        files = {"mission-control/gogreen/scale_dock.py": {1: "x"}}
        self.assertEqual(len(self.run_kind("REX-016", files)), 1)
        files["mission-control/jade_temple/site/cicd_dag.json"] = {1: "{}"}
        self.assertEqual(self.run_kind("REX-016", files), [])

    @unittest.skipUnless(shutil.which("git"), "git not available")
    def test_exec_bit_reads_git_mode(self):
        # Per-command safe.directory: an elevated Windows shell owns temp files as Administrators.
        def g(*a):
            return subprocess.run(["git", "-c", "safe.directory=*", *a], cwd=self.root, capture_output=True,
                                  text=True, check=True).stdout
        orig = R.git
        R.git = lambda *a, cwd=None: g(*a)
        self.addCleanup(setattr, R, "git", orig)
        g("init", "-q")
        lines = self.put("s.py", "#!/usr/bin/env python3\nprint(1)\n")
        g("add", "s.py")
        g("update-index", "--chmod=-x", "s.py")
        self.assertEqual(len(self.run_kind("REX-004", {"s.py": lines})), 1)
        g("update-index", "--chmod=+x", "s.py")
        self.assertEqual(self.run_kind("REX-004", {"s.py": lines}), [])

    @unittest.skipUnless(shutil.which("git"), "git not available")
    def test_base_falls_back_when_origin_head_is_absent(self):
        def g(*a):
            return subprocess.run(["git", "-c", "safe.directory=*", "-c", "user.name=t", "-c", "user.email=t@t",
                                   *a], cwd=self.root, capture_output=True, text=True, check=True).stdout
        orig = R.git
        R.git = lambda *a, cwd=None: g(*a)
        self.addCleanup(setattr, R, "git", orig)
        g("init", "-q")
        self.put("a.txt", "a\n")
        g("add", "a.txt")
        g("commit", "-q", "-m", "base")
        g("update-ref", "refs/remotes/origin/main", "HEAD")
        self.put("b.py", "x = 1\n")
        g("add", "b.py")
        g("commit", "-q", "-m", "change")
        self.assertEqual(R.resolve_base(self.root, "origin/HEAD"), "origin/main")
        self.assertEqual(list(R.changed(self.root, "origin/HEAD")), ["b.py"])
        with self.assertRaises(SystemExit):
            R.resolve_base(self.root, "origin/nope")

    @unittest.skipUnless(shutil.which("ruff"), "ruff not installed")
    def test_ruff_hits_only_added_lines_and_respects_test_exclude(self):
        lines = self.put("pkg/a.py", "import os\nimport sys\nassert sys\n")
        self.put("tests/test_a.py", "assert True\n")
        files = {"pkg/a.py": {2: lines[2], 3: lines[3]}, "tests/test_a.py": {1: "assert True"}}
        hits, note = R.ruff_findings(CAT, files, self.root, None)
        if note and "could not read" in note:
            self.skipTest(f"this workstation's ruff cannot read the temp files: {note}")
        self.assertIsNone(note)
        self.assertEqual(sorted(hits), ["REX-019"])
        self.assertEqual([h[0] for h in hits["REX-019"]], ["pkg/a.py"])

    @unittest.skipUnless(shutil.which("ruff"), "ruff not installed")
    def test_every_catalog_ruff_code_is_selectable(self):
        codes = sorted(c for e in CAT["entries"] if e["detector"]["kind"] == "ruff" for c in e["detector"]["codes"] if c != "E999")
        run = subprocess.run([shutil.which("ruff"), "check", "--isolated", "--no-cache", "--preview", "--select", ",".join(codes),
                              "--stdin-filename", "x.py", "-"], input="x = 1\n", capture_output=True, text=True, check=False)
        self.assertIn(run.returncode, (0, 1), run.stderr)

    def test_scan_reports_missing_ruff_as_a_note_not_a_pass(self):
        lines = self.put("a.py", "import os\n")
        orig = R.shutil.which
        R.shutil.which = lambda name: None
        try:
            rep = R.scan(CAT, {"a.py": lines}, self.root)
        finally:
            R.shutil.which = orig
        self.assertEqual(rep["authority"], R.AUTHORITY)
        self.assertEqual(rep["findings"], [])
        self.assertTrue(rep["notes"] and "ruff not on PATH" in rep["notes"][0])


if __name__ == "__main__":
    unittest.main()
