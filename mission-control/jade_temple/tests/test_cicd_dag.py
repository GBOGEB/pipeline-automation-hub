"""CI/CD DAG + SIPOC: OIDs are real git blob ids, layering is a DAG anchored by
SIPOC, UNKNOWN is never PASS, colour precedence keeps Code Purple and root red
visible, and the committed outputs are byte-identical to a rebuild."""
import copy
import importlib.util
import io
import json
import re
import shutil
import subprocess
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HUB = ROOT.parents[1]


def _load(name, rel):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


cd = _load("cicd_dag_under_test", "tools/cicd_dag.py")
page = _load("build_cicd_dag_under_test", "site/build_cicd_dag.py")
MODEL = cd.project(ROOT)
SCOPES = {s["scope"]: s for s in MODEL["scopes"]}


def n(nid, kind):
    return {"id": nid, "kind": kind}


def e(a, b, t="FLOW"):
    return {"from": a, "to": b, "type": t}


class Identity(unittest.TestCase):
    def test_blob_oid_matches_git_reference_values(self):
        self.assertEqual(cd.git_blob_oid(b""), "e69de29bb2d1d6434b8b29ae775ad8c2e48c5391")
        self.assertEqual(cd.git_blob_oid(b"hello\n"), "ce013625030ba8dba906f756967f9e9ca394464a")

    def test_crlf_folds_for_text_but_not_binary(self):
        self.assertEqual(cd.git_blob_oid(b"hello\r\n"), cd.git_blob_oid(b"hello\n"))
        self.assertNotEqual(cd.git_blob_oid(b"\0hello\r\n"), cd.git_blob_oid(b"\0hello\n"))

    @unittest.skipUnless(shutil.which("git"), "git not available")
    def test_bound_oids_equal_git_head_objects(self):
        checked = 0
        for obj in MODEL["objects"]:
            if obj["id"] == "OBJ.CICD_DAG":
                continue  # the tool under change may be ahead of HEAD
            dirty = subprocess.run(["git", "status", "--porcelain", "--", obj["path"]],
                                   cwd=HUB, capture_output=True, text=True)
            head = subprocess.run(["git", "rev-parse", f"HEAD:{obj['path']}"],
                                  cwd=HUB, capture_output=True, text=True)
            if dirty.returncode or dirty.stdout.strip() or head.returncode:
                continue
            self.assertEqual(obj["oid"], head.stdout.strip(), obj["path"])
            checked += 1
        self.assertGreaterEqual(checked, 10)

    def test_bind_objects_fails_closed_on_missing_file_or_symbol(self):
        with tempfile.TemporaryDirectory() as tmp:
            t = Path(tmp)
            (t / "a.py").write_text("def real():\n    pass\n", encoding="utf-8")
            ok = cd.bind_objects(t, [{"id": "X", "path": "a.py", "symbol": "real"}])
            self.assertRegex(ok["X"]["oid"], r"^[0-9a-f]{40}$")
            with self.assertRaisesRegex(ValueError, "no def ghost"):
                cd.bind_objects(t, [{"id": "X", "path": "a.py", "symbol": "ghost"}])
            with self.assertRaisesRegex(ValueError, "missing"):
                cd.bind_objects(t, [{"id": "Y", "path": "nope.py"}])

    def test_external_paths_are_never_given_an_oid(self):
        b = cd.path_binding(HUB, "GBOGEB/gg_MATH", "requirements-release.txt")
        self.assertEqual((b["oid"], b["status"]), (None, "EXTERNAL_UNOBSERVED"))
        b = cd.path_binding(HUB, cd.HUB_REPO, "no/such/file.html")
        self.assertEqual((b["oid"], b["status"]), (None, "NOT_IN_CHECKOUT"))

    def test_sha_ref_accepts_only_full_commit_or_sha256(self):
        self.assertEqual(cd.sha_ref("x", "abc"), [])
        self.assertEqual(cd.sha_ref("x", None), [])
        self.assertEqual(cd.sha_ref("x", "a" * 40)[0]["kind"], "commit")
        self.assertEqual(cd.sha_ref("x", "b" * 64)[0]["kind"], "sha256")


