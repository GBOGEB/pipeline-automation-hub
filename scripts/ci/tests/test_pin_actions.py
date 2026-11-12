"""Controls for scripts/ci/pin_actions.py (resolution is mocked; no network, no gh)."""
import importlib.util
import io
import sys
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("pin_actions", HERE.parent / "pin_actions.py")
pa = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(pa)

SHA_A = "a" * 40
SHA_B = "b" * 40
SHA_OLD = "11bd71901bbe5b1630ceea73d27597364c9af683"

WORKFLOW = (
    "name: demo\r\n"
    "jobs:\r\n"
    "  build:\r\n"
    "    # uses: GBOGEB/pipeline-automation-hub/.github/workflows/jade-reusable-ci.yml@v1\r\n"
    "    steps:\r\n"
    "      - uses: actions/checkout@v4\r\n"
    "      - name: py\r\n"
    "        uses: \"actions/setup-python@v5\"   # keep me\r\n"
    "      - uses: actions/checkout@v4\r\n"
    f"      - uses: actions/upload-artifact@{SHA_OLD} # v4.2.2\r\n"
    "      - uses: ./.github/actions/local\r\n"
    "      - uses: docker://alpine:3.20\r\n"
    "      - uses: github/codeql-action/init@v3\r\n"
    "  reuse-self:\r\n"
    "    uses: GBOGEB/pipeline-automation-hub/.github/workflows/jade-reusable-ci.yml@master\r\n"
    "  reuse-other:\r\n"
    "    uses: octo/shared/.github/workflows/ci.yml@v2\r\n"
)


class FakeResolver:
    def __init__(self, table):
        self.table, self.calls = table, []

    def __call__(self, repo, ref):
        self.calls.append((repo, ref))
        if (repo, ref) not in self.table:
            raise pa.ResolveError(f"{repo}@{ref}: 404")
        return self.table[(repo, ref)]


TABLE = {
    ("actions/checkout", "v4"): SHA_A,
    ("actions/setup-python", "v5"): SHA_B,
    ("github/codeql-action", "v3"): "c" * 40,
    ("octo/shared", "v2"): "d" * 40,
}


class PinText(unittest.TestCase):
    def setUp(self):
        self.fake = FakeResolver(TABLE)
        self.new, self.changes = pa.pin_text(WORKFLOW, pa.Resolver(self.fake))
        self.lines = self.new.split("\r\n")

    def test_rewrites_tag_to_sha_with_tag_comment(self):
        self.assertEqual(self.lines[5], f"      - uses: actions/checkout@{SHA_A} # v4")

    def test_keeps_quotes_and_existing_comment(self):
        self.assertEqual(self.lines[7], f"        uses: \"actions/setup-python@{SHA_B}\" # v5 (keep me)")

    def test_subpath_action_resolves_against_owner_repo(self):
        self.assertIn(f"      - uses: github/codeql-action/init@{'c' * 40} # v3", self.lines)
        self.assertIn(("github/codeql-action", "v3"), self.fake.calls)

    def test_skips_pinned_local_docker_self_reusable_and_comments(self):
        for keep in (f"      - uses: actions/upload-artifact@{SHA_OLD} # v4.2.2",
                     "      - uses: ./.github/actions/local",
                     "      - uses: docker://alpine:3.20",
                     "    uses: GBOGEB/pipeline-automation-hub/.github/workflows/jade-reusable-ci.yml@master",
                     "    # uses: GBOGEB/pipeline-automation-hub/.github/workflows/jade-reusable-ci.yml@v1"):
            self.assertIn(keep, self.lines)

    def test_pins_foreign_reusable_workflow(self):
        self.assertIn(f"    uses: octo/shared/.github/workflows/ci.yml@{'d' * 40} # v2", self.lines)

    def test_cache_resolves_each_ref_once(self):
        self.assertEqual(self.fake.calls.count(("actions/checkout", "v4")), 1)
        self.assertEqual(len(self.changes), 5)

    def test_only_uses_lines_change_and_crlf_preserved(self):
        old, new = WORKFLOW.split("\r\n"), self.new.split("\r\n")
        self.assertEqual(len(old), len(new))
        self.assertEqual(self.new.count("\r\n"), WORKFLOW.count("\r\n"))
        changed = {i + 1 for i, (a, b) in enumerate(zip(old, new)) if a != b}
        self.assertEqual(changed, {n for n, _, _ in self.changes})

    def test_idempotent(self):
        again, changes = pa.pin_text(self.new, pa.Resolver(self.fake))
        self.assertEqual(again, self.new)
        self.assertEqual(changes, [])

    def test_scan_text_after_pin_is_clean(self):
        self.assertEqual(pa.scan_text(self.new), [])
        self.assertEqual([r for _, r in pa.scan_text(WORKFLOW)],
                         ["actions/checkout@v4", "actions/setup-python@v5", "actions/checkout@v4",
                          "github/codeql-action/init@v3", "octo/shared/.github/workflows/ci.yml@v2"])

    def test_bad_resolution_is_rejected(self):
        r = pa.Resolver(lambda repo, ref: "v4")
        with self.assertRaises(pa.ResolveError):
            r("actions/checkout", "v4")


