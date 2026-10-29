"""Adversarial handoff admission tests bound to the canonical SIPOC planner."""
import importlib.util
import unittest
from pathlib import Path

path = Path(__file__).resolve().parents[1] / "sipoc_instances.py"
spec = importlib.util.spec_from_file_location("sipoc_instances", path)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
SHA = "a" * 40
DIGEST = "b" * 64


def nodes():
    return {
        "P": {"source_sha": SHA, "repo": "GBOGEB/pipeline-automation-hub",
              "stage_ref": "DMAIC:ANALYZE", "depends_on": []},
        "C": {"source_sha": SHA, "repo": "GBOGEB/pipeline-automation-hub",
              "stage_ref": "GATE:P5", "depends_on": ["P"]},
    }


def edge(kind="CONTINUE_NEXT"):
    return {
        "id": "E1", "edge_type": kind, "producer": "P",
        "consumer": "C" if kind == "CONTINUE_NEXT" else None,
        "source_sha": SHA, "producer_receipt_sha256": DIGEST,
        "consumer_receipt_sha256": DIGEST, "consumer_source_sha": SHA,
        "source_pulse": 1, "target_pulse": 2 if kind == "SELF_REENTRY" else 1,
        "consumer_repo": "GBOGEB/CODEX" if kind == "PAY_IT_FORWARD" else "GBOGEB/pipeline-automation-hub",
        "target_stage_ref": None if kind == "CONTINUE_NEXT" else (
            "DMAIC:ANALYZE" if kind == "SELF_REENTRY" else "GATE:P5"),
        "evidence_class": "OBSERVED", "independent_consumer_proof": True,
        "sanitized": True, "authority_transfer": False,
        "dispatch_authorized": False, "merge_authorized": False,
    }


def project(edges):
    return mod._project_handoffs({"handoffs": edges}, nodes(),
                                 {"DMAIC:ANALYZE", "GATE:P5"})


class TestHandoffAdmission(unittest.TestCase):
    def test_candidate_never_equals_native_approval(self):
        for kind in ("CONTINUE_NEXT", "SELF_REENTRY", "PAY_IT_FORWARD"):
            with self.subTest(kind=kind):
                result = project([edge(kind)])[0]
                self.assertEqual(result["advisory_status"], "ELIGIBLE_FOR_EXTERNAL_ADMISSION")
                self.assertFalse(result["native_consumer_accepted"])
                self.assertFalse(result["merge_authorized"])

    def test_unproven_receipts_and_synthetic_defer(self):
        for key, value in (
            ("producer_receipt_sha256", None), ("consumer_receipt_sha256", None),
            ("consumer_source_sha", None), ("independent_consumer_proof", False),
            ("evidence_class", "SYNTHETIC"), ("evidence_class", "DECLARED"),
        ):
            e = edge()
            e[key] = value
            with self.subTest(key=key):
                self.assertEqual(project([e])[0]["advisory_status"], "DEFER")

    def test_bad_provenance_or_unauthorized_permission_rejected(self):
        for key, value in (
            ("source_sha", "c"*40), ("producer_receipt_sha256", "bad"),
            ("consumer_receipt_sha256", "bad"), ("consumer_source_sha", "bad"),
            ("authority_transfer", True), ("dispatch_authorized", True),
            ("merge_authorized", True), ("source_pulse", True),
            ("target_pulse", 0), ("edge_type", "BYPASS"),
            ("consumer", "UNKNOWN"),
        ):
            e = edge()
            e[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                project([e])

    def test_self_only_next_pulse_same_process(self):
        for key, value in (
            ("target_pulse", 1), ("consumer_repo", "GBOGEB/CODEX"),
            ("target_stage_ref", "GATE:P5"),
        ):
            e = edge("SELF_REENTRY")
            e[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                project([e])

    def test_lateral_sanitization_and_temporal_order(self):
        e = edge("PAY_IT_FORWARD")
        e["sanitized"] = False
        self.assertEqual(project([e])[0]["advisory_status"], "DEFER")
        e["target_pulse"] = 0
        with self.assertRaises(ValueError):
            project([e])

    def test_duplicate_ids_or_oversize_rejected(self):
        with self.assertRaises(ValueError):
            project([edge(), edge()])
        with self.assertRaises(ValueError):
            project([edge()]*129)


if __name__ == "__main__":
    unittest.main()
