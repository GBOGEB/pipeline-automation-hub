"""C1-C14 alkane DAG: keys, carbon and formula agree, waves come from the JADE
Kahn owner, a matrix is same-wave peers, a lane is a chain, and a cycle or a
dangling edge stops the run."""
import copy
import importlib.util
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("alkane_dag_under_test", ROOT / "tools" / "alkane_dag.py")
ad = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ad)
DOC = ad.load()
NODES = DOC["nodes"]
WAVES = [["C1_methane"], ["C2_ethane"], ["C3_propane", "C4_butane", "C5_pentane"],
         ["C6_hexane", "C7_heptane", "C8_octane"], ["C9_nonane"],
         ["C10_decane", "C11_undecane"], ["C12_dodecane"], ["C13_tridecane"], ["C14_tetradecane"]]


def by_wave(wave, nodes):
    return [sorted((k for k in wave if wave[k] == w), key=lambda k: nodes[k]["carbon"])
            for w in range(1, max(wave.values(), default=0) + 1)]


def run_cli(doc):
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "dag.json"
        path.write_text(json.dumps(doc), encoding="utf-8", newline="\n")
        out = io.StringIO()
        with redirect_stdout(out):
            code = ad.main(["--dag", str(path)])
    return code, out.getvalue()


class CommittedDag(unittest.TestCase):
    def test_clean(self):
        r = ad.evaluate(NODES)
        self.assertIsNone(r["fatal"])
        self.assertEqual(r["errors"], [])

    def test_waves(self):
        self.assertEqual(by_wave(ad.evaluate(NODES)["wave"], NODES), WAVES)

    def test_critical_path(self):
        self.assertEqual(ad.evaluate(NODES)["critical"],
                         ["C1_methane", "C2_ethane", "C3_propane", "C6_hexane", "C9_nonane",
                          "C10_decane", "C12_dodecane", "C13_tridecane", "C14_tetradecane"])

    def test_waves_and_path_come_from_their_owners(self):
        with mock.patch.object(ad.L, "topo_layers", side_effect=ValueError("owner called")):
            self.assertEqual(ad.evaluate(NODES)["fatal"], "owner called")
        with mock.patch.object(ad.CD, "critical_path", return_value=["owner"]):
            self.assertEqual(ad.evaluate(NODES)["critical"], ["owner"])

    def test_cli_passes(self):
        code, out = run_cli(DOC)
        self.assertEqual(code, 0, out)
        self.assertIn("task mapping: 0/14", out)
        self.assertTrue(out.rstrip().endswith("PASS"))


class Naming(unittest.TestCase):
    def test_formula(self):
        self.assertEqual([ad.formula(n) for n in (1, 2, 14)], ["CH4", "C2H6", "C14H30"])

    def test_misnamed_node(self):
        nodes = copy.deepcopy(NODES)
        nodes["C5_hexane"] = nodes.pop("C5_pentane")
        r = ad.evaluate(nodes)
        self.assertIn("C5_hexane: C5 is pentane", r["errors"])
        self.assertIn("unknown edge endpoint", r["fatal"])  # C8 still names C5_pentane

    def test_carbon_and_formula_must_match_key(self):
        nodes = copy.deepcopy(NODES)
        nodes["C2_ethane"].update(carbon=3, formula="C2H4")
        errs = ad.evaluate(nodes)["errors"]
        self.assertIn("C2_ethane: carbon 3 != 2", errs)
        self.assertIn("C2_ethane: formula C2H4 != C2H6", errs)

    def test_bare_padded_or_extra_keys(self):
        for key, msg in (("C14", "key must be C<n>_<alkane>"),
                         ("C01_methane", "key must be C<n>_<alkane>"),
                         ("C15_pentadecane", "C15 is outside C1-C14")):
            with self.subTest(key=key):
                nodes = copy.deepcopy(NODES)
                nodes[key] = {"carbon": 15, "lane": "LANE-Z", "depends_on": []}
                self.assertTrue(any(msg in e for e in ad.evaluate(nodes)["errors"]))

    def test_missing_node(self):
        nodes = copy.deepcopy(NODES)
        del nodes["C14_tetradecane"]
        self.assertIn("C14: 0 nodes, want 1", ad.evaluate(nodes)["errors"])

    def test_non_numeric_carbon_is_a_diagnostic_not_a_crash(self):
        doc = copy.deepcopy(DOC)
        doc["nodes"]["C6_hexane"]["carbon"] = "6"  # MATRIX-01 peer: sorted beside an int
        doc["nodes"]["C10_decane"]["carbon"] = None  # sorted inside wave 6 by report()
        code, out = run_cli(doc)
        self.assertEqual(code, 1, out)
        self.assertIn("FAIL C6_hexane: carbon '6' != 6", out)
        self.assertIn("FAIL C10_decane: carbon None != 10", out)
        self.assertIn("W6  C10_decane[LANE-D]  C11_undecane[LANE-E]", out)

    def test_empty_graph_reports_missing_nodes(self):
        code, out = run_cli(dict(DOC, nodes={}))
        self.assertEqual(code, 1, out)
        self.assertIn("FAIL C1: 0 nodes, want 1", out)
        self.assertIn("FAIL C14: 0 nodes, want 1", out)


class Lanes(unittest.TestCase):
    def test_pasted_1_2_matrices_are_rejected(self):
        nodes = copy.deepcopy(NODES)
        for k, change in DOC["lane_changes_from_1_2"].items():
            nodes[k]["lane"] = change["was"]
        errs = ad.evaluate(nodes)["errors"]
        self.assertIn("MATRIX-02: only C9_nonane; a matrix needs >= 2 peers", errs)
        self.assertIn("MATRIX-03: C12_dodecane, C13_tridecane sit in waves [7, 8]; "
                      "a matrix runs in one wave", errs)
        self.assertIn("MATRIX-03: members consume different inputs", errs)

    def test_lane_must_not_serialise_parallel_work(self):
        nodes = copy.deepcopy(NODES)
        nodes["C4_butane"]["lane"] = "LANE-A"
        self.assertIn("LANE-A: C4_butane does not depend on C3_propane; parallel work forced serial",
                      ad.evaluate(nodes)["errors"])

    def test_lane_id_format(self):
        nodes = copy.deepcopy(NODES)
        nodes["C10_decane"]["lane"] = "lane d"
        self.assertIn("C10_decane: lane 'lane d' is not LANE-<id> or MATRIX-<nn>",
                      ad.evaluate(nodes)["errors"])


class Fatal(unittest.TestCase):
    def test_cycle_stops_the_run(self):
        doc = copy.deepcopy(DOC)
        doc["nodes"]["C4_butane"]["depends_on"].append("C7_heptane")
        code, out = run_cli(doc)
        self.assertEqual(code, 2)
        self.assertIn("FATAL cycle", out)

    def test_wrong_schema_is_refused(self):
        doc = dict(DOC, schema="jade.temple.alkane-dag.v0")
        with self.assertRaisesRegex(ValueError, "schema"):
            run_cli(doc)


if __name__ == "__main__":
    unittest.main()
