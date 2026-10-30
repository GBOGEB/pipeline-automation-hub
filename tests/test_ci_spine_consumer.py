"""W4 CI-spine consumer: canonical owner reuse, stale evidence and HTML safety."""
import contextlib
import copy
import hashlib
import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "mission-control/v2/spine_w4/ci_spine_consumer.py"
spec = importlib.util.spec_from_file_location("ci_spine_consumer", SOURCE)
M = importlib.util.module_from_spec(spec)
spec.loader.exec_module(M)
SHA = "a" * 40
HUB = "GBOGEB/pipeline-automation-hub"


def sample():
    index = {"schema": M.SOURCE_SCHEMA, "verdict": "PASS_STATIC_BINDINGS_ONLY",
             "errors": [], "source": {"checkout_sha": SHA, "expected_sha": SHA},
             "assurance": {"merge_admission": "HOLD"}, "anchors": [
                 {"id": "CI-SOURCE", "phase": "SOURCE", "path": ".github/workflows/a.yml",
                  "static_binding": "PASS"}]}
    control = json.loads((ROOT / "mission-control/v2/spine_w4/control_view.json").read_text())
    metrics = {"schema": M.METRICS_SCHEMA, "observed_at_utc": "2026-10-26T11:35:37Z",
               "period": {"since": "2026-10-01", "until": "2026-10-26"},
               "repos": [{"repo": HUB, "head_sha": "b" * 40, "same_pulse": False,
                          "totals": {"job_coverage": 0.34, "p95_job_queue_s": 1836,
                                     "workflow_runs": 16840}}]}
    delta = {"schema": M.DELTA_SCHEMA, "verdict": "DIFFERENCE_REVIEW_REQUIRED", "errors": [],
             "source": {"previous_sha": "b" * 40, "current_sha": SHA},
             "workflow_changes": [{"path": ".github/workflows/check.yml", "change": "MODIFIED",
                                   "safety_attention": True, "changed_fields": ["permissions"]}],
             "authority_changes": []}
    wave = {"schema": M.WAVE_SCHEMA, "max_workers": 3,
            "tasks": [{"id": "CI-N7-A", "stage": "DISCOVER", "lane": "SOURCE"}]}
    return index, control, metrics, delta, wave


