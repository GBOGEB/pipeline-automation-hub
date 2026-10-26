"""Rolling-5 window: NIRVANA needs sustained exact-SHA PASS, UNKNOWN is never
PASS, the ledger is append-only and hash-pinned, and SOURCE_RED ranks the
red that unlocks the most work."""
import copy
import hashlib
import importlib.util
import io
import json
import shutil
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("rolling5", ROOT / "tools" / "rolling5.py")
r5 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r5)

GATES = [f"H{i:02d}" for i in range(1, 13)]
SHA_A, SHA_B = "a" * 40, "b" * 40


def row(repo, rank, statuses, sha=SHA_A, candidate=None):
    gates = [{"id": g, "label": g, "phase": "X", "status": statuses.get(g, "UNKNOWN"),
              "evidence": None, "reason": None} for g in GATES]
    out = {"rank": rank, "repo": repo, "source_sha": sha, "gates": gates,
           "blockers": []}
    if candidate:
        out["candidate_branch"], out["candidate_sha"] = candidate
    return out


def snapshot(date, rows, edges=()):
    return {"schema": "jade.temple.focus5.readonly/1.0",
            "source": {"observed_date": date}, "rows": rows, "edges": list(edges)}


ALL_PASS = dict.fromkeys(GATES, "PASS")


class Sandbox:
    """A throwaway jade_temple root with the real policy and a small roster."""

    def __init__(self, roster_size=7):
        self.dir = tempfile.TemporaryDirectory()
        self.root = Path(self.dir.name)
        (self.root / "data").mkdir()
        (self.root / "site").mkdir()
        shutil.copy(ROOT / "data" / "ROLLING5_POLICY.json", self.root / "data")
        roster = [{"repo": f"o/r{i}", "rank": i} for i in range(1, roster_size + 1)]
        self.write("data/TOP21_PORTFOLIO.json", {"repositories": roster})
        self.write("data/ROLLING5_PULSES.json", {"pulses": []})

    def write(self, rel, obj):
        (self.root / rel).write_text(json.dumps(obj), encoding="utf-8", newline="\n")

    def add(self, pid, snap):
        self.count = getattr(self, "count", 0) + 1
        rel = f"data/snap_{self.count}.json"
        self.write(rel, snap)
        ledger = json.loads((self.root / "data/ROLLING5_PULSES.json").read_text(encoding="utf-8"))
        ledger["pulses"].append({
            "id": pid, "observed_date": snap["source"]["observed_date"],
            "snapshot": rel,
            "snapshot_sha256": hashlib.sha256((self.root / rel).read_bytes()).hexdigest()})
        self.write("data/ROLLING5_PULSES.json", ledger)

    def close(self):
        self.dir.cleanup()


def five(statuses_by_repo=None, sha=SHA_A):
    statuses_by_repo = statuses_by_repo or {}
    return [row(f"o/r{i}", i, statuses_by_repo.get(f"o/r{i}", {}), sha)
            for i in range(1, 6)]


class RealDataTests(unittest.TestCase):
    def setUp(self):
        self.model = r5.project()

    def test_reproduces_focus5_denominator_without_credit(self):
        m = self.model["metrics"]
        # Latest pulse P0002 (2026-10-25); P0001 was 14/60.
        self.assertEqual((m["verified_pass"], m["gate_denominator"]), (17, 60))
        self.assertEqual(m["verified_completion_pct"], 28.33)
        self.assertEqual(m["nirvana_count"], 0)
        self.assertEqual(self.model["merge_admission"], "HOLD")
        self.assertFalse(self.model["release_credit"])
        self.assertFalse(self.model["authority_transfer"])

    def test_h08_is_core_focus(self):
        # P0001: H08 FAIL in all five (COMMON_CAUSE). P0002: protection is active on
        # hub, cryoplant-project and gg_MATH (H08 UNKNOWN until a RED canary), so the
        # remaining H08 red is LOCAL to the two unprotected repos.
        red = self.model["source_red"]
        self.assertEqual(red["core_focus"], "H08")
        top = red["ranked_gates"][0]
        self.assertEqual((top["gate"], top["repo_count"], top["class"]),
                         ("H08", 2, "LOCAL"))

    def test_h03_is_common_unknown_breaking_every_golden_thread(self):
        unknown = {u["gate"]: u for u in self.model["source_red"]["common_unknown"]}
        self.assertEqual(unknown["H03"]["repo_count"], 5)
        self.assertTrue(all(r["golden_thread"]["first_break"] == "OWNER_SCOPE"
                            for r in self.model["repos"]))

    def test_window_holds_five_until_nirvana(self):
        w = self.model["window"]
        self.assertEqual(len(w["current"]), 5)
        self.assertEqual(w["next"], w["current"])
        self.assertEqual(w["admitted"], [])

    def test_short_history_is_declared_not_extrapolated(self):
        # Two pulses: fewer than three, so 'unattended' is never inferred.
        self.assertEqual(self.model["history_depth"], 2)
        for repo in self.model["repos"]:
            for s in repo["streaks"].values():
                self.assertIsNone(s["unattended"])

    def test_committed_outputs_are_in_parity(self):
        with redirect_stdout(io.StringIO()):
            self.assertEqual(r5.main(["--check"]), 0)


