"""Negative and positive controls for read-only reverse-pressure allocation."""
from __future__ import annotations

import copy
import json
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import reverse_pressure as m


def data():
    ids = [
        ("FORMAT", "DOW_BLACK_ISORT", "P1", 2),
        ("SECURITY", "DOW_BANDIT_SAFETY", "P0", 3),
        ("PY_COMPAT", "PY310_DEPENDENCY", "P1", 4),
        ("WORKFLOW_POLICY", "GOVERNANCE_CANONICAL", "P0", 4),
        ("COVERAGE_MODE", None, "P1", 2),
        ("REPLAY", "FOUR_HOP", "P0", 1),
    ]
    families = [{"id": alias, "priority": tier} for _, alias, tier, _ in ids if alias]
    owners = []
    observations = []
    serial = 0
    for root_id, alias, tier, n in ids:
        links = []
        for _ in range(n):
            serial += 1
            ref = f"GBOGEB/ABACUS#{100 + serial}"
            links.append(ref)
            observations.append({"repository": "GBOGEB/ABACUS", "pr": 100+serial,
                                 "head_sha": f"{serial:040x}", "state": "open", "failed": 1})
        owners.append({"id": root_id, "canonical": links[0],
                       "related": links[1:],
                       "status": "MULTIPLE_OVERLAPPING_REPAIRS" if root_id == "WORKFLOW_POLICY"
                       else "REPAIR_OPEN"})
    return {"families": families}, {"all_observations": observations, "root_owners": owners}


def isolated(pulse, census, delta=None):
    with patch.dict(sys.modules, {
        "cbq_ch_bd_render": types.SimpleNamespace(validate=lambda a: None),
        "cbq_impact_census": types.SimpleNamespace(validate=lambda a, b: None),
    }):
        return m.analyze(pulse, census, delta)


