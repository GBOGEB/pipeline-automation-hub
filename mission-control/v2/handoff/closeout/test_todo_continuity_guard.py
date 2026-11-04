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
             "intent_count_reconstructed": len(intents), "action_count_reconstructed": len(actions),
             "security_waiver": False, "authority_transfer": False,
             "full_chat_message_count": None, "full_chat_prompt_count": None,
             "release_gate": "INDEPENDENT_PR_AND_MAIN_ADMISSION"}
    ledger = {"schema": "missioncontrol.cp_close.semantic_ledger.v1",
              "actions": actions, "intents": intents, "decisions": [], "insights": [],
              "metrics": [], "prs": [], "issues": []}
    bd = {"schema": "missioncontrol.cp_close.bd_projection.v1", "source_sha256": BD_SHA,
          "read_only_historical": True, "authority_transfer": False,
          "new_canonical_bd_items": 0, "focus": [{"id": "CPQ-001"}], "global_item_count": 1}
    directory.mkdir(parents=True, exist_ok=True)
    blobs = {}
    for name, obj in (("STATE.json", state), ("INTENT_ACTION_LEDGER.json", ledger), ("BD_QUEUE_READONLY.json", bd)):
        content = (json.dumps(obj, sort_keys=True) + "\n").encode()
        (directory / name).write_bytes(content)
        blobs[name] = hashlib.sha256(content).hexdigest()
    manifest = {"schema": "missioncontrol.cp_close.manifest.v1", "session_alias": alias,
                "authority_transfer": False, "verbatim_transcript_claim": False,
                "main_merge_admission": "INDEPENDENT_REVIEW_REQUIRED", "observed_main_sha": SHA,
                "canonical_bd_sha256": BD_SHA, "member_sha256": blobs}
    (directory / "MANIFEST.json").write_text(json.dumps(manifest, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    return mod.load_packet(directory)


def sidecar(before, after):
    return {"schema": mod.LINK_SCHEMA,
            "from_session": before["alias"], "to_session": after["alias"],
            "from_manifest_sha256": before["manifest_digest"],
            "to_manifest_sha256": after["manifest_digest"],
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
        links = sidecar(self.before, a)
        links["revisions"] = [{"kind": "action", "id": "SC-A001", "reason": "Owner reassigned",
                               "evidence_url": "https://github.com/GBOGEB/pipeline-automation-hub/issues/358"}]
        self.assertEqual("PASS_LINEAGE_ONLY_NOT_ADMISSION", mod.reconcile(self.before, a, links)["acceptance"])

    def test_action_evidence_url_deletion_requires_revision_same_session(self):
        acts = copy.deepcopy(list(self.before["actions"].values()))
        acts[0]["evidence_urls"] = ["https://github.com/GBOGEB/pipeline-automation-hub/issues/358"]
        first = packet(self.root / "evidence_before", actions=acts)
        acts[0]["evidence_urls"] = []
        second = packet(self.root / "evidence_after", actions=acts)
        report = mod.reconcile(first, second)
        self.assertEqual(["SC-A001"], report["unproven_semantic_revisions"])
        self.assertEqual("HOLD_LINEAGE_GAPS", report["acceptance"])

    def test_action_evidence_rewrite_requires_source_cross_session(self):
        acts = copy.deepcopy(list(self.before["actions"].values()))
        acts[0]["evidence_urls"] = ["https://github.com/GBOGEB/pipeline-automation-hub/issues/358"]
        later = packet(self.root / "evidence_after", alias="CP-NEXT-20261104", actions=acts)
        links = sidecar(self.before, later)
        report = mod.reconcile(self.before, later, links)
        self.assertIn("action:SC-A001>SC-A001", report["unproven_semantic_revisions"])
        links["action_links"][0]["revision_reason"] = "New evidence attached"
        links["action_links"][0]["revision_evidence_url"] = "https://github.com/GBOGEB/pipeline-automation-hub/issues/358"
        self.assertEqual("PASS_LINEAGE_ONLY_NOT_ADMISSION", mod.reconcile(self.before, later, links)["acceptance"])

    def test_cross_session_intent_source_class_rewrite_requires_revision(self):
        its = copy.deepcopy(list(self.before["intents"].values()))
        its[0]["source_class"] = "SOURCE_BOUND_REFERENCE"
        later = packet(self.root / "source_class_after", alias="CP-NEXT-20261104", intents=its)
        links = sidecar(self.before, later)
        report = mod.reconcile(self.before, later, links)
        self.assertIn("intent:SC-I001>SC-I001", report["unproven_semantic_revisions"])
        links["intent_links"][0]["revision_reason"] = "Reclassified after authenticated source"
        links["intent_links"][0]["revision_evidence_url"] = "https://github.com/GBOGEB/pipeline-automation-hub/issues/358"
        self.assertEqual("PASS_LINEAGE_ONLY_NOT_ADMISSION", mod.reconcile(self.before, later, links)["acceptance"])


    def test_manifest_privacy_and_main_admission_markers_fail_closed(self):
        for key, bad in (("verbatim_transcript_claim", True),
                         ("authority_transfer", True),
                         ("main_merge_admission", "ADMITTED"),
                         ("verbatim_transcript_claim", None)):
            with self.subTest(field=key, value=bad):
                first = packet(self.root / ("manifest_" + key + "_" + str(bad)))
                manifestfile = self.root / ("manifest_" + key + "_" + str(bad)) / "MANIFEST.json"
                doc = json.loads(manifestfile.read_text(encoding="utf-8"))
                if bad is None:
                    doc.pop(key)
                else:
                    doc[key] = bad
                manifestfile.write_text(json.dumps(doc) + "\n", encoding="utf-8", newline="\n")
                with self.assertRaisesRegex(ValueError, "manifest/authority/privacy"):
                    mod.load_packet(manifestfile.parent)

    def test_digest_valid_state_privacy_invariant_fail_closed(self):
        for key, bad in (("security_waiver", True), ("authority_transfer", True),
                         ("full_chat_prompt_count", 4), ("full_chat_message_count", 5),
                         ("release_gate", "ADMITTED"), ("security_waiver", None)):
            with self.subTest(field=key, value=bad):
                source = packet(self.root / ("state_" + key + "_" + str(bad)))
                directory = self.root / ("state_" + key + "_" + str(bad))
                statefile = directory / "STATE.json"
                state = json.loads(statefile.read_text(encoding="utf-8"))
                if bad is None:
                    state.pop(key)
                else:
                    state[key] = bad
                raw = (json.dumps(state) + "\n").encode("utf-8")
                statefile.write_bytes(raw)
                manifestfile = directory / "MANIFEST.json"
                doc = json.loads(manifestfile.read_text(encoding="utf-8"))
                doc["member_sha256"]["STATE.json"] = hashlib.sha256(raw).hexdigest()
                manifestfile.write_text(json.dumps(doc) + "\n", encoding="utf-8", newline="\n")
                with self.assertRaisesRegex(ValueError, "privacy/non-admission"):
                    mod.load_packet(directory)

    def test_digest_valid_bd_non_authority_fail_closed(self):
        for key, bad in (("authority_transfer", True), ("new_canonical_bd_items", 1)):
            with self.subTest(field=key):
                directory = self.root / ("bd_" + key)
                packet(directory)
                bdfile = directory / "BD_QUEUE_READONLY.json"
                bd = json.loads(bdfile.read_text(encoding="utf-8"))
                bd[key] = bad
                raw = (json.dumps(bd) + "\n").encode("utf-8")
                bdfile.write_bytes(raw)
                manifestfile = directory / "MANIFEST.json"
                m = json.loads(manifestfile.read_text(encoding="utf-8"))
                m["member_sha256"]["BD_QUEUE_READONLY.json"] = hashlib.sha256(raw).hexdigest()
                manifestfile.write_text(json.dumps(m) + "\n", encoding="utf-8", newline="\n")
                with self.assertRaisesRegex(ValueError, "privacy/non-admission"):
                    mod.load_packet(directory)

    def test_absent_canonical_bd_digest_rejected(self):
        path = self.root / "before" / "MANIFEST.json"
        m = json.loads(path.read_text(encoding="utf-8"))
        m.pop("canonical_bd_sha256")
        path.write_text(json.dumps(m) + "\n", encoding="utf-8", newline="\n")
        with self.assertRaisesRegex(ValueError, "canonical BD provenance"):
            mod.load_packet(self.root / "before")

    def test_invalid_matching_bd_digest_rejected(self):
        bdfile = self.root / "before" / "BD_QUEUE_READONLY.json"
        bd = json.loads(bdfile.read_text(encoding="utf-8"))
        bd["source_sha256"] = "invalid-but-equal"
        raw = (json.dumps(bd) + "\n").encode("utf-8")
        bdfile.write_bytes(raw)
        manifestfile = self.root / "before" / "MANIFEST.json"
        m = json.loads(manifestfile.read_text(encoding="utf-8"))
        m["canonical_bd_sha256"] = "invalid-but-equal"
        m["member_sha256"]["BD_QUEUE_READONLY.json"] = hashlib.sha256(raw).hexdigest()
        manifestfile.write_text(json.dumps(m) + "\n", encoding="utf-8", newline="\n")
        with self.assertRaisesRegex(ValueError, "canonical BD provenance"):
            mod.load_packet(self.root / "before")

    def test_cross_session_sidecar_bound_to_both_packet_digests(self):
        first = packet(self.root / "digest_first", alias="CP-NEXT-20261104")
        links = sidecar(self.before, first)
        changed_actions = copy.deepcopy(list(first["actions"].values()))
        changed_actions[0]["summary"] = "Newer packet uses same session alias"
        latest = packet(self.root / "digest_latest", alias="CP-NEXT-20261104", actions=changed_actions)
        with self.assertRaisesRegex(ValueError, "packet digest mismatch"):
            mod.reconcile(self.before, latest, links)
        links.pop("to_manifest_sha256")
        with self.assertRaisesRegex(ValueError, "packet digest mismatch"):
            mod.reconcile(self.before, first, links)

    def test_three_to_one_supersession_order_invariant(self):
        old_actions = copy.deepcopy(list(self.before["actions"].values()))
        old_actions[1]["depends_on"] = []
        extra = copy.deepcopy(old_actions[0])
        extra["id"] = "SC-A003"
        old_actions.append(extra)
        earlier = packet(self.root / "three_old", actions=old_actions)
        successor = packet(self.root / "one_new", alias="CP-NEXT-20261104",
                           actions=[copy.deepcopy(old_actions[0])],
                           intents=[{"id": "SC-I001", "summary": "Original intent",
                                     "actions": ["SC-A001"], "source_class": "USER_VISIBLE_RECONSTRUCTED"}])
        links = sidecar(earlier, successor)
        links["action_links"][1]["to"] = "SC-A001"
        links["action_links"][1]["disposition"] = "SUPERSEDED_WITH_LINEAGE"
        links["action_links"].append({"from": "SC-A003", "to": "SC-A001", "disposition": "CONTINUED",
                                      "evidence_url": "https://github.com/GBOGEB/pipeline-automation-hub/issues/358"})
        original = mod.reconcile(earlier, successor, links)
        links["action_links"].reverse()
        reversed_order = mod.reconcile(earlier, successor, links)
        self.assertEqual(original, reversed_order)
        self.assertEqual("HOLD_LINEAGE_GAPS", original["acceptance"])

    def test_intent_provenance_field_change_blocks_without_revision(self):
        its = copy.deepcopy(list(self.before["intents"].values()))
        its[0]["original_chat_message_id"] = "declared-but-not-verified"
        later = packet(self.root / "intent_provenance_after", alias="CP-NEXT-20261104", intents=its)
        links = sidecar(self.before, later)
        report = mod.reconcile(self.before, later, links)
        self.assertEqual(["intent:SC-I001>SC-I001"], report["unproven_semantic_revisions"])
        self.assertEqual("HOLD_LINEAGE_GAPS", report["acceptance"])

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
        r = mod.reconcile(self.before, a, sidecar(self.before, a))
        self.assertEqual("PASS_LINEAGE_ONLY_NOT_ADMISSION", r["acceptance"])
        self.assertFalse(r["complete_transcript_certified"])

    def test_cross_session_duplicate_source_mapping_rejected(self):
        a = packet(self.root / "after", alias="CP-NEXT-20261104")
        links = sidecar(self.before, a)
        links["action_links"].append(links["action_links"][0])
        with self.assertRaisesRegex(ValueError, "duplicate"):
            mod.reconcile(self.before, a, links)

    def test_unmatched_revision_id_cannot_clear_a_hold(self):
        acts = copy.deepcopy(list(self.before["actions"].values()))
        acts[0]["owner"] = "OTHER"
        a = packet(self.root / "after", actions=acts)
        links = sidecar(self.before, a)
        links["revisions"] = [{"kind": "action", "id": "SC-A999", "reason": "false claim",
                               "evidence_url": "https://github.com/GBOGEB/pipeline-automation-hub/issues/358"}]
        with self.assertRaisesRegex(ValueError, "unmatched revision"):
            mod.reconcile(self.before, a, links)

    def test_cross_session_semantic_rewrite_requires_decision_receipt(self):
        acts = copy.deepcopy(list(self.before["actions"].values()))
        acts[0]["done_when"] = "Scope reduced silently"
        a = packet(self.root / "after", alias="CP-NEXT-20261104", actions=acts)
        links = sidecar(self.before, a)
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
        links = sidecar(self.before, a)
        self.assertIn("action:SC-A002>SC-A002", mod.reconcile(self.before, a, links)["unproven_semantic_revisions"])

    def test_archive_closed_without_successor_does_not_erase_original(self):
        acts = copy.deepcopy(list(self.before["actions"].values()))[:1]
        its = copy.deepcopy(list(self.before["intents"].values()))
        its[0]["actions"] = ["SC-A001"]
        a = packet(self.root / "after", alias="CP-NEXT-20261104", actions=acts, intents=its)
        links = sidecar(self.before, a)
        links["action_links"][1]["disposition"] = "ARCHIVED_CLOSED"
        links["action_links"][1]["to"] = None
        r = mod.reconcile(self.before, a, links)
        self.assertEqual("PASS_LINEAGE_ONLY_NOT_ADMISSION", r["acceptance"])
        self.assertIn("SC-A002", r["historical_action_ids"])
        self.assertIsNone(r["accepted_distinct_root_closures"])

    def test_many_to_one_continued_rejected(self):
        a = packet(self.root / "after", alias="CP-NEXT-20261104")
        links = sidecar(self.before, a)
        links["action_links"][1]["to"] = "SC-A001"
        with self.assertRaisesRegex(ValueError, "many-to-one"):
            mod.reconcile(self.before, a, links)

    def test_unproven_archive_of_open_action_rejected(self):
        a = packet(self.root / "after", alias="CP-NEXT-20261104")
        links = sidecar(self.before, a)
        links["action_links"][0]["disposition"] = "ARCHIVED_CLOSED"
        links["action_links"][0]["to"] = None
        with self.assertRaisesRegex(ValueError, "archive"):
            mod.reconcile(self.before, a, links)

    def test_unowned_private_url_does_not_authorize_link(self):
        a = packet(self.root / "after", alias="CP-NEXT-20261104")
        links = sidecar(self.before, a)
        links["action_links"][0]["evidence_url"] = "https://example.org/private"
        with self.assertRaisesRegex(ValueError, "source-bound"):
            mod.reconcile(self.before, a, links)

    def test_tampered_member_rejected(self):
        p = self.root / "before" / "INTENT_ACTION_LEDGER.json"
        p.write_text(p.read_text(encoding="utf-8") + "\n", encoding="utf-8", newline="\n")
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
        p.write_text('{"id":"one","id":"two"}', encoding="utf-8", newline="\n")
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
        self.assertEqual("PASS_LINEAGE_ONLY_NOT_ADMISSION", json.loads(out.read_text(encoding="utf-8"))["acceptance"])

    def test_cli_unmapped_session_fails_with_exit_two(self):
        packet(self.root / "after", alias="CP-NEXT-20261104")
        out = self.root / "out" / "hold.json"
        rc = mod.main(["--before", str(self.root / "before"),
                       "--after", str(self.root / "after"), "--out", str(out)])
        self.assertEqual(2, rc)
        self.assertEqual("HOLD_LINEAGE_GAPS", json.loads(out.read_text(encoding="utf-8"))["acceptance"])

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
