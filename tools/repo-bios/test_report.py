import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

spec = importlib.util.spec_from_file_location("bios_report", Path(__file__).with_name("report.py"))
report = importlib.util.module_from_spec(spec)
spec.loader.exec_module(report)


class ReportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "repo"
        self.root.mkdir()
        self.git("init", "-q")
        self.git("config", "user.email", "fixture@example.invalid")
        self.git("config", "user.name", "Fixture")
        self.write("main.py", "# comment\n\nprint('ok')\n")
        self.write("tests/test_main.py", "assert True\n")
        self.write("analysis.R", "x <- 1\n")
        self.write("docs/ADR-001.md", "# Proposed decision\n")
        self.write("checks/aht-check.py", "print('candidate')\n")
        self.workflow("jobs:\n  build:\n    runs-on: ubuntu-latest\n  verify:\n    needs: build\n    runs-on: ubuntu-latest\n")
        self.commit()

    def tearDown(self):
        self.temp.cleanup()

    def git(self, *args):
        return subprocess.run(["git", "-C", str(self.root), *args], check=True,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout

    def write(self, path, text):
        p = self.root / path
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")

    def workflow(self, body):
        self.write(".github/workflows/ci.yml", body)

    def commit(self):
        self.git("add", ".")
        self.git("commit", "-qm", "fixture")

    def read(self, entries=()):
        return report.snapshot("owner/repo", self.root, entries)

    def test_source_ignores_dirty_and_untracked_content(self):
        before = self.read(["main.py"])
        self.write("main.py", "changed\n" * 20)
        self.write("untracked.py", "more\n")
        after = self.read(["main.py"])
        self.assertEqual(before["languages"], after["languages"])
        self.assertEqual(after["selected_pipeline_entry_loc"], 3)
        self.assertEqual(after["languages"]["R"]["physical_loc"], 1)

    def test_kahn_and_consumers_reuse_owner(self):
        wf = self.read()["workflows"][0]
        self.assertEqual(wf["layers"], [["build"], ["verify"]])
        self.assertEqual(wf["jobs"][0]["downstream"], ["verify"])
        self.assertTrue(all(j["runtime_state"] == "UNKNOWN" for j in wf["jobs"]))

    def test_cycle_not_reported_ready(self):
        self.workflow("jobs:\n  a: {needs: b}\n  b: {needs: a}\n")
        self.commit()
        wf = self.read()["workflows"][0]
        self.assertIsNone(wf["layers"])
        self.assertIn("cycle", wf["graph_error"])

    def test_missing_prerequisite_not_reported_ready(self):
        self.workflow("jobs:\n  a: {needs: missing}\n")
        self.commit()
        self.assertIn("unknown edge", self.read()["workflows"][0]["graph_error"])

    def test_malformed_yaml_is_diagnostic(self):
        self.workflow("jobs: [broken\n")
        self.commit()
        self.assertTrue(self.read()["workflows"][0]["parse_error"])

    def test_nested_legacy_not_active_workflow(self):
        self.write(".github/workflows/legacy/old.yml", "jobs: {}\n")
        self.commit()
        self.assertEqual(self.read()["workflow_count"], 1)

    def test_symlink_not_followed(self):
        (self.root / "external.py").symlink_to("/etc/passwd")
        self.commit()
        snap = self.read()
        self.assertEqual(snap["counts"]["symlinks"], 1)
        self.assertEqual(snap["languages"]["Python"]["files"], 3)

    def test_unknown_pipeline_and_native_metrics(self):
        snap = self.read()
        self.assertIsNone(snap["selected_pipeline_entry_loc"])
        self.assertEqual(snap["runtime_kpis"]["state"], "UNKNOWN")
        self.assertEqual(snap["adr_candidates"][0]["decision_status"], "UNKNOWN_PATH_CANDIDATE")
        self.assertEqual(len(snap["aht_candidates"]), 1)

    def test_missing_pipeline_entry_fails(self):
        with self.assertRaises(ValueError):
            self.read(["absent.py"])

    def test_as_is_kpi_preserves_unknowns_and_history(self):
        original = {"as_of": "2020-01-01", "coverage": None, "failures": 7}
        self.write("metrics.json", json.dumps(original))
        self.commit()
        snap = report.snapshot("owner/repo", self.root, metric_paths=["metrics.json"])
        self.assertEqual(snap["as_is_metrics"][0]["document"], original)
        self.assertEqual(snap["runtime_kpis"]["state"], "UNKNOWN")

    def test_html_cannot_inject_from_source(self):
        snap = self.read()
        snap["workflows"][0]["path"] = "</script><script>alert(1)</script>"
        page = report.webpage({"repositories": [snap]})
        self.assertNotIn("</script><script>alert", page)
        self.assertIn("\\u003c/script>", page)

    def test_cli_outputs_and_hashes(self):
        out = Path(self.temp.name) / "report"
        self.assertEqual(report.main(["--repo", f"owner/repo={self.root}", "--out", str(out)]), 0)
        self.assertEqual(len((out / "SHA256SUMS").read_text().splitlines()), 3)
        self.assertEqual(json.loads((out / "report.json").read_text())["repositories"][0]["source_sha"], self.read()["source_sha"])

    def test_refuses_output_inside_source(self):
        with self.assertRaises(SystemExit):
            report.main(["--repo", f"owner/repo={self.root}", "--out", str(self.root / "report")])


if __name__ == "__main__":
    unittest.main()
