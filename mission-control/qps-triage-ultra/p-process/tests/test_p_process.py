"""Offline tests for the P process (Code Purple x EVERRED): no network, no secrets.

Run: python -m unittest discover -s mission-control/qps-triage-ultra/p-process/tests -v
"""
import hashlib
import importlib.util
import json
import re
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

import yaml

P = Path(__file__).resolve().parents[1]
REPO = P.parents[2]


def load(name: str, rel: str):
    spec = importlib.util.spec_from_file_location(name, P / rel)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


readback = load("p_readback", "kit/readback.py")
harvest = load("p_harvest", "everred/harvest.py")
build_rulesets = load("p_build_rulesets", "rulesets/build_rulesets.py")
verify_rulesets = load("p_verify_rulesets", "rulesets/verify_rulesets.py")
p_decide = load("p_decide", "p_decide.py")
refresh = load("p_refresh", "refresh.py")


class CodePurpleKit(unittest.TestCase):
    def test_empty_ruleset_is_not_clean(self):
        # 13 Oct lesson: a ruleset with zero rules passed L2. It must report every expected rule as absent.
        exp = [{"type": "deletion"}, {"type": "required_status_checks", "contexts": ["PR Feedback Gate"], "strict": True}]
        self.assertEqual(readback.missing_rules([], exp), ["deletion rule absent", "required_status_checks rule absent"])

    def test_partial_restore_still_reports_gate(self):
        actual = [{"type": "deletion"}, {"type": "required_status_checks", "parameters": {"required_status_checks": [{"context": "smoke"}]}}]
        exp = [{"type": "deletion"}, {"type": "required_status_checks", "contexts": ["PR Feedback Gate"], "strict": True}]
        self.assertEqual(readback.missing_rules(actual, exp), ["required check 'PR Feedback Gate' absent", "strict up-to-date policy off"])

    def test_classify_inherited_vs_source(self):
        c = readback.classify(["coverage", "lint"], ["coverage"])
        self.assertEqual(c, {"inherited": ["coverage"], "source_defect_candidates": ["lint"]})

    def test_incident_l2_declares_rule_content(self):
        inc = yaml.safe_load((P / "kit/incident.yaml").read_text())
        l2 = next(x for x in inc["lift_criteria"] if x["id"] == "L2")
        self.assertTrue(l2["ref"]["expected_rules"], "L2 must compare rule content, not only enforcement")
        self.assertIn("L5", {x["id"] for x in inc["lift_criteria"]})


class Rulesets(unittest.TestCase):
    def setUp(self):
        self.man = json.loads((P / "rulesets/manifest.json").read_text())

    def test_every_ruleset_is_basic_and_safe(self):
        for repo, m in self.man.items():
            rs = json.loads((P / "rulesets" / m["file"]).read_text())
            with self.subTest(repo=repo):
                self.assertEqual(rs["bypass_actors"], [], "break glass adds a bypass actor at the time; never ship one")
                self.assertEqual(rs["conditions"]["ref_name"]["include"], ["~DEFAULT_BRANCH"])
                types = [r["type"] for r in rs["rules"]]
                for t in ("deletion", "non_fast_forward", "pull_request", "required_status_checks"):
                    self.assertIn(t, types)
                rsc = next(r for r in rs["rules"] if r["type"] == "required_status_checks")["parameters"]["required_status_checks"]
                self.assertEqual([c["context"] for c in rsc], m["checks"])
                self.assertTrue(all(c["integration_id"] == build_rulesets.ACTIONS for c in rsc))

    def test_generator_matches_committed_files(self):
        for repo, cfg in build_rulesets.REPOS.items():
            name = repo.split("/")[1]
            committed = json.loads((P / "rulesets" / f"{name}.basic.json").read_text())
            self.assertEqual(build_rulesets.basic(repo, cfg), committed, f"{name}.basic.json is stale: run build_rulesets.py")

    def test_hub_required_checks_are_not_path_filtered(self):
        jobs = build_rulesets.path_filtered_jobs(REPO / ".github/workflows")
        for c in self.man["GBOGEB/pipeline-automation-hub"]["checks"]:
            self.assertIn(c, jobs, f"{c} is not a PR job in this repo")
            self.assertFalse(jobs[c], f"{c} is path-filtered: as a required check it would block unrelated PRs")

    def test_path_filter_detection(self):
        tmp = P / "build" / "wf_test"
        shutil.rmtree(tmp, ignore_errors=True)
        tmp.mkdir(parents=True)
        (tmp / "a.yml").write_text("on:\n  pull_request:\n    paths: ['x/**']\njobs:\n  audit:\n    runs-on: x\n")
        (tmp / "b.yml").write_text("on: [pull_request]\njobs:\n  t:\n    name: smoke\n    runs-on: x\n")
        j = build_rulesets.path_filtered_jobs(tmp)
        self.assertTrue(j["audit"])
        self.assertFalse(j["smoke"])
        shutil.rmtree(tmp)

    def test_drift_gaps(self):
        exp = json.loads((P / "rulesets/ABACUS.basic.json").read_text())
        eff = [{"type": "deletion"}, {"type": "pull_request", "parameters": {"required_review_thread_resolution": True}}, {"type": "non_fast_forward"}]
        self.assertEqual(verify_rulesets.gaps(eff, exp), ["required_status_checks missing"])
        self.assertEqual(len(verify_rulesets.gaps([], exp)), 4)