class GraphRules(unittest.TestCase):
    def test_layering_anchors_sipoc_and_ignores_crosswalk_and_temporal(self):
        nodes = [n("s", "S"), n("i", "I"), n("p", "P"), n("q", "P"), n("o", "O"), n("c", "C")]
        edges = [e("s", "i"), e("i", "p"), e("p", "q", "PREREQ"), e("q", "o"), e("o", "c"),
                 e("q", "i", "TEMPORAL"), e("s", "q", "CROSSWALK")]
        layer = cd.layer_nodes(nodes, edges)
        self.assertEqual([layer[x] for x in "sipqoc"], [0, 1, 2, 3, 4, 5])

    def test_layering_rejects_cycles(self):
        with self.assertRaisesRegex(ValueError, "cycle"):
            cd.layer_nodes([n("a", "P"), n("b", "P")], [e("a", "b"), e("b", "a")])

    def test_critical_path_on_declared_gate_dag(self):
        pol = json.loads((ROOT / "data/ROLLING5_POLICY.json").read_text(encoding="utf-8"))
        self.assertEqual(cd.critical_path(pol["gate_prerequisites"]),
                         ["H01", "H02", "H04", "H05", "H10", "H12"])

    def test_frontier_treats_unknown_as_not_pass(self):
        pre = {"A": [], "B": ["A"], "C": ["B"]}
        f = cd.gate_frontier({"A": "PASS", "B": "UNKNOWN", "C": "UNKNOWN"}, pre)
        self.assertEqual(f, {"ready_frontier": ["B"], "blocked_by_ancestor": ["C"]})
        f = cd.gate_frontier({"A": "UNKNOWN"}, pre)
        self.assertEqual(f["ready_frontier"], ["A"])

    def test_colour_precedence(self):
        prec = MODEL and json.loads((ROOT / cd.POLICY).read_text(encoding="utf-8"))["colour_precedence"]
        self.assertEqual(cd.colour_of({"ROOT_RED", "CODE_PURPLE", "FAIL"}, prec, "NEUTRAL"), "CODE_PURPLE")
        self.assertEqual(cd.colour_of({"FAIL", "ROOT_RED"}, prec, "NEUTRAL"), "ROOT_RED")
        self.assertEqual(cd.colour_of({"PASS", "CROSSWALK"}, prec, "NEUTRAL"), "PASS")
        self.assertEqual(cd.colour_of({"CROSSWALK"}, prec, "NEUTRAL"), "CROSSWALK")
        self.assertEqual(cd.colour_of(set(), prec, "NEUTRAL"), "NEUTRAL")

    def test_p_process_loop_drift_fails_closed(self):
        pol = json.loads((ROOT / cd.POLICY).read_text(encoding="utf-8"))
        pol["p_process_loop"] = pol["p_process_loop"][:-1]
        with self.assertRaisesRegex(ValueError, "loop drift"):
            cd.load_sources(ROOT, pol)


