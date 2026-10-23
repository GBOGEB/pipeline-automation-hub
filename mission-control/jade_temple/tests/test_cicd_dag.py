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
POLICY = json.loads((ROOT / cd.POLICY).read_text(encoding="utf-8"))
CENSUS = cd.load_census(ROOT, POLICY)


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
        b = cd.path_binding(HUB, "GBOGEB/gg_MATH", "no/such/file.py", CENSUS)
        self.assertEqual((b["oid"], b["status"]), (None, "EXTERNAL_UNOBSERVED"))
        b = cd.path_binding(HUB, cd.HUB_REPO, "no/such/file.html")
        self.assertEqual((b["oid"], b["status"]), (None, "NOT_IN_CHECKOUT"))

    def test_external_paths_bind_to_census_blob_at_census_head(self):
        crow = CENSUS["repos"]["GBOGEB/cryoplant-project"]
        wf = crow["workflows"][0]
        b = cd.path_binding(HUB, crow["repo"], wf["path"], CENSUS)
        self.assertEqual(b["status"], "BOUND_AT_CENSUS_HEAD")
        self.assertEqual((b["oid"], b["at"], b["jade_oid"]), (wf["blob_oid"], crow["head_sha"], wf["oid"]))
        run = cd.census_workflow(CENSUS, crow["repo"], wf["name"])
        self.assertEqual(run["oid"], CENSUS["index"][crow["repo"]]["paths"][
            CENSUS["index"][crow["repo"]]["names"][wf["name"]]][0])

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
                    if b["status"] == "BOUND_AT_CENSUS_HEAD" and b["at"] is not None:
                        self.assertRegex(b["at"], r"^[0-9a-f]{40}$")

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


