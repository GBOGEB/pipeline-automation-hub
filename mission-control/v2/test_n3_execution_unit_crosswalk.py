"""MissionControl N3 cross-domain glossary compatibility: no false pulse/advance credit.

Runs with: python -m unittest discover -s mission-control/v2 -p test_n3_execution_unit_crosswalk.py -v
Dependency-free. Tests the source-controlled glossary and method registry,
not a substitute for CODEX review or native CI proof.
"""
from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent


def read(name):
    with (HERE / name).open(encoding="utf-8") as f:
        return json.load(f)


def validate_bridge(glossary, methods):
    """Fail closed on overlapping namespace and false admission semantics."""
    b = glossary["cross_repository_execution_units"]
    u = b["units"]
    assert b["schema"] == "missioncontrol.execution_unit_crosswalk.v1"
    assert set(u) == {"3W", "3MP", "G3P", "G3A"}
    assert u["3W"]["unit"] == "WAVE"
    assert u["3W"]["accepted_advance_implicit"] is False
    assert u["3MP"]["unit"] == "PULSE"
    assert u["3MP"]["hold_may_complete_pulse"] is True
    assert u["3MP"]["accepted_advance_implicit"] is False
    assert u["G3P"]["pulse_slots"] == 3
    assert u["G3P"]["received_holds_do_not_prove_accepted_advances"] is True
    assert u["G3A"]["unit"] == "ACCEPTED_CHECKPOINT"
    assert u["G3A"]["target_accepted_advances"] == 3
    assert u["G3A"]["requires"] == "THREE_DISTINCT_INDEPENDENTLY_VERIFIED_ACCEPTANCE_GATES"
    assert u["G3A"]["accepted_advance_implicit"] is False
    assert glossary["reservations"]["G3P"]["canonical_meaning"] == "GOVERNED_THREE_PULSE_WAVE"
    assert glossary["core_terms"]["N_PULSE"] != glossary["core_terms"]["N_ACCEPTED"]
    assert "3P*" in b["namespace_conflict"]
    assert "Never" not in b["namespace_conflict"]["3P*"] or isinstance(b["namespace_conflict"]["3P*"], str)
    assert "3MP" in b["namespace_conflict"]["3P*"]
    assert methods["profiles"]["3PR"]["phases"] == ["REFRESH", "PROBE", "RANK"]
    assert methods["profiles"]["3PC"]["phases"] == ["PREPARE", "PROVE", "COMMIT"]
    assert methods["dispatcher"]["id"] == "3P*"
    assert "G3P" not in methods["profiles"]
    assert b["independent_controls"]["authority_transfer"] is False
    assert b["independent_controls"]["security_waiver"] is False
    assert b["independent_controls"]["automatic_main_merge"] is False
    assert b["independent_controls"]["no_background_work_claim"] is True
    assert b["ordinal_contract"]["n_pulse"] != b["ordinal_contract"]["n_accepted"]
    assert b["pulse_actions"][0]["slot"] == 1
    assert b["pulse_actions"][1]["slot"] == 2
    assert b["pulse_actions"][2]["slot"] == 3
    assert len(b["pulse_actions"]) == 3
    assert len(set(b["hard_stops"])) == len(b["hard_stops"])
    assert b["semantic_authority"].startswith("GBOGEB/CODEX::")
    assert glossary["n3_continuation_extension"]["separate_accepted_checkpoint_ordinal"] is True
    assert "BARE_3P_STAR_ALIAS_NE_CROSS_REPO_TOKEN" in glossary["non_equivalences"]
    assert glossary["identity_grammar"]["g3a_advance"].endswith("ADVANCE-<1|2|3>")
    return True


