"""Read-only CI spine adapter: determinism, safety, scope and negative controls."""
import fnmatch
import importlib.util
import json
import re
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("ci_spine_index", ROOT / "scripts/ci_spine_index.py")
M = importlib.util.module_from_spec(spec)
spec.loader.exec_module(M)


class StubWorkflows:
    @staticmethod
    def parse(text, path="", repo=""):
        from hashlib import sha256
        return {"path": path, "oid": "jade:wf:" + repo + ":" + path, "name": path,
                "jobs": [{"id": "a", "oid": path + "#a", "needs": [], "layer": 0,
                          "def_sha256": sha256(text.encode()).hexdigest()}],
                "triggers": ["pull_request"], "dag": {"layers": [["a"]], "edges": [],
                "cycle": "CYCLE" in text, "dangling": []},
                "parse_error": "YAML" if "BROKEN" in text else None}


class StubActions:
    @staticmethod
    def wf_class(name, path):
        return "TEST_QA"


class Contract(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / ".github/workflows").mkdir(parents=True)
        (self.root / "canonical.py").write_text("x=1", encoding="utf-8")
        (self.root / "AGENTS.md").write_text("canonical.py", encoding="utf-8")
        (self.root / ".github/workflows/a.yml").write_text("on: pull_request\njobs: {}\n", encoding="utf-8")
        self.c = {"schema": M.SCHEMA, "coverage_scope": "anchors_only",
                  "anchors": [{"id": "CI-TEST-A", "phase": "TEST",
                               "path": ".github/workflows/a.yml", "purpose": "test"}],
                  "metric_owner_bindings": {"test": "canonical.py"},
                  "conceptual_edges": []}

    def build(self):
        return M.build(self.root, self.c, owners=(StubWorkflows, StubActions))

    def test_positive_is_static_only(self):
        r = self.build()
        self.assertEqual(r["verdict"], "PASS_STATIC_BINDINGS_ONLY")
        self.assertEqual(r["assurance"]["merge_admission"], "HOLD")
        self.assertEqual(r["source"]["live_run_census"], "NOT_FETCHED")
        self.assertEqual(r["counts"]["workflow_files"], 1)
        self.assertEqual(r["anchors"][0]["static_binding"], "PASS")

    def test_duplicate_anchor_fails_closed(self):
        self.c["anchors"].append(dict(self.c["anchors"][0]))
        self.assertIn("duplicate anchor id", " ".join(self.build()["errors"]))

    def test_missing_and_escape_are_rejected(self):
        self.c["anchors"][0]["path"] = "../private.yml"
        self.assertIn("unsafe workflow", " ".join(self.build()["errors"]))
        self.c["anchors"][0]["path"] = ".github/workflows/absent.yml"
        self.assertIn("missing canonical", " ".join(self.build()["errors"]))

    def test_unmapped_drift_is_advisory_not_false_green(self):
        (self.root / ".github/workflows/new.yml").write_text("BROKEN", encoding="utf-8")
        r = self.build()
        self.assertEqual(r["counts"]["unbound_workflows"], 1)
        self.assertEqual(r["counts"]["structural_advisories"], 1)
        self.assertEqual(r["verdict"], "PASS_STATIC_BINDINGS_ONLY")

    def test_bound_bad_dag_fails(self):
        (self.root / ".github/workflows/a.yml").write_text("CYCLE", encoding="utf-8")
        self.assertIn("malformed canonical workflow", " ".join(self.build()["errors"]))

    def test_unknown_owner_or_backward_edge_fails(self):
        self.c["metric_owner_bindings"]["test"] = "stray.py"
        self.assertIn("invalid metric owner", " ".join(self.build()["errors"]))
        self.c["metric_owner_bindings"]["test"] = "canonical.py"
        self.c["anchors"].append({"id": "CI-SOURCE-B", "phase": "SOURCE",
                                  "path": ".github/workflows/a.yml"})
        self.c["conceptual_edges"] = [["CI-TEST-A", "CI-SOURCE-B"]]
        self.assertIn("nonprogressive", " ".join(self.build()["errors"]))

    def test_exact_head_mismatch_first_red(self):
        r = M.build(self.root, self.c, "a" * 40, owners=(StubWorkflows, StubActions))
        self.assertIn("exact-head mismatch", " ".join(r["errors"]))

    def test_qa_filter_covers_all_anchor_workflows_and_imported_owners(self):
        qa = (ROOT / ".github/workflows/ci-spine-governed-qa.yml").read_text(encoding="utf-8")
        self.assertIn("  push:", qa)
        pr = qa.split("  pull_request:", 1)[1].split("  push:", 1)[0]
        push = qa.split("  push:", 1)[1].split("  workflow_dispatch:", 1)[0]
        contract = json.loads((ROOT / "governance/ci_spine/CI_SPINE_BINDINGS_V1.json").read_text())
        anchors = contract["anchors"]
        owners = contract["metric_owner_bindings"]
        self.assertIsInstance(owners, dict)
        self.assertTrue(owners)
        # Bind to the current contract, not a fixed tuple. A newly declared
        # canonical owner must appear in both trigger sets or this fails.
        required = {".github/workflows/**", "AGENTS.md", contract["workflow_parser_owner"],
                    *owners.values()}
        self.assertTrue(all(isinstance(path, str) and path for path in required))
        for block in (pr, push):
            patterns = re.findall(r"^\s+- '([^']+)'$", block, re.M)
            self.assertIn(".github/workflows/**", patterns)
            for path in sorted(required):
                self.assertTrue(any(fnmatch.fnmatchcase(path, pattern) for pattern in patterns),
                                "uncovered canonical source: " + path)
            for anchor in anchors:
                self.assertTrue(any(fnmatch.fnmatchcase(anchor["path"], pattern)
                                    for pattern in patterns), anchor["path"])


    def test_injected_identity_cannot_escape(self):
        for p in ("/etc/passwd", "../escape.yml", ".github/workflows/../../x.yml",
                  ".github\\workflows\\a.yml"):
            self.assertIsNone(M._safe(self.root, p))


if __name__ == "__main__":
    unittest.main()
