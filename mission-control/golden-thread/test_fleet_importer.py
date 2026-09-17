import copy
import json
import unittest
from pathlib import Path

import fleet_importer as fi
import golden_thread as gt

HERE = Path(__file__).resolve().parent
LEDGER_FIXTURE = HERE / "fixtures" / "COLD_TAIL_BOOTSTRAP_LEDGER_v1.json"


class FleetImporterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ledger = json.loads(LEDGER_FIXTURE.read_text(encoding="utf-8"))
        cls.scope = {
            "schema": fi.SCOPE_SCHEMA,
            "read_only": True,
            "max_items": 2,
            "include_pull_requests": False,
            "sources": [
                {"repository": "GBOGEB/example", "issue_numbers": [1, 2]},
            ],
            "classification_credit": 0,
            "engineering_credit": 0,
            "compliance_credit": 0,
            "release_credit": 0,
            "visual_fidelity_credit": False,
            "authority_transfer": False,
        }

    def issue(self, number, title=None, updated_at=None, pull_request=False):
        raw = {
            "id": 1000 + number,
            "node_id": f"NODE-{number}",
            "number": number,
            "title": title or f"Issue {number}",
            "state": "open",
            "state_reason": None,
            "created_at": "2026-09-01T00:00:00Z",
            "updated_at": updated_at or "2026-09-16T00:00:00Z",
            "closed_at": None,
            "html_url": f"https://github.com/GBOGEB/example/issues/{number}",
            "url": f"https://api.github.com/repos/GBOGEB/example/issues/{number}",
            "labels": [{"name": "triage"}],
            "assignees": [{"login": "GBOGEB"}],
            "milestone": None,
            "body": f"body-{number}",
        }
        if pull_request:
            raw["pull_request"] = {"url": "https://api.github.com/example"}
        return fi.normalize_issue("GBOGEB/example", raw)

    def test_exact_snapshot_replay_adds_no_event(self):
        snapshots = [self.issue(1), self.issue(2)]
        registry = fi.empty_registry(self.scope)
        ledger1, registry1, receipt1 = fi.import_snapshots(
            self.ledger,
            registry,
            self.scope,
            snapshots,
            recorded_at="2026-09-17T02:20:00Z",
        )
        self.assertEqual(receipt1["added_event_count"], 2)
        self.assertEqual(len(ledger1["events"]), len(self.ledger["events"]) + 2)
        ledger2, registry2, receipt2 = fi.import_snapshots(
            ledger1,
            registry1,
            self.scope,
            snapshots,
            recorded_at="2026-09-17T02:21:00Z",
        )
        self.assertEqual(receipt2["added_event_count"], 0)
        self.assertEqual(receipt2["replayed_snapshot_count"], 2)
        self.assertEqual(ledger2, ledger1)
        self.assertEqual(registry2, registry1)

    def test_changed_snapshot_creates_successor_transaction(self):
        first = self.issue(1)
        registry = fi.empty_registry(self.scope)
        ledger1, registry1, _ = fi.import_snapshots(
            self.ledger,
            registry,
            self.scope,
            [first],
            recorded_at="2026-09-17T02:20:00Z",
        )
        changed = self.issue(1, title="Issue 1 changed", updated_at="2026-09-17T02:22:00Z")
        ledger2, registry2, receipt = fi.import_snapshots(
            ledger1,
            registry1,
            self.scope,
            [changed],
            recorded_at="2026-09-17T02:23:00Z",
        )
        self.assertEqual(receipt["added_event_count"], 1)
        history = registry2["sources"]["GBOGEB/example#1"]["history"]
        self.assertEqual(len(history), 2)
        self.assertEqual(history[1]["parent_transaction_id"], history[0]["transaction_id"])
        self.assertNotEqual(history[1]["transaction_id"], history[0]["transaction_id"])
        self.assertEqual(len(ledger2["events"]), len(self.ledger["events"]) + 2)

    def test_import_is_observation_only_without_classification_credit(self):
        snapshot = self.issue(1)
        ledger, registry, receipt = fi.import_snapshots(
            self.ledger,
            fi.empty_registry(self.scope),
            self.scope,
            [snapshot],
            recorded_at="2026-09-17T02:20:00Z",
        )
        event = ledger["events"][-1]
        self.assertEqual(event["actor"], "MissionControl.FleetImporter")
        self.assertEqual(event["authority_domain"], "GBOGEB/example")
        self.assertTrue(event["non_compensating_preserved"])
        self.assertEqual(event["payload"]["import_state"], "UNCLASSIFIED_READER_REQUIRED")
        self.assertEqual(receipt["classification_credit"], 0)
        self.assertEqual(receipt["source_write_count"], 0)
        self.assertFalse(receipt["visual_fidelity_credit"])
        self.assertFalse(receipt["authority_transfer"])
        self.assertEqual(fi.verify_registry(registry, self.scope)["status"], "PASS")

    def test_out_of_scope_snapshot_fails_closed(self):
        other = fi.normalize_issue(
            "GBOGEB/other",
            {
                "id": 9,
                "node_id": "OTHER",
                "number": 9,
                "title": "Other",
                "state": "open",
                "created_at": "2026-09-01T00:00:00Z",
                "updated_at": "2026-09-16T00:00:00Z",
                "html_url": "https://github.com/GBOGEB/other/issues/9",
                "url": "https://api.github.com/repos/GBOGEB/other/issues/9",
            },
        )
        with self.assertRaises(fi.FleetImportError):
            fi.import_snapshots(
                self.ledger,
                fi.empty_registry(self.scope),
                self.scope,
                [other],
                recorded_at="2026-09-17T02:20:00Z",
            )

    def test_pull_request_fails_when_scope_excludes_prs(self):
        with self.assertRaises(fi.FleetImportError):
            fi.import_snapshots(
                self.ledger,
                fi.empty_registry(self.scope),
                self.scope,
                [self.issue(1, pull_request=True)],
                recorded_at="2026-09-17T02:20:00Z",
            )

    def test_registry_tamper_fails_closed(self):
        ledger, registry, _ = fi.import_snapshots(
            self.ledger,
            fi.empty_registry(self.scope),
            self.scope,
            [self.issue(1)],
            recorded_at="2026-09-17T02:20:00Z",
        )
        bad = copy.deepcopy(registry)
        bad["source_write_count"] = 1
        with self.assertRaises(fi.FleetImportError):
            fi.verify_registry(bad, self.scope)


if __name__ == "__main__":
    unittest.main()