class StreakTests(unittest.TestCase):
    def test_current_record_previous_and_regressions(self):
        s = r5.streak_stats(["PASS", "PASS", "FAIL", "PASS", "PASS", "PASS"], 3)
        self.assertEqual((s["streak_on_current"], s["streak_record"],
                          s["previous_streak"], s["regressions"]), (3, 3, 2, 1))
        self.assertFalse(s["nevergreen"])

    def test_broken_current_streak_moves_to_previous(self):
        s = r5.streak_stats(["PASS", "PASS", "PASS", "FAIL"], 3)
        self.assertEqual((s["streak_on_current"], s["previous_streak"],
                          s["streak_record"]), (0, 3, 3))

    def test_unknown_is_never_green_and_becomes_unattended(self):
        s = r5.streak_stats(["UNKNOWN"] * 3, 3)
        self.assertTrue(s["nevergreen"])
        self.assertTrue(s["unattended"])
        self.assertEqual(s["streak_on_current"], 0)

    def test_unattended_needs_enough_history(self):
        self.assertIsNone(r5.streak_stats(["UNKNOWN"] * 2, 3)["unattended"])
        self.assertFalse(r5.streak_stats(["UNKNOWN", "UNKNOWN", "FAIL"], 3)["unattended"])

    def test_unobserved_pulses_do_not_count(self):
        s = r5.streak_stats([None, "PASS"], 3)
        self.assertEqual((s["pulses_observed"], s["streak_on_current"]), (1, 1))


class NirvanaRotationTests(unittest.TestCase):
    def timeline(self, *snaps):
        return [r5.rows_of(s) for s in snaps]

    def test_single_all_pass_pulse_is_not_nirvana(self):
        t = self.timeline(snapshot("2026-10-01", five({"o/r1": ALL_PASS})))
        self.assertFalse(r5.nirvana("o/r1", t, 2))

    def test_sustained_exact_sha_all_pass_is_nirvana(self):
        s = snapshot("2026-10-01", five({"o/r1": ALL_PASS}))
        self.assertTrue(r5.nirvana("o/r1", self.timeline(s, s), 2))

    def test_missing_duplicate_and_extra_gate_denied(self):
        for mode in ("missing", "duplicate", "extra"):
            items = five({"o/r1": ALL_PASS})
            gates = items[0]["gates"]
            if mode == "missing":
                gates.pop()
            elif mode == "duplicate":
                gates[-1] = dict(gates[0])
            else:
                gates.append({"id": "H13", "status": "PASS"})
            with self.subTest(mode=mode), self.assertRaisesRegex(
                    ValueError, "invalid H01-H12 gate inventory"):
                r5.rows_of(snapshot("2026-10-02", items))

    def test_duplicate_repo_denied(self):
        items = five()
        items.append(copy.deepcopy(items[0]))
        with self.assertRaisesRegex(ValueError, "duplicate repository"):
            r5.rows_of(snapshot("2026-10-02", items))

    def test_direct_nirvana_requires_exact_inventory(self):
        items = five({"o/r1": ALL_PASS})
        timeline = self.timeline(snapshot("2026-10-01", items),
                                 snapshot("2026-10-02", items))
        self.assertTrue(r5.nirvana("o/r1", timeline, 2))
        timeline[1]["o/r1"]["gates"].pop("H12")
        self.assertFalse(r5.nirvana("o/r1", timeline, 2))

    def test_sha_drift_or_one_unknown_denies_nirvana(self):
        a = snapshot("2026-10-01", five({"o/r1": ALL_PASS}))
        b = snapshot("2026-10-02", five({"o/r1": ALL_PASS}, sha=SHA_B))
        self.assertFalse(r5.nirvana("o/r1", self.timeline(a, b), 2))
        almost = dict(ALL_PASS, H12="UNKNOWN")
        c = snapshot("2026-10-02", five({"o/r1": almost}))
        self.assertFalse(r5.nirvana("o/r1", self.timeline(a, c), 2))

    def test_missing_or_non_hex_sha_denies_nirvana(self):
        s = snapshot("2026-10-01", five({"o/r1": ALL_PASS}, sha=None))
        self.assertFalse(r5.nirvana("o/r1", self.timeline(s, s), 2))
        self.assertFalse(r5.nirvana("o/r9", self.timeline(s, s), 2))

    def test_rotation_admits_next_ranked_and_never_exceeds_window(self):
        roster = [{"repo": f"o/r{i}", "rank": i} for i in range(1, 8)]
        window = [f"o/r{i}" for i in range(1, 6)]
        out = r5.rotate(window, roster, {"o/r2"}, 5)
        self.assertEqual(out["admitted"], ["o/r6"])
        self.assertEqual(len(out["next"]), 5)
        self.assertNotIn("o/r2", out["next"])

    def test_exhausted_roster_leaves_empty_slots_not_graduates(self):
        roster = [{"repo": f"o/r{i}", "rank": i} for i in range(1, 6)]
        window = [f"o/r{i}" for i in range(1, 6)]
        out = r5.rotate(window, roster, {"o/r1", "o/r2"}, 5)
        self.assertEqual(out["empty_slots"], 2)
        self.assertNotIn("o/r1", out["next"])

    def test_race_counts_unknown_as_remaining(self):
        rows = r5.rows_of(snapshot("d", five({"o/r1": {"H01": "PASS"},
                                              "o/r2": {"H01": "FAIL"}})))
        race = {x["repo"]: x for x in r5.race(rows)}
        self.assertEqual(race["o/r1"]["remaining"], 11)
        self.assertEqual(race["o/r1"]["position"], 1)
        self.assertGreater(race["o/r2"]["position"], race["o/r3"]["position"])