class Census(unittest.TestCase):
    def test_census_pin_drift_fails_closed(self):
        pol = copy.deepcopy(POLICY)
        pol["devops_census"]["digest_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "digest/schema drift"):
            cd.load_census(ROOT, pol)

    def test_objects_must_reference_the_pinned_census(self):
        with tempfile.TemporaryDirectory() as tmp:
            t = Path(tmp)
            cfg = POLICY["devops_census"]
            (t / "data").mkdir()
            shutil.copy(ROOT / cfg["census"], t / cfg["census"])
            obj = json.loads((ROOT / cfg["objects"]).read_text(encoding="utf-8"))
            obj["census_digest_sha256"] = "f" * 64
            (t / cfg["objects"]).write_text(json.dumps(obj), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "not bound to the pinned census"):
                cd.load_census(t, POLICY)

    def test_no_census_policy_means_no_census(self):
        self.assertIsNone(cd.load_census(ROOT, {k: v for k, v in POLICY.items() if k != "devops_census"}))
        self.assertIsNone(cd.census_binding(None, "GBOGEB/x", "a.py"))

    def test_lifecycle_chain_is_acyclic_with_one_feedback_edge(self):
        for name in ["TOTAL"] + [s for s in SCOPES if s.startswith("REPO:")]:
            s = SCOPES[name]
            life = [x for x in s["nodes"] if x["type"] == "LIFECYCLE"]
            self.assertEqual(len(life), 10, name)
            fb = [e for e in s["edges"] if e["from"] == "L.S9_CONTROL" and e["to"] == "L.S0_PLAN"]
            self.assertEqual([e["type"] for e in fb], ["TEMPORAL"], name)
            xs = {(e["from"], e["to"]) for e in s["edges"] if e["type"] == "CROSSWALK"}
            self.assertIn(("L.S3_TEST", "H05"), xs, name)
        self.assertIn(("L.S9_CONTROL", "P.root"),
                      {(e["from"], e["to"]) for e in SCOPES["TOTAL"]["edges"]})

    def test_stage_status_never_promotes_unknown(self):
        self.assertEqual(cd.stage_status({"probes": 5, "pass": 5}), "PASS")
        self.assertEqual(cd.stage_status({"probes": 5, "pass": 4,
                                          "next_blocker": {"state": "UNKNOWN"}}), "UNKNOWN")
        self.assertEqual(cd.stage_status({"probes": 5, "pass": 1,
                                          "next_blocker": {"state": "FAIL"}}), "FAIL")
        self.assertEqual(cd.stage_status({"probes": 0, "pass": 0}), "UNKNOWN")

    def test_fleet_metrics_and_matrix_follow_the_census(self):
        dv = SCOPES["TOTAL"]["metrics"]["devops"]
        t = CENSUS["census"]["fleet"]["totals"]
        self.assertEqual(dv["deploy_contract_core"], f"{t['wf_deploy_contract_core']}/{t['wf_deploy']}")
        self.assertEqual(dv["workflows"], t["wf_workflows"])
        lc = MODEL["lifecycle"]
        self.assertEqual(len(lc["repos"]), len(CENSUS["census"]["repos"]))
        drift = sorted(cd._short(r["repo"]) for r in lc["repos"] if r["sha_drift"])
        self.assertEqual(drift, dv["census_sha_drift"])

    def test_repo_census_nodes_and_drift_flag(self):
        for name, s in SCOPES.items():
            if not name.startswith("REPO:"):
                continue
            ids = {x["id"]: x for x in s["nodes"]}
            for nid in ("I.CENSUS_HEAD", "I.TESTS", "O.DEPLOY"):
                self.assertIn(nid, ids, name)
            head = ids["I.CENSUS_HEAD"]
            self.assertEqual(head["metrics"]["sha_drift"], s["metrics"]["devops"]["sha_drift"])
            if not s["metrics"]["devops"]["deploy_jobs"]:
                self.assertEqual(ids["O.DEPLOY"]["status"], "UNKNOWN")

    def test_hub_objects_adopt_jade_oid_only_on_identical_blob(self):
        seen = 0
        for s in MODEL["scopes"]:
            for node in s["nodes"]:
                for b in node["oids"]:
                    if b["status"] == "BOUND" and b["jade_oid"]:
                        hit = cd.census_binding(CENSUS, cd.HUB_REPO, b["path"])
                        self.assertEqual(hit["oid"], b["oid"])
                        seen += 1
        self.assertGreater(seen, 0)


class ScaleDock(unittest.TestCase):
    """#781 owns the dock definitions; this projection only calls them."""

    def _sources(self):
        return cd.load_sources(ROOT, POLICY)

    def test_docks_come_from_scale_dock_and_agree(self):
        docks = cd.scale_docks(HUB, POLICY, self._sources())
        self.assertEqual(docks["consistency"]["state"], "CONSISTENT_WHERE_OBSERVED")
        for name in ("issue_bd", "crosswalk"):
            self.assertEqual(docks["docks"][name], {"status": "NOT_DOCKED", "metrics": None})
        pp = SCOPES["TOTAL"]["metrics"]["p_process"]
        self.assertEqual(pp["open_roots"], docks["docks"]["p_process"]["metrics"]["open_roots"])
        self.assertEqual(pp["dock_consistency"], docks["consistency"]["state"])
        node = {x["id"]: x for x in SCOPES["TOTAL"]["nodes"]}["X.DOCK_CONSISTENCY"]
        self.assertEqual(node["status"], "PASS")
        self.assertIn("scale_dock.py", node["oids"][0]["path"])

    def test_source_disagreement_is_reported_not_repaired(self):
        src = self._sources()
        src["p_state"] = copy.deepcopy(src["p_state"])
        first = sorted(src["p_state"]["repos"])[0]
        src["p_state"]["repos"][first]["open_roots"] += 1
        docks = cd.scale_docks(HUB, POLICY, src)
        self.assertEqual(docks["consistency"]["state"], "HOLD_SOURCE_DISAGREEMENT")
        self.assertEqual(cd.DOCK_STATUS[docks["consistency"]["state"]], "FAIL")

    def test_dock_schema_drift_fails_closed(self):
        src = self._sources()
        src["code_purple"] = dict(src["code_purple"], schema="code-purple.census/v1")
        with self.assertRaisesRegex(ValueError, "code_purple dock schema drift"):
            cd.scale_docks(HUB, POLICY, src)


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
                        "mission-control/gogreen", ".github/workflows"):
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
        # Detail panel is DOM-built (CodeQL js/xss-through-dom): no HTML string sinks, https links only.
        self.assertNotIn("innerHTML", html)
        self.assertNotIn("insertAdjacentHTML", html)
        self.assertIn("x.protocol==='https:'", html)
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
