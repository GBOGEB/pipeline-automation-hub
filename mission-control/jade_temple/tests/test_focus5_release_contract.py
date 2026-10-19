"""JADE N+7 Focus5 fixed-denominator dashboard and authority negative tests."""
from __future__ import annotations
import copy
import importlib.util
import json
import unittest
from pathlib import Path

JADE = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "focus5_builder", JADE / "site/build_focus5.py"
)
builder = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(builder)
SOURCE = JADE / "data/FOCUS5_POINT_RELEASE_NPLUS7.json"
TEMPLATE = JADE / "site/focus5_template.html"


class Focus5ReleaseContract(unittest.TestCase):
    def setUp(self):
        self.data = json.loads(SOURCE.read_text(encoding="utf-8"))

    def test_60_gates_15_qualified_and_latest_heads(self):
        builder.validate(self.data)
        self.assertEqual(self.data["metrics"]["passed"], 15)
        self.assertEqual(self.data["metrics"]["required_gate_total"], 60)
        self.assertEqual({x["rank"] for x in self.data["rows"]}, {2, 4, 5, 8, 16})

    def test_missing_gate_cannot_improve_percentage(self):
        bad = copy.deepcopy(self.data)
        bad["rows"][0]["gates"].pop()
        with self.assertRaises(AssertionError):
            builder.validate(bad)

    def test_unknown_to_pass_requires_consistent_native_receipt_update(self):
        bad = copy.deepcopy(self.data)
        pending = next(g for g in bad["rows"][0]["gates"]
                       if g["status"] == "UNKNOWN")
        pending["status"] = "PASS"
        with self.assertRaises(AssertionError):
            builder.validate(bad)

    def test_false_governed_merge_cannot_be_projected(self):
        bad = copy.deepcopy(self.data)
        bad["workflow"]["merge_admission"] = "PASS"
        with self.assertRaises(AssertionError):
            builder.validate(bad)

    def test_cross_repo_graph_is_not_causal_root_closure(self):
        bad = copy.deepcopy(self.data)
        bad["edges"][0]["causal_root_proof"] = True
        with self.assertRaises(AssertionError):
            builder.validate(bad)

    def test_unknown_root_counts_remain_null(self):
        bad = copy.deepcopy(self.data)
        bad["metrics"]["canonical_root_closed"] = 0
        with self.assertRaises(AssertionError):
            builder.validate(bad)

    def test_generator_output_is_byte_deterministic(self):
        expected = builder.render(SOURCE.read_text(encoding="utf-8"),
                                  TEMPLATE.read_text(encoding="utf-8"))
        actual = (JADE / "site/focus5.html").read_text(encoding="utf-8")
        self.assertEqual(expected, actual)

    def test_excel_ready_burndown_has_exactly_sixty_atoms(self):
        source = SOURCE.read_text(encoding="utf-8")
        expected = builder.make_csv(source)
        actual = (JADE / "site/focus5_burndown.csv").read_text(encoding="utf-8")
        self.assertEqual(expected, actual)
        self.assertEqual(actual.count("\n"), 61)
        self.assertIn("H12", actual)
        self.assertIn("GBOGEB/cryoplant-project", actual)

    def test_embedded_script_termination_fails_closed(self):
        source = SOURCE.read_text(encoding="utf-8")
        unsafe = source.replace('"name": "', '"name": "</script>', 1)
        with self.assertRaises((ValueError, json.JSONDecodeError)):
            builder.render(unsafe, TEMPLATE.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
