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
                                   "safety_attention": True, "changed_fields": ["permissions"]}]}
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