class Consumer(unittest.TestCase):
    def test_existing_w4_renderer_and_governance_reused(self):
        i, c, m, d, w = sample()
        page, receipt = M.render(i, c, m, d, w, SHA)
        self.assertIn("W4", page)
        self.assertIn("<svg", page)
        self.assertIn("CI source evidence", page)
        self.assertIn("JADE DAG / SIPOC", page)
        self.assertIn("HISTORICAL_UNMATCHED_SOURCE", page)
        self.assertIn("1836", page)  # exact source-owned historical value, not recomputed
        self.assertIn("DECLARED_ONLY_NO_DISPATCH", page)
        self.assertEqual(receipt["admission"], "HOLD")
        self.assertEqual(receipt["runtime_nonregression"], "NOT_PROVEN")
        self.assertFalse(receipt["dispatch_authorized"])

    def test_html_escapes_all_external_values(self):
        i, c, m, d, w = sample()
        injection = "<img src=x onerror=alert(1)>"
        i["anchors"][0]["id"] = injection
        d["workflow_changes"][0]["path"] = injection
        w["tasks"][0]["lane"] = injection
        page, _ = M.render(i, c, m, d, w)
        self.assertNotIn(injection, page)
        self.assertIn("&lt;img src=x onerror=alert(1)&gt;", page)

    def test_missing_metric_and_delta_are_explicit_unknown(self):
        i, c, _, _, _ = sample()
        page, receipt = M.render(i, c)
        self.assertIn("NOT_SUPPLIED", page)
        self.assertIsNone(receipt["actions_metrics_observed_at"])
        self.assertEqual(receipt["delta_binding"], "NOT_SUPPLIED")

    def test_mismatched_delta_is_not_joined(self):
        i, c, m, d, w = sample()
        d["source"]["current_sha"] = "c" * 40
        page, receipt = M.render(i, c, m, d, w)
        self.assertEqual(receipt["delta_binding"], "STALE_DIFFERENT_SOURCE_NOT_JOINED")
        self.assertIn("STALE_DIFFERENT_SOURCE_NOT_JOINED", page)

    def test_authority_only_rebind_is_visible_and_never_promotes(self):
        i, c, m, d, w = sample()
        d["workflow_changes"] = []
        d["authority_changes"] = [{
            "id": "CI-FPC", "status": "AUTHORITY_REVIEW_REQUIRED",
            "before": {"path": ".github/workflows/old-fpc.yml", "phase": "CONTROL"},
            "after": {"path": ".github/workflows/new-fpc.yml", "phase": "CONTROL"},
        }]
        page, receipt = M.render(i, c, m, d, w, SHA)
        self.assertIn("Authority-binding changes", page)
        self.assertIn("AUTHORITY_REVIEW_REQUIRED", page)
        self.assertIn("old-fpc.yml", page)
        self.assertIn("new-fpc.yml", page)
        self.assertEqual(receipt["authority_changes_count"], 1)
        self.assertEqual(receipt["delta_binding"], "SAME_CURRENT_SOURCE_REVIEW_ONLY")
        self.assertEqual(receipt["admission"], "HOLD")
        self.assertFalse(receipt["dispatch_authorized"])

    def test_authority_rebind_stale_source_is_explicitly_not_joined(self):
        i, c, m, d, w = sample()
        d["workflow_changes"] = []
        d["authority_changes"] = [{
            "id": "CI-SOURCE", "status": "AUTHORITY_REVIEW_REQUIRED",
            "before": None, "after": {"path": ".github/workflows/historical.yml"},
        }]
        d["source"]["current_sha"] = "c" * 40
        page, receipt = M.render(i, c, m, d, w)
        self.assertEqual(receipt["delta_binding"], "STALE_DIFFERENT_SOURCE_NOT_JOINED")
        self.assertIn("historical or mismatched sources are not joined", page)
        self.assertIn("historical.yml", page)

    def test_malformed_authority_records_and_false_no_delta_fail_closed(self):
        i, c, m, d, w = sample()
        bad = [None, {}, "bad", [None], [{"id": "a"}],
               [{"id": "a", "status": "PASS", "before": {}, "after": {}}],
               [{"id": "a", "status": "AUTHORITY_REVIEW_REQUIRED",
                 "before": [], "after": {}}],
               [{"id": "a", "status": "AUTHORITY_REVIEW_REQUIRED",
                 "before": None, "after": None}],
               [{"id": "a", "status": "AUTHORITY_REVIEW_REQUIRED",
                 "before": {"path": ".github/workflows/same.yml"}, "after": {"path": ".github/workflows/same.yml"}}],
               [{"id": "a", "status": "AUTHORITY_REVIEW_REQUIRED",
                 "before": None, "after": {}}],
               [{"id": "a", "status": "AUTHORITY_REVIEW_REQUIRED",
                 "before": None, "after": {"path": ""}}]]
        for value in bad:
            with self.subTest(value=value):
                trial = copy.deepcopy(d)
                trial["authority_changes"] = value
                with self.assertRaisesRegex(ValueError, "CI_SPINE_VIEW_HOLD"):
                    M.render(i, c, m, trial, w)
        d["authority_changes"] = [{
            "id": "a", "status": "AUTHORITY_REVIEW_REQUIRED",
            "before": None, "after": {"path": ".github/workflows/new.yml"},
        }]
        d["verdict"] = "NO_OBSERVED_SOURCE_DELTA"
        with self.assertRaisesRegex(ValueError, "contradictory delta verdict"):
            M.render(i, c, m, d, w)

    def test_authority_binding_payload_escapes_html(self):
        i, c, m, d, w = sample()
        injection = "<img src=x onerror=alert(1)>"
        d["authority_changes"] = [{
            "id": injection, "status": "AUTHORITY_REVIEW_REQUIRED",
            "before": {"path": ".github/workflows/old.yml", "purpose": injection},
            "after": {"path": ".github/workflows/safe.yml"},
        }]
        page, receipt = M.render(i, c, m, d, w)
        self.assertNotIn(injection, page)
        self.assertIn("&lt;img src=x onerror=alert(1)&gt;", page)
        self.assertEqual(receipt["authority_changes_count"], 1)

    def test_only_canonical_top_level_workflow_yaml_paths_are_accepted(self):
        valid = (".github/workflows/canonical.yml", ".github/workflows/fpc.yaml")
        for path in valid:
            with self.subTest(valid_path=path):
                self.assertTrue(M.canonical_workflow_binding(path))
        invalid = (" ", "unrelated.txt", ".github/workflows/ ",
                   ".github/workflows/ .yaml", ".github/workflows/a.yml ",
                   ".github/workflows/sub/a.yml", ".github/workflows//a.yml",
                   ".github/workflows/a\\b.yml", ".github/workflows/a\\\\b.yml",
                   ".github/workflows/../a.yml", ".github/workflows/a.json",
                   ".github\\\\workflows\\\\a.yml")
        for path in invalid:
            with self.subTest(invalid_path=path):
                self.assertFalse(M.canonical_workflow_binding(path))
                i, c, m, d, w = sample()
                d["authority_changes"] = [{
                    "id": "CI-FAIL", "status": "AUTHORITY_REVIEW_REQUIRED",
                    "before": None, "after": {"path": path},
                }]
                with self.assertRaisesRegex(ValueError, "CI_SPINE_VIEW_HOLD"):
                    M.render(i, c, m, d, w)

    def test_static_index_never_grants_admission(self):
        i, c, m, d, w = sample()
        i["assurance"]["merge_admission"] = "PASS"
        with self.assertRaisesRegex(ValueError, "CI_SPINE_VIEW_HOLD"):
            M.render(i, c, m, d, w)
        i["assurance"]["merge_admission"] = "HOLD"
        i["errors"] = ["first red"]
        with self.assertRaisesRegex(ValueError, "CI_SPINE_VIEW_HOLD"):
            M.render(i, c, m, d, w)

    def test_wrong_source_or_corrupted_w4_fails_closed(self):
        i, c, m, d, w = sample()
        with self.assertRaisesRegex(ValueError, "wrong expected source"):
            M.render(i, c, m, d, w, "c" * 40)
        c["merge_admission"] = "PASS"
        with self.assertRaises(ValueError):
            M.render(i, c, m, d, w)

    def test_malformed_canonical_metric_or_delta_rejected(self):
        i, c, m, d, w = sample()
        m["schema"] = "untrusted"
        with self.assertRaises(ValueError):
            M.render(i, c, m, d, w)
        m["schema"] = M.METRICS_SCHEMA
        d["verdict"] = "CI_SPINE_DELTA_FIRST_RED"
        with self.assertRaises(ValueError):
            M.render(i, c, m, d, w)

    def test_cli_manifest_hashes_exact_bytes_and_holds(self):
        i, c, m, d, w = sample()
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            data = {"index": i, "control": c, "metrics": m, "delta": d, "wave": w}
            for name, doc in data.items():
                (root / f"{name}.json").write_text(json.dumps(doc, sort_keys=True), encoding="utf-8")
            output = root / "ci-view.html"
            argv = [arg for name in data for arg in ("--" + name, str(root / f"{name}.json"))]
            argv += ["--expected-head", SHA, "--out", str(output)]
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(M.main(argv), 0)
            manifest = json.loads((root / "ci-view.manifest.json").read_text())
            self.assertEqual(manifest["html_sha256"], hashlib.sha256(output.read_bytes()).hexdigest())
            self.assertEqual(manifest["input_sha256"]["metrics"],
                             hashlib.sha256((root / "metrics.json").read_bytes()).hexdigest())
            self.assertEqual(manifest["admission"], "HOLD")
            self.assertIn("HISTORICAL_UNMATCHED_SOURCE", output.read_text())


if __name__ == "__main__":
    unittest.main()