class Everred(unittest.TestCase):
    def setUp(self):
        self.ledger = yaml.safe_load((P / "everred/roots.yaml").read_text())

    def test_signature_normalisation(self):
        self.assertEqual(harvest.split_env("tests (Python 3.12, ubuntu-latest)"), ("tests", "Python 3.12, ubuntu-latest"))
        self.assertEqual(harvest.norm("shard-007 at 1a2b3c4d5e"), "shard-* at <sha>")

    def test_probe_fails_closed(self):
        root = {"id": "X", "match": [{"probe": "ruleset_drift", "repo": "GBOGEB/none"}]}
        self.assertTrue(harvest.probe_root(root, {})["red"], "a repo missing from the drift census must not read green")
        green = harvest.probe_root(root, {"GBOGEB/none": {"red": False, "gaps": [], "effective_rules": ["deletion"]}})
        self.assertFalse(green["red"])
        self.assertIsNone(harvest.probe_root({"id": "Y", "match": [{"job": "lint"}]}, {}))

    def test_probe_is_not_a_signature_match(self):
        self.assertFalse(harvest.matches({"repo": "r", "workflow": "w", "job": "j", "step": "s"}, {"probe": "ruleset_drift"}))

    def test_root_ledger_schema(self):
        L = self.ledger
        self.assertEqual(L["schema"], "everred.roots/3.0")
        ids = [r["id"] for r in L["roots"]]
        self.assertEqual(len(ids), len(set(ids)), "root IDs are never reused")
        for r in L["roots"]:
            with self.subTest(root=r["id"]):
                self.assertRegex(r["id"], r"^[A-Z]+-RC-\d{4}-\d{4}$")
                self.assertIn(r["state"], L["lifecycle"])
                self.assertIn(r["class"], L["classes"])
                self.assertEqual(set(r["dims"]), set(L["dimensions"]), "all seven dimensions, every root")
                for k, v in r["dims"].items():
                    self.assertIn(v, L["dimensions"][k] + ["NA"])
                if r["class"] == "CONTROL_PLANE_DRIFT":
                    self.assertTrue(any(m.get("probe") == "ruleset_drift" for m in r.get("match", [])), "drift is found by probe, not by a red job")
                if r.get("split_from"):
                    self.assertIn(r["split_from"], ids)

    def test_probe_scope_covers_manifest(self):
        man = json.loads((P / "rulesets/manifest.json").read_text())
        self.assertEqual(set(self.ledger["probe_scope"]), set(man))


