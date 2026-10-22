"""Guards against fabricated credit in a GitHub-first handover."""
import copy
import json
import unittest
from pathlib import Path
from validate_github_first_handoff import validate

HERE = Path(__file__).parent
PROFILE = json.loads((HERE / "GITHUB_FIRST_PROFILE_V1.json").read_text(encoding="utf-8"))
STATE = json.loads((HERE / "STATE_N13_N15_20261017.json").read_text(encoding="utf-8"))


class HandoffContractTests(unittest.TestCase):
    def test_valid_frozen_source_checkpoint(self):
        self.assertEqual(validate(PROFILE, STATE)["admission"], "HOLD")

    def reject(self, change):
        bad = copy.deepcopy(STATE)
        change(bad)
        with self.assertRaises(ValueError):
            validate(PROFILE, bad)

    def test_reject_short_sha(self):
        self.reject(lambda s: s["source_heads"]["GBOGEB/ABACUS"].update(sha="1234"))

    def test_reject_dropped_federation_repo(self):
        self.reject(lambda s: s["source_heads"].pop("GBOGEB/gg_MATH"))

    def test_reject_false_accepted_advance(self):
        self.reject(lambda s: s.update(accepted_n_delta=3))

    def test_reject_false_root_closure(self):
        self.reject(lambda s: s.update(formal_root_closures=2))

    def test_reject_screenshot_as_native(self):
        self.reject(lambda s: s["user_screenshot_historical"].update(native_admission_credit=True))

    def test_reject_fabricated_workflow_denominator(self):
        self.reject(lambda s: s["github_current"]["workflow_conclusions"].update(total=12))

    def test_reject_relabelled_first_pass(self):
        self.reject(lambda s: s["github_current"]["independent_first_pass_closure"].update(status="PASS"))

    def test_reject_admission_green(self):
        self.reject(lambda s: s["controls"].update(merge_admission="PASS"))

    def test_reject_security_waiver(self):
        self.reject(lambda s: s["controls"].update(security_waiver=True))

    def test_reject_unauthenticated_crew(self):
        self.reject(lambda s: s["controls"].update(authenticated_crew_dispatch=True))


if __name__ == "__main__":
    unittest.main()