class N3ExecutionUnitCrosswalkTests(unittest.TestCase):
    def setUp(self):
        self.glossary = read("MC_GLOSSARY_TAXONOMY_v2.json")
        self.methods = read("MC_METHOD_PROFILE_REGISTRY_v1.json")

    def test_actual_registry_crosswalk(self):
        self.assertTrue(validate_bridge(self.glossary, self.methods))

    def test_three_waves_cannot_claim_advance(self):
        g = copy.deepcopy(self.glossary)
        g["cross_repository_execution_units"]["units"]["3W"]["accepted_advance_implicit"] = True
        with self.assertRaises(AssertionError):
            validate_bridge(g, self.methods)

    def test_measured_holds_cannot_become_advances(self):
        g = copy.deepcopy(self.glossary)
        g["cross_repository_execution_units"]["units"]["3MP"]["accepted_advance_implicit"] = True
        with self.assertRaises(AssertionError):
            validate_bridge(g, self.methods)

    def test_g3p_is_one_three_pulse_wave(self):
        g = copy.deepcopy(self.glossary)
        g["cross_repository_execution_units"]["units"]["G3P"]["pulse_slots"] = 4
        with self.assertRaises(AssertionError):
            validate_bridge(g, self.methods)

    def test_g3a_requires_distinct_accepted_gates(self):
        g = copy.deepcopy(self.glossary)
        g["cross_repository_execution_units"]["units"]["G3A"]["requires"] = "THREE_RUNS"
        with self.assertRaises(AssertionError):
            validate_bridge(g, self.methods)

    def test_g3a_count_cannot_follow_pulse_count(self):
        g = copy.deepcopy(self.glossary)
        g["cross_repository_execution_units"]["units"]["G3A"]["accepted_advance_implicit"] = True
        with self.assertRaises(AssertionError):
            validate_bridge(g, self.methods)

    def test_legacy_3pr_is_not_three_pulses(self):
        m = copy.deepcopy(self.methods)
        m["profiles"]["3PR"]["phases"] = ["PULSE1", "PULSE2", "PULSE3"]
        with self.assertRaises(AssertionError):
            validate_bridge(self.glossary, m)

    def test_legacy_3pc_is_not_auto_merge(self):
        m = copy.deepcopy(self.methods)
        m["profiles"]["3PC"]["phases"] = ["PREPARE", "MERGE", "ADMIT"]
        with self.assertRaises(AssertionError):
            validate_bridge(self.glossary, m)

    def test_3p_star_method_selector_is_preserved(self):
        m = copy.deepcopy(self.methods)
        m["dispatcher"]["id"] = "3MP"
        with self.assertRaises(AssertionError):
            validate_bridge(self.glossary, m)

    def test_bare_three_p_star_never_replaces_cross_repo_3mp(self):
        g = copy.deepcopy(self.glossary)
        g["cross_repository_execution_units"]["namespace_conflict"]["3P*"] = "UNAMBIGUOUS"
        with self.assertRaises(AssertionError):
            validate_bridge(g, self.methods)

    def test_false_authority_transfer_rejected(self):
        g = copy.deepcopy(self.glossary)
        g["cross_repository_execution_units"]["independent_controls"]["authority_transfer"] = True
        with self.assertRaises(AssertionError):
            validate_bridge(g, self.methods)

    def test_false_security_waiver_rejected(self):
        g = copy.deepcopy(self.glossary)
        g["cross_repository_execution_units"]["independent_controls"]["security_waiver"] = True
        with self.assertRaises(AssertionError):
            validate_bridge(g, self.methods)

    def test_false_main_merge_rejected(self):
        g = copy.deepcopy(self.glossary)
        g["cross_repository_execution_units"]["independent_controls"]["automatic_main_merge"] = True
        with self.assertRaises(AssertionError):
            validate_bridge(g, self.methods)

    def test_false_background_continuation_rejected(self):
        g = copy.deepcopy(self.glossary)
        g["cross_repository_execution_units"]["independent_controls"]["no_background_work_claim"] = False
        with self.assertRaises(AssertionError):
            validate_bridge(g, self.methods)

    def test_missing_source_authority_fails_closed(self):
        g = copy.deepcopy(self.glossary)
        g["cross_repository_execution_units"]["semantic_authority"] = ""
        with self.assertRaises(AssertionError):
            validate_bridge(g, self.methods)

    def test_duplicate_pulse_ordinals_rejected(self):
        g = copy.deepcopy(self.glossary)
        g["cross_repository_execution_units"]["pulse_actions"][2]["slot"] = 2
        with self.assertRaises(AssertionError):
            validate_bridge(g, self.methods)

    def test_original_existing_g3p_profile_not_promoted(self):
        m = copy.deepcopy(self.methods)
        m["profiles"]["G3P"] = {"phases": ["P1", "P2", "P3"]}
        with self.assertRaises(AssertionError):
            validate_bridge(self.glossary, m)


if __name__ == "__main__":
    unittest.main()