class EndToEndTests(unittest.TestCase):
    def setUp(self):
        self.box = Sandbox()

    def tearDown(self):
        self.box.close()

    def test_first_to_nirvana_graduates_and_admits_next(self):
        partial = dict(ALL_PASS, H09="UNKNOWN")
        self.box.add("P1", snapshot("2026-10-01", five({"o/r3": partial})))
        self.box.add("P2", snapshot("2026-10-02", five({"o/r3": ALL_PASS})))
        self.box.add("P3", snapshot("2026-10-03", five({"o/r3": ALL_PASS})))
        model = r5.project(self.box.root)
        self.assertEqual(model["nirvana_ledger"],
                         [{"repo": "o/r3", "pulse": "P3", "order": 1}])
        self.assertEqual(model["window"]["admitted"], ["o/r6"])
        r3 = next(r for r in model["repos"] if r["repo"] == "o/r3")
        self.assertEqual(r3["streaks"]["H09"]["streak_on_current"], 2)
        self.assertEqual(r3["streaks"]["H01"]["streak_record"], 3)
        self.assertTrue(r3["nirvana"])
        self.assertEqual(model["metrics"]["nirvana_count"], 1)

    def test_snapshot_tamper_fails_closed(self):
        self.box.add("P1", snapshot("2026-10-01", five()))
        (self.box.root / "data/snap_1.json").write_text("{}", encoding="utf-8", newline="\n")
        with self.assertRaisesRegex(ValueError, "snapshot drift"):
            r5.project(self.box.root)

    def test_duplicate_and_out_of_order_pulses_fail_closed(self):
        self.box.add("P1", snapshot("2026-10-02", five()))
        self.box.add("P1", snapshot("2026-10-03", five(sha=SHA_B)))
        with self.assertRaisesRegex(ValueError, "duplicate"):
            r5.project(self.box.root)
        box = Sandbox()
        try:
            box.add("P1", snapshot("2026-10-02", five()))
            box.add("P2", snapshot("2026-10-01", five(sha=SHA_B)))
            with self.assertRaisesRegex(ValueError, "older"):
                r5.project(box.root)
        finally:
            box.close()

    def test_empty_ledger_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "empty"):
            r5.project(self.box.root)

    def test_append_pulse_pins_and_rejects_duplicates(self):
        self.box.add("P1", snapshot("2026-10-01", five()))
        self.box.write("data/next.json", snapshot("2026-10-02", five(sha=SHA_B)))
        with redirect_stdout(io.StringIO()):
            self.assertEqual(r5.main(["--append-pulse", "data/next.json",
                                      "--pulse-id", "P2"], root=self.box.root), 0)
        ledger = json.loads((self.box.root / "data/ROLLING5_PULSES.json").read_text(encoding="utf-8"))
        self.assertEqual([p["id"] for p in ledger["pulses"]], ["P1", "P2"])
        self.assertEqual(ledger["pulses"][1]["origin"], "APPENDED")
        with self.assertRaisesRegex(ValueError, "duplicate"):
            r5.append_pulse(self.box.root, "data/next.json", "P3")

    def test_append_refuses_a_ledger_that_already_drifted(self):
        self.box.add("P1", snapshot("2026-10-01", five()))
        (self.box.root / "data/snap_1.json").write_text("{}", encoding="utf-8", newline="\n")
        self.box.write("data/next.json", snapshot("2026-10-02", five()))
        with self.assertRaisesRegex(ValueError, "drift"):
            r5.append_pulse(self.box.root, "data/next.json", "P2")

    def test_unknown_status_value_is_rejected(self):
        bad = five()
        bad[0]["gates"][0]["status"] = "GREEN"
        with self.assertRaisesRegex(ValueError, "unknown gate status"):
            r5.rows_of(snapshot("d", bad))

    def test_cli_write_check_and_drift(self):
        self.box.add("P1", snapshot("2026-10-01", five()))
        with redirect_stdout(io.StringIO()):
            self.assertEqual(r5.main(["--check"], root=self.box.root), 1)
            self.assertEqual(r5.main(["--write"], root=self.box.root), 0)
            self.assertEqual(r5.main(["--check"], root=self.box.root), 0)
        csv_text = (self.box.root / "site/rolling5.csv").read_text(encoding="utf-8")
        self.assertEqual(len(csv_text.strip().splitlines()), 6)
        with redirect_stdout(io.StringIO()), self.assertRaises(SystemExit):
            r5.main(["--append-pulse", "data/x.json"], root=self.box.root)