class Projection(unittest.TestCase):
    def test_read_only_flags(self):
        self.assertFalse(MODEL["authority_transfer"])
        self.assertFalse(MODEL["release_credit"])
        self.assertEqual(MODEL["merge_admission"], "HOLD")

    def test_scopes_total_five_repos_orchestrators(self):
        names = [s["scope"] for s in MODEL["scopes"]]
        self.assertEqual(names[0], "TOTAL")
        self.assertEqual(names[-1], "ORCHESTRATORS")
        self.assertEqual(len([x for x in names if x.startswith("REPO:")]), 5)

    def test_every_edge_resolves_and_every_node_sits_in_one_sipoc_column(self):
        for s in MODEL["scopes"]:
            ids = {x["id"] for x in s["nodes"]}
            for edge in s["edges"]:
                self.assertIn(edge["from"], ids, s["scope"])
                self.assertIn(edge["to"], ids, s["scope"])
            flat = [i for k in "SIPOC" for i in s["sipoc"][k]]
            self.assertEqual(sorted(flat), sorted(ids), s["scope"])

    def test_oid_bindings_are_40_hex_or_explicitly_unobserved(self):
        for s in MODEL["scopes"]:
            for node in s["nodes"]:
                for b in node["oids"]:
                    if b["oid"] is None:
                        self.assertIn(b["status"], {"EXTERNAL_UNOBSERVED", "NOT_IN_CHECKOUT"})
                    else:
                        self.assertRegex(b["oid"], r"^[0-9a-f]{40}$")

    def test_total_gate_metrics_agree_with_rolling5(self):
        g = SCOPES["TOTAL"]["metrics"]["gates"]
        r5 = json.loads((ROOT / "site/rolling5.json").read_text(encoding="utf-8"))["metrics"]
        self.assertEqual(g["pass"], r5["verified_pass"])
        self.assertEqual(g["total"], r5["gate_denominator"])
        self.assertEqual(g["verified_completion_pct"], r5["verified_completion_pct"])
        self.assertEqual(g["pass"] + len(g["ready_frontier"]) + g["blocked_by_ancestor"], g["total"])
        self.assertGreaterEqual(g["rolled_throughput_yield"], 0)
        self.assertLessEqual(g["rolled_throughput_yield"], 1)

    def test_source_red_and_code_purple_are_visible(self):
        total = {x["id"]: x for x in SCOPES["TOTAL"]["nodes"]}
        core = SCOPES["TOTAL"]["metrics"]["source_red"]["core_focus"]
        self.assertEqual(total[core]["colour"], "ROOT_RED")
        self.assertIn("rolling5.py", total[core]["oids"][0]["path"])
        self.assertEqual(total["P.CODE_PURPLE"]["colour"], "CODE_PURPLE")
        self.assertEqual(total["S.ABACUS"]["colour"], "CODE_PURPLE")

    def test_repo_root_red_is_a_subset_of_source_red(self):
        for s in MODEL["scopes"]:
            if s["scope"].startswith("REPO:"):
                g = s["metrics"]["gates"]
                self.assertTrue(set(g["root_red"]) <= set(g["source_red"]), s["scope"])
                self.assertTrue(g["root_red"], s["scope"])

    def test_temporal_edges_close_the_p_loop_without_a_cycle(self):
        t = [x for x in SCOPES["TOTAL"]["edges"] if x["type"] == "TEMPORAL"]
        self.assertIn(("P.recurse", "P.harvest"), {(x["from"], x["to"]) for x in t})

    def test_orchestrator_hub_receives_most_federation_edges(self):
        repos = SCOPES["ORCHESTRATORS"]["metrics"]["repos"]
        hub = repos[cd.HUB_REPO]["in_degree"]
        self.assertEqual(hub, max(r["in_degree"] for r in repos.values()))


class Outputs(unittest.TestCase):
    def test_tool_check_parity(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            self.assertEqual(cd.main(["--check"]), 0, buf.getvalue())

    def test_page_check_parity(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            self.assertEqual(page.main(["--check"]), 0, buf.getvalue())

    def test_check_detects_drift(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "mission-control" / "jade_temple"
            shutil.copytree(ROOT, root, ignore=shutil.ignore_patterns("qa", "__pycache__", "*.pdf", "*.png"))
            for rel in ("mission-control/qps-triage-ultra/p-process", "mission-control/federation-atlas",
                        ".github/workflows"):
                shutil.copytree(HUB / rel, Path(tmp) / rel,
                                ignore=shutil.ignore_patterns("fonts", "*.pdf", "node_modules"))
            buf = io.StringIO()
            with redirect_stdout(buf):
                self.assertEqual(cd.main(["--check"], root=root), 0, buf.getvalue())
                (root / cd.OUT_CSV).write_text("tampered\n", encoding="utf-8")
                self.assertEqual(cd.main(["--check"], root=root), 1)
            self.assertIn("CICD_DAG_FIRST_RED", buf.getvalue())

    def test_page_is_offline_and_labels_every_lens(self):
        html = (ROOT / page.OUT).read_text(encoding="utf-8")
        self.assertNotRegex(html, r'<script[^>]+src=')
        self.assertEqual(re.findall(r'<link[^>]+href="([^"]+)"', html), ["jade.css"])
        for lens in cd.LENSES:
            self.assertIn(f'data-lens-btn="{lens}"', html)
            self.assertIn(f"l-{lens}", html)

    def test_mermaid_has_one_file_per_scope_and_lens(self):
        for scope in cd.MMD_SCOPES:
            for lens in cd.LENSES:
                text = (ROOT / cd.MMD.format(scope=scope, lens=lens)).read_text(encoding="utf-8")
                self.assertTrue(text.splitlines()[1] == "flowchart LR")
                self.assertIn("classDef root_red", text)

    def test_csv_crosswalk_covers_every_node(self):
        rows = (ROOT / cd.OUT_CSV).read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(rows) - 1, sum(len(s["nodes"]) for s in MODEL["scopes"]))


if __name__ == "__main__":
    unittest.main()