class ReversePressureTests(unittest.TestCase):
    def test_priority_and_reverse_reach(self):
        a, b = data()
        result = isolated(a, b)
        rows = result["root_owners"]
        self.assertEqual([r["root_id"] for r in rows],
                         ["WORKFLOW_POLICY", "SECURITY", "REPLAY",
                          "PY_COMPAT", "COVERAGE_MODE", "FORMAT"])
        self.assertEqual([r["pressure_score"] for r in rows], [12, 9, 3, 8, 4, 4])
        self.assertEqual(sum(r["descriptive_pressure_share"] for r in rows), 1.0)
        self.assertEqual(6, result["metrics"]["owner_clusters"])
        self.assertEqual(0, result["metrics"]["accepted_engineering_roots_closed"])

    def test_statistics_do_not_self_promote(self):
        p, c = data()
        r = isolated(p, c)
        self.assertFalse(r["ranking_diagnostics"]["pca_ready"])
        self.assertFalse(r["ranking_diagnostics"]["bt_ready"])
        self.assertIsNone(r["ranking_diagnostics"]["pca_loadings"])
        self.assertIsNone(r["ranking_diagnostics"]["bt_strengths"])
        self.assertFalse(r["worker_proposals"]["dispatch_authorized"])
        self.assertFalse(r["worker_proposals"]["mutation_authorized"])
        self.assertIsNone(r["metrics"]["rex_verified_reopens"])

    def test_changed_sha_is_not_source_matched(self):
        p, c = data()
        first = c["all_observations"][0]
        delta = self.make_delta([first])
        delta["rows"][0]["head_sha"] = "f" * 40
        r = isolated(p, c, delta)
        row = next(r for r in r["root_owners"] if r["root_id"] == "FORMAT")
        self.assertEqual(1, len(row["changed_head_refs"]))
        self.assertFalse(row["source_matched_for_delta"])

    def test_partial_recheck_stays_partial(self):
        p, c = data()
        delta = self.make_delta([c["all_observations"][0]])
        r = isolated(p, c, delta)
        row = next(r for r in r["root_owners"] if r["root_id"] == "FORMAT")
        self.assertEqual(1, len(row["not_refreshed_refs"]))
        self.assertFalse(row["source_matched_for_delta"])

    @staticmethod
    def make_delta(rows):
        return {"schema": m.DELTA_SCHEMA, "observation_grade": "METADATA_ONLY",
                "authority_transfer": False, "merge_authorized": False,
                "accepted_root_closures": 0,
                "rows": [dict(repository=x["repository"], pr=x["pr"],
                              head_sha=x["head_sha"], state=x["state"],
                              reused_artifact_bytes=False, observed_workflow_runs=2,
                              counts={"success": 1, "failure": 0, "cancelled": 0,
                                      "pending": 1, "queued": 0, "in_progress": 0,
                                      "other": 0}) for x in rows]}

    def test_delta_observed_denominators(self):
        p, c = data()
        r = isolated(p, c, self.make_delta(c["all_observations"][:2]))
        self.assertEqual(2, r["metrics"]["delta_observed_prs"])
        self.assertEqual(4, r["metrics"]["delta_workflow_observations"])
        self.assertEqual(2, r["metrics"]["delta_terminal_workflow_observations"])

    def test_delta_rejects_bool_as_count(self):
        d = self.make_delta(data()[1]["all_observations"][:1])
        d["rows"][0]["counts"]["failure"] = False
        with self.assertRaisesRegex(ValueError, "DELTA_COUNTS_INVALID"):
            m.validate_delta(d)

    def test_delta_rejects_fabricated_proof(self):
        d = self.make_delta(data()[1]["all_observations"][:1])
        d["rows"][0]["reused_artifact_bytes"] = True
        with self.assertRaisesRegex(ValueError, "DELTA_FORGED_ARTIFACT_PROOF"):
            m.validate_delta(d)

    def test_delta_rejects_duplicate_pr(self):
        d = self.make_delta(data()[1]["all_observations"][:1])
        d["rows"].append(copy.deepcopy(d["rows"][0]))
        with self.assertRaisesRegex(ValueError, "DELTA_DUPLICATE_PR"):
            m.validate_delta(d)

    def test_delta_rejects_missing_run_population(self):
        d = self.make_delta(data()[1]["all_observations"][:1])
        d["rows"][0]["observed_workflow_runs"] = 20
        with self.assertRaisesRegex(ValueError, "DELTA_COUNTS_NOT_EXHAUSTIVE"):
            m.validate_delta(d)

    def test_delta_rejects_authority(self):
        d = self.make_delta(data()[1]["all_observations"][:1])
        d["merge_authorized"] = True
        with self.assertRaisesRegex(ValueError, "DELTA_AUTHORITY_OR_SCHEMA"):
            m.validate_delta(d)

    def test_duplicate_graph_edge_rejected(self):
        p, c = data()
        c["root_owners"][0]["related"].append(c["root_owners"][0]["canonical"])
        with self.assertRaisesRegex(ValueError, "UNSUPPORTED_DEPENDENCY_EDGE"):
            isolated(p, c)

    def test_taxonomy_drift_rejected(self):
        p, c = data()
        c["root_owners"][0]["id"] = "FAKE"
        with self.assertRaisesRegex(ValueError, "CANONICAL_OWNER_TAXONOMY_DRIFT"):
            isolated(p, c)

    def test_missing_canonical_reference_rejected(self):
        p, c = data()
        c["root_owners"][0]["canonical"] = "GBOGEB/ABACUS#9999"
        with self.assertRaisesRegex(ValueError, "UNSUPPORTED_DEPENDENCY_EDGE"):
            isolated(p, c)

    def test_frozen_source_schema_strict_when_native(self):
        src = HERE / "CBQ_CH_BD_20261016.json"
        rec = HERE / "RE_CENSUS_IMPACT_20261016.json"
        if not src.is_file() or not rec.is_file():
            self.skipTest("only available in canonical hub checkout")
        result = m.analyze(json.loads(src.read_text()), json.loads(rec.read_text()))
        self.assertEqual(6, result["metrics"]["owner_clusters"])
        self.assertEqual(2, result["metrics"]["canonical_owner_overlap_clusters"])
        self.assertEqual(0, result["metrics"]["accepted_engineering_roots_closed"])


if __name__ == "__main__":
    unittest.main()


class ProofDrainTests(unittest.TestCase):
    def test_sorted_nonterminal_burden_and_no_forged_latency(self):
        p, c = data()
        one, two = c["all_observations"][:2]
        delta = ReversePressureTests.make_delta([one, two])
        delta["rows"][0]["counts"] = dict(success=0, failure=0, cancelled=0,
                                             pending=2, queued=3, in_progress=0, other=0)
        delta["rows"][0]["observed_workflow_runs"] = 5
        result = isolated(p, c, delta)
        q = result["proof_drain"]
        self.assertEqual(f'{one["repository"]}#{one["pr"]}', q[0]["pr"])
        self.assertEqual(5, q[0]["nonterminal_run_observations"])
        self.assertIsNone(result["metrics"]["queue_p95_seconds"])
        self.assertEqual(2, len(result["worker_proposals"]["proposed_readonly_waves"]))
        self.assertFalse(result["worker_proposals"]["dispatch_authorized"])

    def test_no_delta_means_no_fake_queue(self):
        p, c = data()
        result = isolated(p, c)
        self.assertEqual([], result["proof_drain"])
        self.assertEqual(0, result["metrics"]["delta_workflow_observations"])
        self.assertIsNone(result["metrics"]["delta_terminal_fraction_descriptive"])
