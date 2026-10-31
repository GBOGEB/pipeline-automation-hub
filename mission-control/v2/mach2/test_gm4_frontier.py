"""GM-IV slot map, lease disjointness and return-receipt shape. No GitHub calls."""
import copy
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gm4_frontier as g4

HUB_A = "a" * 40
HUB_B = "b" * 40
BLOBS = ("c" * 40, "d" * 40)


def fake_fetch(heads):
    def fetch(route):
        parts = route.split("/")
        if len(parts) == 3:
            return {"default_branch": "main"}
        repo, ref = "/".join(parts[1:3]), parts[4]
        return {"sha": heads.get(repo, ref) if ref == "main" else ref}
    return fetch


def series(slot_map, name, hub, heads=None):
    pinned = {s["candidate_repository"]: s["target_sha"] for s in slot_map["slots"]}
    return [g4.observe_slot(s, name, hub, BLOBS, fake_fetch({**pinned, **(heads or {})}),
                            clock=lambda: "2026-10-29T10:00:00Z") for s in slot_map["slots"]]


class SlotMapTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.reg, cls.gov = g4.load_sources()
        cls.map = g4.build_slot_map(cls.reg, cls.gov)

    def test_eight_named_slots_from_canonical_sources(self):
        self.assertEqual([s["slot"] for s in self.map["slots"]], list(g4.SLOTS))
        self.assertEqual(len({s["candidate_repository"] for s in self.map["slots"]}), 8)
        self.assertTrue(all(s["child_binding"] is None and s["assigned_worker"] is None
                            for s in self.map["slots"]))
        self.assertIsNone(self.map["authorized_workers"])

    def test_committed_slot_map_matches_sources(self):
        committed = json.loads((g4.BASE / g4.SLOT_MAP).read_text(encoding="utf-8"))
        self.assertEqual(committed, json.loads(json.dumps(self.map)))

    def test_canonical_child_binding_fails_closed(self):
        reg = copy.deepcopy(self.reg)
        next(m for m in reg["grand_missions"] if m["id"] == "GM-IV")["children"] = ["x"]
        with self.assertRaisesRegex(ValueError, "children must stay empty"):
            g4.build_slot_map(reg, self.gov)

    def test_gm_v_launch_fails_closed(self):
        reg = copy.deepcopy(self.reg)
        next(m for m in reg["grand_missions"] if m["id"] == "GM-V")["state"] = "ACTIVE"
        with self.assertRaisesRegex(ValueError, "HELD"):
            g4.build_slot_map(reg, self.gov)


class LeaseTests(unittest.TestCase):
    def setUp(self):
        reg, gov = g4.load_sources()
        self.map = g4.build_slot_map(reg, gov)

    def test_slot_leases_disjoint(self):
        x = g4.check_leases(self.map)
        self.assertEqual((x["result"], x["pairs_checked"], x["overlapping_pairs"]),
                         ("PASS_DISJOINT", 28, 0))

    def test_shared_reads_do_not_conflict(self):
        reads = [set(s["lease"]["read_paths"]) for s in self.map["slots"]]
        self.assertTrue(set.intersection(*reads))
        g4.check_leases(self.map)

    def test_duplicate_write_lease_rejected(self):
        self.map["slots"][1]["lease"]["write_paths"] = list(self.map["slots"][0]["lease"]["write_paths"])
        with self.assertRaisesRegex(ValueError, "overlapping slot leases"):
            g4.check_leases(self.map)

    def test_parent_prefix_write_rejected(self):
        self.map["slots"][2]["lease"]["write_paths"] = [f"{g4.HUB}/{g4.RETURNS}"]
        with self.assertRaisesRegex(ValueError, "overlapping slot leases"):
            g4.check_leases(self.map)

    def test_write_into_another_slots_read_rejected(self):
        self.map["slots"][3]["lease"]["write_paths"].append(self.map["slots"][4]["candidate_repository"])
        with self.assertRaisesRegex(ValueError, "overlapping slot leases"):
            g4.check_leases(self.map)

    def test_write_outside_wave_rejected(self):
        self.map["slots"][5]["lease"]["write_paths"] = [f"{g4.HUB}/mission-control/v2/x"]
        with self.assertRaisesRegex(ValueError, "outside the wave lease"):
            g4.check_leases(self.map)

    def test_sibling_wave_overlap_rejected(self):
        self.map["sibling_leases"] = {"X": [g4.RETURNS + "/GM-IV-F07"]}
        with self.assertRaisesRegex(ValueError, "sibling wave"):
            g4.check_leases(self.map)

    def test_unsafe_path_rejected(self):
        self.map["slots"][0]["lease"]["read_paths"].append("GBOGEB/x/../y")
        with self.assertRaisesRegex(ValueError, "unsafe"):
            g4.check_leases(self.map)


