"""Offline CP.CLOSE continuity negative controls; no GitHub calls or dispatch."""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("todo_continuity_guard", HERE / "todo_continuity_guard.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

SHA = "a" * 40
BD_SHA = "b" * 64


def packet(directory: Path, alias="CP-DEMO-20261103", actions=None, intents=None):
    actions = copy.deepcopy(actions if actions is not None else [
        {"id": "SC-A001", "owner": "HUB", "state": "HOLD", "priority": "P0",
         "summary": "Immutable work", "done_when": "Independent owner review", "depends_on": [],
         "evidence_urls": []},
        {"id": "SC-A002", "owner": "HUB", "state": "DONE", "priority": "P1",
         "summary": "Historical work", "done_when": "Native proof", "depends_on": ["SC-A001"],
         "evidence_urls": []},
    ])
    intents = copy.deepcopy(intents if intents is not None else [
        {"id": "SC-I001", "summary": "Original intent", "actions": ["SC-A001", "SC-A002"],
         "source_class": "USER_VISIBLE_RECONSTRUCTED"},
    ])
    state = {"schema": "missioncontrol.cp_close.state.v1", "session_alias": alias,
             "source": {"observed_main_sha": SHA},
             "intent_count_reconstructed": len(intents), "action_count_reconstructed": len(actions)}
    ledger = {"schema": "missioncontrol.cp_close.semantic_ledger.v1",
              "actions": actions, "intents": intents, "decisions": [], "insights": [],
              "metrics": [], "prs": [], "issues": []}
    bd = {"schema": "missioncontrol.cp_close.bd_projection.v1", "source_sha256": BD_SHA,
          "read_only_historical": True, "focus": [{"id": "CPQ-001"}], "global_item_count": 1}
    directory.mkdir(parents=True, exist_ok=True)
    blobs = {}
    for name, obj in (("STATE.json", state), ("INTENT_ACTION_LEDGER.json", ledger), ("BD_QUEUE_READONLY.json", bd)):
        content = (json.dumps(obj, sort_keys=True) + "\n").encode()
        (directory / name).write_bytes(content)
        blobs[name] = hashlib.sha256(content).hexdigest()
    manifest = {"schema": "missioncontrol.cp_close.manifest.v1", "session_alias": alias,
                "authority_transfer": False, "observed_main_sha": SHA,
                "canonical_bd_sha256": BD_SHA, "member_sha256": blobs}
    (directory / "MANIFEST.json").write_text(json.dumps(manifest, sort_keys=True) + "\n")
    return mod.load_packet(directory)


def sidecar(old_alias, new_alias):
    return {"schema": mod.LINK_SCHEMA, "from_session": old_alias, "to_session": new_alias,
            "action_links": [
                {"from": "SC-A001", "to": "SC-A001", "disposition": "CONTINUED",
                 "evidence_url": "https://github.com/GBOGEB/pipeline-automation-hub/issues/358"},
                {"from": "SC-A002", "to": "SC-A002", "disposition": "CONTINUED",
                 "evidence_url": "https://github.com/GBOGEB/pipeline-automation-hub/issues/358"},
            ],
            "intent_links": [{"from": "SC-I001", "to": "SC-I001", "disposition": "CONTINUED",
                              "evidence_url": "https://github.com/GBOGEB/pipeline-automation-hub/issues/358"}],
            "revisions": []}


class TodoContinuityTests(unittest.TestCase):
    def setUp(self):
        self.t = tempfile.TemporaryDirectory()
        self.root = Path(self.t.name)
        self.before = packet(self.root / "before")

    def tearDown(self):
        self.t.cleanup()

    def test_stable_revision_passes_lineage_not_admission(self):
        a = packet(self.root / "after")
        report = mod.reconcile(self.before, a)
        self.assertEqual("PASS_LINEAGE_ONLY_NOT_ADMISSION", report["acceptance"])
        self.assertIsNone(report["accepted_distinct_root_closures"])
        self.assertFalse(report["merge_authorized"])
        self.assertEqual(report, mod.reconcile(self.before, a))

    def test_removed_action_is_not_silent(self):
        acts = copy.deepcopy(list(self.before["actions"].values()))[:1]
        intent = [{"id": "SC-I001", "summary": "Original intent", "actions": ["SC-A001"]}]
        a = packet(self.root / "after", actions=acts, intents=intent)
        r = mod.reconcile(self.before, a)
        self.assertEqual(["SC-A002"], r["unmapped_historical_actions"])
        self.assertEqual("HOLD_LINEAGE_GAPS", r["acceptance"])

    def test_changed_owner_requires_source_bound_revision(self):
        acts = copy.deepcopy(list(self.before["actions"].values()))
        acts[0]["owner"] = "OTHER"
        a = packet(self.root / "after", actions=acts)
        r = mod.reconcile(self.before, a)
        self.assertEqual(["SC-A001"], r["unproven_semantic_revisions"])
        self.assertEqual("HOLD_LINEAGE_GAPS", r["acceptance"])
        links = sidecar(self.before["alias"], a["alias"])
        links["revisions"] = [{"kind": "action", "id": "SC-A001", "reason": "Owner reassigned",
                               "evidence_url": "https://github.com/GBOGEB/pipeline-automation-hub/issues/358"}]
        self.assertEqual("PASS_LINEAGE_ONLY_NOT_ADMISSION", mod.reconcile(self.before, a, links)["acceptance"])

    def test_done_transition_is_not_accepted_closure(self):
        acts = copy.deepcopy(list(self.before["actions"].values()))
        acts[0]["state"] = "DONE"
        a = packet(self.root / "after", actions=acts)
        r = mod.reconcile(self.before, a)
        self.assertEqual(["SC-A001"], r["candidate_state_promotions_not_accepted"])
        self.assertEqual("HOLD_LINEAGE_GAPS", r["acceptance"])
        self.assertIsNone(r["accepted_distinct_root_closures"])

    def test_cross_session_identical_short_ids_do_not_auto_join(self):
        a = packet(self.root / "after", alias="CP-NEXT-20261104")
        r = mod.reconcile(self.before, a)
        self.assertEqual("HOLD_LINEAGE_GAPS", r["acceptance"])
        self.assertEqual(["SC-A001", "SC-A002"], r["unmapped_historical_actions"])
        self.assertEqual(["SC-I001"], r["unmapped_historical_intents"])

    def test_cross_session_all_historical_items_explicitly_linked(self):
        a = packet(self.root / "after", alias="CP-NEXT-20261104")
        r = mod.reconcile(self.before, a, sidecar(self.before["alias"], a["alias"]))
        self.assertEqual("PASS_LINEAGE_ONLY_NOT_ADMISSION", r["acceptance"])
        self.assertFalse(r["complete_transcript_certified"])

    def test_cross_session_duplicate_source_mapping_rejected(self):
        a = packet(self.root / "after", alias="CP-NEXT-20261104")
        links = sidecar(self.before["alias"], a["alias"])
        links["action_links"].append(links["action_links"][0])
        with self.assertRaisesRegex(ValueError, "duplicate"):
            mod.reconcile(self.before, a, links)

    def test_unmatched_revision_id_cannot_clear_a_hold(self):
        acts = copy.deepcopy(list(self.before["actions"].values()))
        acts[0]["owner"] = "OTHER"
        a = packet(self.root / "after", actions=acts)
        links = sidecar(self.before["alias"], a["alias"])
        links["revisions"] = [{"kind": "action", "id": "SC-A999", "reason": "false claim",
                               "evidence_url": "https://github.com/GBOGEB/pipeline-automation-hub/issues/358"}]
        with self.assertRaisesRegex(ValueError, "unmatched revision"):
            mod.reconcile(self.before, a, links)

    def test_cross_session_semantic_rewrite_requires_decision_receipt(self):
        acts = copy.deepcopy(list(self.before["actions"].values()))
        acts[0]["done_when"] = "Scope reduced silently"
        a = packet(self.root / "after", alias="CP-NEXT-20261104", actions=acts)
        links = sidecar(self.before["alias"], a["alias"])
        r = mod.reconcile(self.before, a, links)
        self.assertEqual("HOLD_LINEAGE_GAPS", r["acceptance"])
        self.assertIn("action:SC-A001>SC-A001", r["unproven_semantic_revisions"])
        links["action_links"][0]["revision_reason"] = "Owner decision adjusts DoD"
        links["action_links"][0]["revision_evidence_url"] = "https://github.com/GBOGEB/pipeline-automation-hub/issues/358"
        self.assertEqual("PASS_LINEAGE_ONLY_NOT_ADMISSION", mod.reconcile(self.before, a, links)["acceptance"])

    def test_cross_session_silent_dependency_loss_blocked(self):
        acts = copy.deepcopy(list(self.before["actions"].values()))
        acts[1]["depends_on"] = []
        a = packet(self.root / "after", alias="CP-NEXT-20261104", actions=acts)
        links = sidecar(self.before["alias"], a["alias"])
        self.assertIn("action:SC-A002>SC-A002", mod.reconcile(self.before, a, links)["unproven_semantic_revisions"])

    def test_archive_closed_without_successor_does_not_erase_original(self):
        acts = copy.deepcopy(list(self.before["actions"].values()))[:1]
        its = [{"id": "SC-I001", "summary": "Original intent", "actions": ["SC-A001"]}]
        a = packet(self.root / "after", alias="CP-NEXT-20261104", actions=acts, intents=its)
        links = sidecar(self.before["alias"], a["alias"])
        links["action_links"][1]["disposition"] = "ARCHIVED_CLOSED"
        links["action_links"][1]["to"] = None
        r = mod.reconcile(self.before, a, links)
        self.assertEqual("PASS_LINEAGE_ONLY_NOT_ADMISSION", r["acceptance"])
        self.assertIn("SC-A002", r["historical_action_ids"])
        self.assertIsNone(r["accepted_distinct_root_closures"])

    def test_many_to_one_continued_rejected(self):
        a = packet(self.root / "after", alias="CP-NEXT-20261104")
        links = sidecar(self.before["alias"], a["alias"])
        links["action_links"][1]["to"] = "SC-A001"
        with self.assertRaisesRegex(ValueError, "many-to-one"):
            mod.reconcile(self.before, a, links)

    def test_unproven_archive_of_open_action_rejected(self):
        a = packet(self.root / "after", alias="CP-NEXT-20261104")
        links = sidecar(self.before["alias"], a["alias"])
        links["action_links"][0]["disposition"] = "ARCHIVED_CLOSED"
        links["action_links"][0]["to"] = None
        with self.assertRaisesRegex(ValueError, "archive"):
            mod.reconcile(self.before, a, links)

    def test_unowned_private_url_does_not_authorize_link(self):
        a = packet(self.root / "after", alias="CP-NEXT-20261104")
        links = sidecar(self.before["alias"], a["alias"])
        links["action_links"][0]["evidence_url"] = "https://example.org/private"
        with self.assertRaisesRegex(ValueError, "source-bound"):
            mod.reconcile(self.before, a, links)

    def test_tampered_member_rejected(self):
        p = self.root / "before" / "INTENT_ACTION_LEDGER.json"
        p.write_text(p.read_text() + "\n")
        with self.assertRaisesRegex(ValueError, "drifted"):
            mod.load_packet(self.root / "before")

    def test_missing_manifest_member_rejected(self):
        (self.root / "before" / "STATE.json").unlink()
        with self.assertRaisesRegex(ValueError, "missing/linked"):
            mod.load_packet(self.root / "before")

    def test_unproven_nondone_status_transition_hold(self):
        acts = copy.deepcopy(list(self.before["actions"].values()))
        acts[0]["state"] = "IN_PR"
        a = packet(self.root / "after", actions=acts)
        r = mod.reconcile(self.before, a)
        self.assertEqual(["SC-A001"], r["unproven_state_transitions"])
        self.assertEqual("HOLD_LINEAGE_GAPS", r["acceptance"])

    def test_duplicate_json_fields_rejected(self):
        p = self.root / "duplicated.json"
        p.write_text('{"id":"one","id":"two"}', encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "duplicate JSON field"):
            mod.read_json(p)

    def test_symlink_manifest_member_rejected(self):
        p = self.root / "before" / "STATE.json"
        p.rename(self.root / "actual_state.json")
        try:
            p.symlink_to(self.root / "actual_state.json")
        except OSError:
            self.skipTest("symlink unavailable")
        with self.assertRaisesRegex(ValueError, "missing/linked"):
            mod.load_packet(self.root / "before")

    def test_deep_valid_dependency_dag_no_recursion_limit(self):
        graph = {}
        for n in range(1, 850):
            key = f"SC-A{n:03d}"
            graph[key] = {"state": "HOLD", "owner": "owner", "done_when": "native proof",
                          "depends_on": [f"SC-A{n-1:03d}"] if n > 1 else []}
        mod.check_dag(graph)

    def test_dag_orphan_rejected(self):
        acts = copy.deepcopy(list(self.before["actions"].values()))
        acts[0]["depends_on"] = ["SC-A999"]
        with self.assertRaisesRegex(ValueError, "orphan"):
            packet(self.root / "after", actions=acts)

    def test_dag_cycle_rejected(self):
        acts = copy.deepcopy(list(self.before["actions"].values()))
        acts[0]["depends_on"] = ["SC-A002"]
        with self.assertRaisesRegex(ValueError, "cycle"):
            packet(self.root / "after", actions=acts)

    def test_cli_stable_packet_exit_zero_with_written_receipt(self):
        packet(self.root / "after")
        out = self.root / "out" / "review.json"
        rc = mod.main(["--before", str(self.root / "before"),
                       "--after", str(self.root / "after"), "--out", str(out)])
        self.assertEqual(0, rc)
        self.assertEqual("PASS_LINEAGE_ONLY_NOT_ADMISSION", json.loads(out.read_text())["acceptance"])

    def test_cli_unmapped_session_fails_with_exit_two(self):
        packet(self.root / "after", alias="CP-NEXT-20261104")
        out = self.root / "out" / "hold.json"
        rc = mod.main(["--before", str(self.root / "before"),
                       "--after", str(self.root / "after"), "--out", str(out)])
        self.assertEqual(2, rc)
        self.assertEqual("HOLD_LINEAGE_GAPS", json.loads(out.read_text())["acceptance"])

    def test_bd_focus_drift_is_not_closure(self):
        a = packet(self.root / "after")
        a["bd"]["focus"] = []
        r = mod.reconcile(self.before, a)
        self.assertEqual(["CPQ-001"], r["bd_focus_removed_projection_only"])
        self.assertIsNone(r["bd_global_root_closure_inference"])


class NativePacketReplayTests(unittest.TestCase):
    """Committed sanitized CP.CLOSE records: native required, local optional.

    The workflow sets CP_TODO_REQUIRE_REAL_PACKET=1, so missing history
    cannot be reported as a passing green suite on a partial checkout.
    """
    PACKET_NAMES = (
        "CP-FED-TERMINAL-20261017",
        "CP-QPS-UNLOCK-RETIRE-20261026",
    )

    def sources(self):
        import os
        root = HERE / "records"
        absent = [name for name in self.PACKET_NAMES
                  if not (root / name / "MANIFEST.json").is_file()]
        if absent:
            if os.environ.get("CP_TODO_REQUIRE_REAL_PACKET") == "1":
                self.fail("native CP.CLOSE packet(s) missing: " + ", ".join(absent))
            self.skipTest("local pilot has no committed full-repository CP.CLOSE packets")
        return [mod.load_packet(root / name) for name in self.PACKET_NAMES]

    def test_committed_record_digests_and_population_preserved(self):
        earlier, later = self.sources()
        self.assertEqual(earlier["alias"], self.PACKET_NAMES[0])
        self.assertEqual(later["alias"], self.PACKET_NAMES[1])
        self.assertEqual((len(earlier["actions"]), len(earlier["intents"])), (9, 5))
        self.assertEqual((len(later["actions"]), len(later["intents"])), (9, 5))
        for packet_obj in (earlier, later):
            self.assertEqual(40, len(packet_obj["source_sha"]))
            self.assertEqual(64, len(packet_obj["manifest_digest"]))

    def test_unmapped_real_session_transition_remains_hold(self):
        earlier, later = self.sources()
        report = mod.reconcile(earlier, later)
        self.assertEqual("HOLD_LINEAGE_GAPS", report["acceptance"])
        self.assertEqual(len(earlier["actions"]), len(report["unmapped_historical_actions"]))
        self.assertEqual(len(earlier["intents"]), len(report["unmapped_historical_intents"]))
        self.assertIsNone(report["accepted_distinct_root_closures"])
        self.assertFalse(report["merge_authorized"])

    def test_exact_real_packet_self_replay_is_lineage_only(self):
        earlier, later = self.sources()
        for source in (earlier, later):
            report = mod.reconcile(source, source)
            self.assertEqual("PASS_LINEAGE_ONLY_NOT_ADMISSION", report["acceptance"])
            self.assertIsNone(report["weighted_closure"])
            self.assertFalse(report["dispatch_authorized"])


if __name__ == "__main__":
    unittest.main()
