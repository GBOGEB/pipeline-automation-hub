"""JADE H01-H12 owner cockpit: fixed populations, negative sources, no false release."""
import copy
import hashlib
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
    def temporary_source(self, history=False):
        tmp = tempfile.TemporaryDirectory()
        root = Path(tmp.name)
        (root / "data").mkdir()
        for path in gate12.FILES.values():
            shutil.copyfile(ROOT / path, root / path)
        if history:
            ledger = json.loads((ROOT / gate12.ROLLING5.LEDGER).read_text(encoding="utf-8"))
            shutil.copyfile(ROOT / gate12.ROLLING5.LEDGER, root / gate12.ROLLING5.LEDGER)
            for pulse in ledger["pulses"]:
                shutil.copyfile(ROOT / pulse["snapshot"], root / pulse["snapshot"])
        return tmp, root

    def mutate_latest(self, root, mutate, repin=True):
        ledger_path = root / gate12.ROLLING5.LEDGER
        ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
        pulse = ledger["pulses"][-1]
        path = root / pulse["snapshot"]
        data = json.loads(path.read_text(encoding="utf-8"))
        mutate(data)
        path.write_text(json.dumps(data), encoding="utf-8", newline="\n")
        if repin:
            pulse["snapshot_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
            ledger_path.write_text(json.dumps(ledger), encoding="utf-8", newline="\n")

    def test_latest_recorded_is_additive_to_frozen_api(self):
        frozen = gate12.project()
        latest = gate12.latest_recorded()
        self.assertNotIn("latest_recorded", frozen)
        self.assertEqual(frozen["metrics"]["observed_pass"], 14)
        self.assertEqual((latest["metrics"]["observed_pass"],
                          latest["metrics"]["observed_fail"],
                          latest["metrics"]["observed_unknown"]), (25, 0, 35))
        self.assertEqual(latest["metrics"]["observed_gate_denominator"], 60)
        self.assertEqual(latest["source"]["pulse_id"], "P0005")
        self.assertEqual(latest["source"]["observation"], "LATEST_RECORDED_PULSE")
        self.assertEqual(latest["source"]["observed_date"], "2026-11-04")
        self.assertFalse(latest["authority"]["current_head_recertified"])
        self.assertEqual(latest["authority"]["formal_release_credit"], 0)
        self.assertTrue(all("reason" in task and "streak" in task for task in latest["queue"]))
        task = next(t for t in latest["queue"] if t["status"] == "UNKNOWN")
        self.assertTrue(task["reason"])
        self.assertIsNotNone(task["streak"])
        output = gate12.outputs()
        model = json.loads(output["gate12_data.json"])
        self.assertEqual(model["metrics"], frozen["metrics"])
        self.assertEqual(model["latest_recorded"], latest)
        self.assertIn("gate12_latest_queue.csv", output)

    def test_latest_tampered_or_missing_snapshot_has_no_frozen_fallback(self):
        for missing in (False, True):
            tmp, root = self.temporary_source(history=True)
            try:
                ledger = json.loads((root / gate12.ROLLING5.LEDGER).read_text(encoding="utf-8"))
                path = root / ledger["pulses"][-1]["snapshot"]
                if missing:
                    path.unlink()
                else:
                    path.write_text("{}", encoding="utf-8", newline="\n")
                with self.subTest(missing=missing), self.assertRaises((ValueError, FileNotFoundError)):
                    gate12.outputs(root)
                self.assertEqual(gate12.project(root)["metrics"]["observed_pass"], 14)
            finally:
                tmp.cleanup()

    def test_latest_reordered_ledger_and_missing_gate_fail_closed(self):
        tmp, root = self.temporary_source(history=True)
        try:
            path = root / gate12.ROLLING5.LEDGER
            data = json.loads(path.read_text(encoding="utf-8"))
            data["pulses"].reverse()
            path.write_text(json.dumps(data), encoding="utf-8", newline="\n")
            with self.assertRaisesRegex(ValueError, "older"):
                gate12.latest_recorded(root)
        finally:
            tmp.cleanup()
        tmp, root = self.temporary_source(history=True)
        try:
            self.mutate_latest(root, lambda d: d["rows"][0]["gates"].pop())
            with self.assertRaisesRegex(ValueError, "gate (population|inventory)"):
                gate12.latest_recorded(root)
        finally:
            tmp.cleanup()

    def test_latest_declared_metrics_cannot_promote_or_change_denominator(self):
        for field in ("passed", "required_gate_total"):
            tmp, root = self.temporary_source(history=True)
            try:
                def mutate(data):
                    data["metrics"][field] += 1
                self.mutate_latest(root, mutate)
                with self.subTest(field=field), self.assertRaisesRegex(ValueError, "metrics disagree|misstated"):
                    gate12.latest_recorded(root)
            finally:
                tmp.cleanup()

    def test_latest_missing_ledger_fails_without_changing_frozen_api(self):
        tmp, root = self.temporary_source()
        try:
            with self.assertRaises(FileNotFoundError):
                gate12.outputs(root)
            self.assertEqual(gate12.project(root)["metrics"]["observed_pass"], 14)
        finally:
            tmp.cleanup()

    def test_latest_cohort_denominator_uses_recorded_population(self):
        tmp, root = self.temporary_source(history=True)
        try:
            def mutate(data):
                data["rows"] = data["rows"][:1]
                data["source"]["focus_repositories"] = 1
                states = [g["status"] for g in data["rows"][0]["gates"]]
                data["metrics"].update({"required_gate_total": 12,
                                        "top21_unassessed_outside_focus": 20,
                                        "passed": states.count("PASS"),
                                        "failed": states.count("FAIL"),
                                        "unknown": states.count("UNKNOWN")})
            self.mutate_latest(root, mutate)
            latest = gate12.latest_recorded(root)
            self.assertEqual(latest["metrics"]["observed_repositories"], 1)
            self.assertEqual(latest["metrics"]["observed_gate_denominator"], 12)
            self.assertEqual(latest["metrics"]["unassessed_gate_slots"], 240)
            self.assertEqual(len(latest["queue"]), 252)
            self.assertEqual(sum(r["observed"] for r in latest["repositories"]), 1)
        finally:
            tmp.cleanup()

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
