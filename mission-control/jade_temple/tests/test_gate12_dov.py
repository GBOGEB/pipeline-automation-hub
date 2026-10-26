"""JADE H01-H12 owner cockpit: fixed populations, negative sources, no false release."""
import copy
import importlib.util
import json
import shutil
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("gate12", ROOT / "tools/build_gate12_dov.py")
gate12 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate12)


class Gate12Tests(unittest.TestCase):
    def temporary_source(self):
        tmp = tempfile.TemporaryDirectory()
        root = Path(tmp.name)
        (root / "data").mkdir()
        for path in gate12.FILES.values():
            shutil.copyfile(ROOT / path, root / path)
        return tmp, root

    def test_twelve_canonical_gate_identities_and_content_owners(self):
        p = gate12.project()
        self.assertEqual([x["id"] for x in p["pillars"]],
                         [f"H{i:02d}" for i in range(1, 13)])
        for x in p["pillars"]:
            self.assertTrue(x["owner"])
            self.assertTrue(x["threshold"])
            self.assertTrue(x["quality"])
            self.assertTrue(x["proof"])
            self.assertTrue(x["action"])
            self.assertEqual(x["threshold_state"], "OWNER_POLICY_REVIEW_REQUIRED")

    def test_focus_vs_top21_denominators_are_not_conflated(self):
        p = gate12.project()
        m = p["metrics"]
        self.assertEqual((m["observed_repositories"], m["unassessed_repositories"]), (5, 16))
        self.assertEqual((m["observed_pass"], m["observed_fail"], m["observed_unknown"]), (14, 8, 38))
        self.assertEqual((m["observed_gate_denominator"], m["portfolio_gate_slots"],
                          m["unassessed_gate_slots"]), (60, 252, 192))
        self.assertEqual(len(p["queue"]), 252)
        self.assertEqual(len({x["repository"] for x in p["queue"]}), 21)

    def test_unassessed_population_never_promoted_to_pass(self):
        p = gate12.project()
        z = [x for x in p["queue"] if x["status"] == "UNOBSERVED"]
        self.assertEqual(len(z), 192)
        self.assertTrue(all(x["evidence"] is None and x["source_sha"] is None for x in z))

    def test_routed_frontier_is_noncompensating(self):
        p = gate12.project()
        states = p["metrics"]["task_readiness"]
        self.assertEqual(sum(states.values()), 252)
        self.assertEqual(states["COMPLETE"], 14)
        self.assertEqual(states["FIRST_RED"], 6)
        self.assertTrue(all(x["readiness"] != "COMPLETE" for x in p["queue"]
                            if x["status"] != "PASS"))
        self.assertTrue(all(x["blocked_by"] for x in p["queue"]
                            if x["readiness"] == "WAIT_DEPENDENCY"))

    def test_generated_output_byte_parity(self):
        for rel, expected in gate12.outputs().items():
            path = ROOT / "site" / rel
            self.assertTrue(path.is_file(), rel)
            self.assertEqual(path.read_bytes(), expected, rel)

    def test_source_and_publisher_release_remain_unqualified(self):
        p = gate12.project()
        self.assertFalse(p["authority"]["current_head_recertified"])
        self.assertEqual(p["authority"]["merge_admission"], "HOLD")
        self.assertEqual(p["authority"]["formal_release_credit"], 0)
        self.assertIsNone(p["source"]["live_current_head"])
        for key in ("static_qa", "browser_qa", "staged_single_publisher", "deployed",
                    "hosted_http_200", "served_sha_matches", "operational_health",
                    "rollback_drill"):
            self.assertIsNone(p["publication"][key], key)
        self.assertEqual(p["publication"]["owner_release"], "HOLD")

    def test_registry_authority_mutation_fails_closed(self):
        tmp, root = self.temporary_source()
        try:
            path = root / gate12.FILES["actions"]
            d = json.loads(path.read_text(encoding="utf-8"))
            d["merge_admission"] = "PASS"
            path.write_text(json.dumps(d), encoding="utf-8", newline="\n")
            with self.assertRaisesRegex(ValueError, "unsafe DoV authority"):
                gate12.project(root)
        finally:
            tmp.cleanup()

    def test_fake_extra_pass_breaks_source_denominator(self):
        tmp, root = self.temporary_source()
        try:
            path = root / gate12.FILES["focus"]
            d = json.loads(path.read_text(encoding="utf-8"))
            target = next(g for g in d["rows"][0]["gates"] if g["status"] == "UNKNOWN")
            target["status"] = "PASS"
            path.write_text(json.dumps(d), encoding="utf-8", newline="\n")
            with self.assertRaisesRegex(ValueError, "misstated evidence totals"):
                gate12.project(root)
        finally:
            tmp.cleanup()

    def test_missing_top21_row_and_gate_rejected(self):
        tmp, root = self.temporary_source()
        try:
            path = root / gate12.FILES["roster"]
            d = json.loads(path.read_text(encoding="utf-8"))
            d["repositories"].pop()
            path.write_text(json.dumps(d), encoding="utf-8", newline="\n")
            with self.assertRaisesRegex(ValueError, "Top21 population drift"):
                gate12.project(root)
        finally:
            tmp.cleanup()

    def test_asset_discovery_and_ui_navigation_are_real_repo_files(self):
        p = gate12.project()
        for asset in p["assets"]:
            self.assertEqual(asset["hosted_status"], "UNVERIFIED")
            self.assertTrue((ROOT / "site" / asset["path"]).is_file(), asset["path"])
        h = (ROOT / "site/gate12_hub.html").read_text(encoding="utf-8")
        j = (ROOT / "site/gate12_ui.js").read_text(encoding="utf-8")
        self.assertIn("<title>", h)
        for anchor in ("executive", "pillars", "content-health", "bd-queue",
                       "pages", "discovery", "source"):
            self.assertIn('id="' + anchor + '"', h)
        self.assertIn("connect-src 'none'", h)
        for sink in ("innerHTML", "insertAdjacentHTML", "XMLHttpRequest", "fetch("):
            self.assertNotIn(sink, j)
        self.assertIn("textContent", j)
        self.assertIn("replaceChildren", j)


if __name__ == "__main__":
    unittest.main()