class Decide(unittest.TestCase):
    ROOTS = [{"id": "ABACUS-RC-2026-0001", "severity": "P0", "state": "BLOCKED_AUTHORITY", "probe": {"red": True}},
             {"id": "CODEX-RC-2026-0003", "severity": "P1", "state": "BLOCKED_AUTHORITY", "probe": {"red": True}}]

    def test_open_case_and_p0_drift_escalate(self):
        st = p_decide.decide({"lifted": False, "lift": [{"ok": True}, {"ok": False}]}, {"roots": self.ROOTS},
                             {"repos": {"GBOGEB/ABACUS": {"red": True}, "GBOGEB/CODEX": {"red": True}}}, ["GBOGEB/ABACUS"])
        a, c = st["repos"]["GBOGEB/ABACUS"], st["repos"]["GBOGEB/CODEX"]
        self.assertEqual(a["mode"], "CODE_PURPLE")
        self.assertEqual([r[:2] for r in a["reasons"]], ["E2", "E1"])
        self.assertEqual(c["mode"], "EVERRED", "P1 drift is an EVERRED lane, not an escalation")

    def test_lifted_case_hands_off(self):
        st = p_decide.decide({"lifted": True, "lift": []}, {"roots": []}, {"repos": {}}, ["GBOGEB/ABACUS"])
        self.assertEqual(st["repos"]["GBOGEB/ABACUS"]["mode"], "EVERRED")
        self.assertEqual(st["repos"]["GBOGEB/ABACUS"]["ruleset"], "UNKNOWN", "no drift row is UNKNOWN, never GREEN")


class Site(unittest.TestCase):
    def test_census_markers_rewrite(self):
        page = P / "build" / "cp_test.html"
        page.parent.mkdir(exist_ok=True)
        page.write_text("<div>\n<!-- census:begin x -->\nOLD\n<!-- census:end -->\n</div>")
        c = {"lifted": False, "lift": [{"ok": True}, {"ok": False}], "generated_at": "2026-10-17T20:25:00+00:00",
             "repos": {"GBOGEB/ABACUS": {"open_prs": 9}}, "merges_since_unblock": 3}
        refresh.stamp_code_purple(page, c)
        t = page.read_text()
        self.assertNotIn("OLD", t)
        self.assertIn("NOT LIFTED · 1 of 2 lift criteria", t)
        self.assertIn("ABACUS: 9 open PRs", t)
        page.unlink()

    def test_committed_site_matches_manifest(self):
        man = json.loads((P / "site/manifest.json").read_text())
        for rel, h in man["files_sha256"].items():
            with self.subTest(file=rel):
                self.assertEqual(hashlib.sha256((P / "site" / rel).read_bytes()).hexdigest(), h)

    def test_pages_link_together_and_census_is_current(self):
        idx = (P / "site/index.html").read_text()
        for href in ("code-purple/index.html", "everred/index.html", "P-process-deck.pdf"):
            self.assertIn(href, idx)
            self.assertTrue((P / "site" / href).is_file(), href)
        census = json.loads((P / "site/code-purple/kit/census.json").read_text())
        cp = (P / "site/code-purple/index.html").read_text()
        self.assertIn("read back " + census["generated_at"][:16].replace("T", " "), cp, "Code Purple header not stamped from the census")


@unittest.skipUnless(shutil.which("node"), "node not installed")
class Model(unittest.TestCase):
    def test_model_integrity(self):
        r = subprocess.run(["node", str(P / "tools/check_model.mts")], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(json.loads(r.stdout)["ok"])

    def test_broken_model_fails(self):
        src = (P / "code-purple/assets/model.js").read_text()
        bad = P / "build" / "model_bad.js"
        bad.parent.mkdir(exist_ok=True)
        bad.write_text(src.replace('f:"N01"', 'f:"N99"', 1))
        r = subprocess.run(["node", str(P / "tools/check_model.mts")], capture_output=True, text=True, env={"CP_MODEL_JS": str(bad), "PATH": "/usr/bin:/bin:" + str(Path(shutil.which("node")).parent)})
        self.assertEqual(r.returncode, 1)
        self.assertTrue(re.search(r"N99 is not a node", r.stderr))
        bad.unlink()


if __name__ == "__main__":
    unittest.main()