class ReceiptTests(unittest.TestCase):
    def setUp(self):
        reg, gov = g4.load_sources()
        self.map = g4.build_slot_map(reg, gov)
        self.r = series(self.map, "A", HUB_A)[0]

    def test_shape_and_not_verified_fields(self):
        g4.validate_receipt(self.r, self.map)
        self.assertEqual(set(self.r), g4.RECEIPT_KEYS)
        self.assertEqual(self.r["DoV"], "NOT_VERIFIED")
        self.assertTrue(set(g4.NULLABLE) <= set(self.r["not_verified"]))
        self.assertTrue(self.r["target_sha_fetchable"])

    def bad(self, pattern, **change):
        with self.assertRaisesRegex(ValueError, pattern):
            g4.validate_receipt(dict(self.r, **change), self.map)

    def test_short_sha_rejected(self):
        self.bad("not an exact sha", hub_head_sha="37c4681a")

    def test_wrong_repo_rejected(self):
        self.bad("repo != slot map", source_owner_repo="GBOGEB/other")

    def test_unknown_slot_rejected(self):
        self.bad("unknown slot", slot="GM-IV-F09")

    def test_forged_owner_disposition_rejected(self):
        self.bad("forged owner", owner_disposition="ACCEPT")

    def test_invented_run_id_rejected(self):
        self.bad("both set and NOT_VERIFIED", run_id=123)

    def test_null_without_not_verified_rejected(self):
        self.bad("missing without NOT_VERIFIED", not_verified=["DoV"])

    def test_child_binding_claim_rejected(self):
        self.bad("claims authority", children_bound=True)

    def test_extra_key_rejected(self):
        self.bad("receipt keys", queue_p95=1.0)

    def test_head_flag_must_match(self):
        self.bad("head movement", head_moved_since_pin=True)

    def test_two_series_distinct_hub_heads(self):
        moved = {"GBOGEB/ABACUS": "e" * 40}
        x = g4.evaluate_series(series(self.map, "A", HUB_A) + series(self.map, "B", HUB_B, moved), self.map)
        self.assertTrue(x["distinct_hub_heads"])
        self.assertEqual(x["frontier_heads_changed_between_series"], ["GM-IV-F05"])
        d = g4.dov(self.map, x)
        self.assertEqual(d["two_independent_repeat_series_at_pinned_new_heads"]["independence"], "NOT_VERIFIED")
        self.assertEqual(d["nondegrading_proof_yield_and_queue_p95"], "NOT_VERIFIED")
        self.assertEqual(d["admission"], "HOLD")

    def test_same_hub_head_is_not_a_repeat(self):
        x = g4.evaluate_series(series(self.map, "A", HUB_A) + series(self.map, "B", HUB_A), self.map)
        self.assertFalse(x["distinct_hub_heads"])

    def test_duplicate_receipt_rejected(self):
        with self.assertRaisesRegex(ValueError, "duplicate receipt"):
            g4.evaluate_series(series(self.map, "A", HUB_A) * 2, self.map)

    def test_committed_receipts_valid(self):
        receipts = g4.read_receipts()
        if receipts:
            g4.evaluate_series(receipts, self.map)


if __name__ == "__main__":
    unittest.main()


def test_zz_canary_g_pah():
    assert False, "red canary: proves CI collects this family"