class Cli(unittest.TestCase):
    def run_main(self, argv, resolve=None):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            rc = pa.main(argv, resolve=resolve)
        return rc, out.getvalue(), err.getvalue()

    def test_check_fails_then_passes_after_pin(self):
        with tempfile.TemporaryDirectory() as d:
            wf = Path(d) / "wf.yml"
            wf.write_bytes(WORKFLOW.encode())
            rc, out, _ = self.run_main(["--check", str(wf)])
            self.assertEqual(rc, 1)
            self.assertIn(":6: unpinned action reference: actions/checkout@v4", out)
            rc, _, _ = self.run_main([str(wf)], resolve=FakeResolver(TABLE))
            self.assertEqual(rc, 0)
            self.assertIn(b"\r\n", wf.read_bytes())
            rc, out, _ = self.run_main(["--check", str(wf)])
            self.assertEqual(rc, 0, out)

    def test_exclude_by_basename(self):
        with tempfile.TemporaryDirectory() as d:
            a, b = Path(d) / "a.yml", Path(d) / "skip.yml"
            a.write_text("steps:\n  - uses: actions/checkout@v4\n")
            b.write_text("steps:\n  - uses: actions/checkout@v4\n")
            rc, _, _ = self.run_main([str(Path(d) / "*.yml"), "--exclude", "skip.yml"], resolve=FakeResolver(TABLE))
            self.assertEqual(rc, 0)
            self.assertIn(SHA_A, a.read_text())
            self.assertNotIn(SHA_A, b.read_text())

    def test_resolution_error_exits_2_without_partial_write(self):
        with tempfile.TemporaryDirectory() as d:
            wf = Path(d) / "wf.yml"
            wf.write_text("steps:\n  - uses: actions/checkout@v4\n  - uses: nope/missing@v1\n")
            before = wf.read_text()
            rc, _, err = self.run_main([str(wf)], resolve=FakeResolver(TABLE))
            self.assertEqual(rc, 2)
            self.assertIn("error", err)
            self.assertEqual(wf.read_text(), before)


class CensusParity(unittest.TestCase):
    """The pinned/kind classification must match the JADE DevOps census (workflows.action_ref)."""

    def test_matches_census_action_ref(self):
        try:
            import yaml  # noqa: F401
        except ImportError:
            self.skipTest("PyYAML not installed; census module not importable")
        sys.path.insert(0, str(pa.ROOT / "mission-control" / "jade_temple" / "devops"))
        try:
            import workflows
        finally:
            sys.path.pop(0)
        self.assertIs(pa.action_ref, workflows.action_ref)



class FrozenBlobTests(unittest.TestCase):
    """--frozen-blob-scan and the rewrite refusal, in a throwaway git repo."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        import subprocess
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        wfd = self.root / ".github" / "workflows"
        wfd.mkdir(parents=True)
        self.frozen = wfd / "frozen.yml"
        self.free = wfd / "free.yml"
        self.frozen.write_bytes(b"jobs:\n  a:\n    steps:\n      - uses: actions/checkout@v4\n")
        self.free.write_bytes(b"jobs:\n  b:\n    steps:\n      - uses: actions/checkout@v4\n")
        oid = next(iter(pa.git_blob_oids([self.frozen], self.root)))
        (self.root / "lineage.json").write_bytes(b'{"frozen.yml": "%s"}\n' % oid.encode())
        subprocess.run(["git", "-C", str(self.root), "add", "-A"], check=True)
        self.old_root, pa.ROOT = pa.ROOT, self.root

    def tearDown(self):
        pa.ROOT = self.old_root
        self.tmp.cleanup()

    def run_main(self, argv, resolve=None):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            rc = pa.main(argv, resolve=resolve)
        return rc, out.getvalue(), err.getvalue()

    def test_blob_oid_matches_git(self):
        import hashlib
        data = self.free.read_bytes()
        want = hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()
        self.assertEqual(list(pa.git_blob_oids([self.free], self.root)), [want])

    def test_scan_lists_only_pinned_file(self):
        frozen = pa.frozen_blobs([self.frozen, self.free], self.root)
        self.assertEqual(list(frozen), [self.frozen])
        self.assertEqual(frozen[self.frozen], ["lineage.json"])

    def test_scan_cli_reports_count(self):
        rc, out, _ = self.run_main(["--frozen-blob-scan", str(self.frozen), str(self.free)])
        self.assertEqual(rc, 0)
        self.assertIn("frozen: 1 of 2", out)

    def test_rewrite_refuses_frozen_without_allow(self):
        before = self.frozen.read_text(encoding="utf-8")
        rc, _, err = self.run_main([str(self.frozen), str(self.free)], resolve=FakeResolver(TABLE))
        self.assertEqual(rc, 2)
        self.assertIn("frozen", err)
        self.assertEqual(self.frozen.read_text(encoding="utf-8"), before)
        self.assertIn("@v4", self.free.read_text(encoding="utf-8"))  # nothing written at all

    def test_rewrite_with_allow_pins(self):
        rc, _, _ = self.run_main([str(self.frozen), "--allow", "frozen.yml"], resolve=FakeResolver(TABLE))
        self.assertEqual(rc, 0)
        self.assertNotIn("checkout@v4\n", self.frozen.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