class GoldenThreadSourceRedTests(unittest.TestCase):
    MAP = {"SOURCE_SHA": ["H01"], "BRANCH": ["@candidate_branch"],
           "REVIEW": ["H09"], "POSTMERGE": []}

    def thread(self, statuses, candidate=None):
        rows = r5.rows_of(snapshot("d", [row("o/x", 1, statuses, candidate=candidate)]))
        return r5.golden_thread(rows["o/x"], self.MAP)

    def test_candidate_branch_requires_branch_and_exact_sha(self):
        self.assertEqual(self.thread({"H01": "PASS"}, ("b", SHA_B))["position"], 2)
        self.assertEqual(self.thread({"H01": "PASS"}, ("b", "short"))["position"], 1)

    def test_fail_step_and_unmapped_step(self):
        t = self.thread({"H01": "PASS", "H09": "PASS"}, ("b", SHA_B))
        self.assertEqual((t["position"], t["first_break"]), (3, "POSTMERGE"))
        t = self.thread({"H01": "FAIL"})
        self.assertEqual(t["steps"][0]["status"], "FAIL")
        self.assertEqual(t["first_break"], "SOURCE_SHA")

    def test_fully_passed_thread_has_no_break(self):
        rows = r5.rows_of(snapshot("d", [row("o/x", 1, ALL_PASS, candidate=("b", SHA_B))]))
        t = r5.golden_thread(rows["o/x"], {"SOURCE_SHA": ["H01"],
                                            "BRANCH": ["@candidate_branch"]})
        self.assertEqual((t["position"], t["of"], t["first_break"]), (2, 2, None))

    def test_dependents_closure_is_transitive(self):
        closure = r5.dependents({"A": [], "B": ["A"], "C": ["B"], "D": []})
        self.assertEqual(closure["A"], {"B", "C"})
        self.assertEqual(closure["D"], set())

    def test_source_red_ranks_common_cause_and_edge_weight(self):
        policy = json.loads((ROOT / "data" / "ROLLING5_POLICY.json").read_text(encoding="utf-8"))
        rows = r5.rows_of(snapshot("d", five({
            "o/r1": {"H08": "FAIL", "H05": "FAIL"}, "o/r2": {"H08": "FAIL"},
            "o/r3": {"H08": "FAIL"}, "o/r4": {"H01": "PASS"}})))
        edges = [{"from": "o/r1", "to": "o/r5", "state": "AUTHORITY_BOUND"},
                 {"from": "o/r2", "to": "o/r5", "state": "REFERENCE_ONLY"}]
        red = r5.source_red(rows, edges, policy)
        self.assertEqual(red["core_focus"], "H08")
        top = red["ranked_gates"][0]
        self.assertEqual((top["repo_count"], top["class"]), (3, "COMMON_CAUSE"))
        self.assertEqual(red["ranked_gates"][1]["class"], "LOCAL")
        first = red["instances"][0]
        self.assertEqual((first["repo"], first["edge_score"]), ("o/r1", 2))
        self.assertIn("H12", first["blocks"])

    def test_passing_dependents_are_not_counted_as_blocked(self):
        policy = json.loads((ROOT / "data" / "ROLLING5_POLICY.json").read_text(encoding="utf-8"))
        statuses = dict(ALL_PASS, H08="FAIL")
        rows = r5.rows_of(snapshot("d", [row("o/x", 1, statuses)]))
        inst = r5.source_red(rows, [], policy)["instances"][0]
        self.assertEqual(inst["blocks"], [])
        self.assertEqual(r5.source_red({}, [], policy)["core_focus"], None)


if __name__ == "__main__":
    unittest.main()
