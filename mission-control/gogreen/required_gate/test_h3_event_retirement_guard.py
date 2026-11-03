"""H3 native guard: source-bound authority and real trigger negative controls."""
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("mip_h3_guard", HERE / "h3_event_retirement_guard.py")
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)


class EventRetirementSafetyTests(unittest.TestCase):
    def test_same_full_population_does_not_authorize_retirement(self):
        expected = ["A", "B", "C"]
        out = M.assess(expected, expected, expected)
        self.assertEqual(out["state"], "BASELINE_PRESERVED")
        self.assertFalse(out["production_event_reduction"])
        self.assertFalse(out["merge_authorized"])

    def test_retiring_enforced_sources_or_fake_replacements_is_hold(self):
        for proposal in (["A"], ["A", "substitute"], [], ["A", "B", "substitute"]):
            with self.subTest(proposal=proposal):
                self.assertEqual(M.assess(["A", "B"], ["A", "B"], proposal)["state"], "HOLD")

    def test_current_population_drift_is_hold(self):
        for live in (["A"], ["A", "B", "unexpected"]):
            self.assertEqual(M.assess(["A", "B"], live, live)["state"], "HOLD")

    def test_duplicate_and_invalid_identity_rejected(self):
        for proposed in ("A", ["A", None], ["A", "A"], {"name": "A"}):
            self.assertEqual(M.assess(["A"], ["A"], proposed)["state"], "HOLD")

    def test_actual_trigger_must_match_marker_and_workflow_run_event(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            f = root / ".github/workflows/gogreen-required-gate-recheck.yml"
            f.parent.mkdir(parents=True)
            doc = """on:\n  workflow_run:\n    types: [completed]\n    workflows:\n      # BEGIN recheck-names\n      - "A"\n      # END recheck-names\n"""
            f.write_text(doc, encoding="utf-8", newline="\n")
            gate = M._owner()
            self.assertEqual(M.active_trigger_names(root, gate), ["A"])
            f.write_text("""on: workflow_dispatch\n# BEGIN recheck-names\n# - "A"\n# END recheck-names\n""", encoding="utf-8", newline="\n")
            with self.assertRaises(ValueError):
                M.active_trigger_names(root, gate)
            f.write_text(doc.replace('      - "A"', '      - "B"') + '# END\n', encoding="utf-8", newline="\n")
            # Marker also changes with the trigger; a separately pinned base
            # is the authority that rejects a would-be listener rename.
            self.assertEqual(M.active_trigger_names(root, gate), ["B"])

    def test_missing_unparseable_or_non_pr_enforced_fails_closed(self):
        gate = M._owner()
        policy = {"entries": {".github/workflows/a.yml": gate.ENFORCED}}
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            with mock.patch.object(gate, "load_policy", return_value=policy):
                with self.assertRaisesRegex(ValueError, "missing"):
                    M.strict_enforced_names(root, gate)
                f = root / ".github/workflows/a.yml"
                f.parent.mkdir(parents=True)
                f.write_text("name: bad\non: [\n", encoding="utf-8", newline="\n")
                with self.assertRaises(ValueError):
                    M.strict_enforced_names(root, gate)
                f.write_text("name: A\non: push\n", encoding="utf-8", newline="\n")
                with self.assertRaisesRegex(ValueError, "non-PR"):
                    M.strict_enforced_names(root, gate)

    def test_simultaneous_policy_demotion_and_listener_removal_is_hold(self):
        gate = M._owner()
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            baseline = root / "base"
            candidate = root / "candidate"
            for r in (baseline, candidate):
                wf = r / ".github/workflows/a.yml"
                wf.parent.mkdir(parents=True)
                wf.write_text("name: A\non: pull_request\n", encoding="utf-8", newline="\n")
                recheck = r / gate.RECHECK
                recheck.parent.mkdir(parents=True, exist_ok=True)
                recheck.write_text(
                    'on:\n  workflow_run:\n    types: [completed]\n    workflows:\n'
                    '      # BEGIN recheck-names\n      - "A"\n      # END recheck-names\n',
                    encoding="utf-8", newline="\n",
                )
            (candidate / gate.RECHECK).write_text(
                'on:\n  workflow_run:\n    types: [completed]\n    workflows:\n'
                '      # BEGIN recheck-names\n      - "Other"\n      # END recheck-names\n',
                encoding="utf-8", newline="\n",
            )
            def policy(_, __, source, ___):
                return {"entries": {".github/workflows/a.yml":
                                    gate.ENFORCED if source == baseline else gate.OBSERVED}}
            with mock.patch.object(gate, "load_policy", side_effect=policy), \
                 mock.patch.object(M, "_owner", return_value=gate), \
                 mock.patch.object(M, "source_head", return_value="a" * 40):
                with self.assertRaisesRegex(ValueError, "demoted|empty enforced source population"):
                    M.preflight(candidate, baseline, "a" * 40)

    def test_wrong_base_sha_rejected_before_authority_read(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaisesRegex(ValueError, "invalid pinned"):
                M.preflight(Path(td), Path(td), "short")
            with mock.patch.object(M, "source_head", return_value="b" * 40):
                with self.assertRaisesRegex(ValueError, "does not match"):
                    M.preflight(Path(td), Path(td), "a" * 40)


if __name__ == "__main__":
    unittest.main()
