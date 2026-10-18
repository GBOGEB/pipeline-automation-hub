"""Ruleset P-process negative readback tests: unknown != confirmed missing."""
import importlib.util
import json
import unittest
from pathlib import Path
P=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("ruleset_provenance",P/"rulesets/verify_rulesets.py")
v=importlib.util.module_from_spec(spec);spec.loader.exec_module(v)
EXPECT=json.loads((P/"rulesets/ABACUS.basic.json").read_text())
RULES=EXPECT["rules"]

class ReadbackProvenance(unittest.TestCase):
    def test_verified_effective_rule_population(self):
        r=v.probe_status(RULES,[],{"protected":True},EXPECT)
        self.assertFalse(r["red"])
        self.assertEqual(r["probe_status"],"VERIFIED_EFFECTIVE")
        self.assertEqual(r["observation_coverage"],{"observed":3,"required":3,"qualification":"COMPLETE"})
    def test_missing_effective_rules_are_confirmed_only_with_complete_readback(self):
        r=v.probe_status([{"type":"deletion"}],[],{"protected":True},EXPECT)
        self.assertTrue(r["red"])
        self.assertEqual(r["probe_status"],"CONFIRMED_DRIFT")
        self.assertIn("required_status_checks missing",r["gaps"])
        self.assertEqual(r["unknown_readbacks"],[])
    def test_inaccessible_branch_rules_are_unknown_not_missing(self):
        r=v.probe_status({"_error":"no authorization"},[],{"protected":True},EXPECT)
        self.assertEqual(r["probe_status"],"UNKNOWN_API_READBACK")
        self.assertTrue(r["red"])
        self.assertEqual(r["gaps"],[])
        self.assertEqual(r["observation_coverage"]["observed"],2)
    def test_inaccessible_ruleset_list_blocks_green(self):
        r=v.probe_status(RULES,{"_error":"restricted"},{"protected":True},EXPECT)
        self.assertEqual(r["probe_status"],"UNKNOWN_API_READBACK")
        self.assertTrue(r["red"])
    def test_missing_default_branch_readback_blocks_green(self):
        r=v.probe_status(RULES,[],{"_error":"unknown branch"},EXPECT)
        self.assertEqual(r["probe_status"],"UNKNOWN_API_READBACK")
        self.assertTrue(r["red"])
    def test_untargeted_active_ruleset_is_control_drift(self):
        r=v.probe_status(RULES,[],{"protected":True},EXPECT,
                         ["ruleset active targets no branch"])
        self.assertEqual(r["probe_status"],"CONFIRMED_DRIFT")
        self.assertTrue(r["red"])
    def test_wrong_app_required_check_is_not_green(self):
        actual=json.loads(json.dumps(RULES))
        actual[-1]["parameters"]["required_status_checks"][0]["integration_id"]=999
        r=v.probe_status(actual,[],{"protected":True},EXPECT)
        self.assertTrue(r["red"])
        self.assertTrue(any("another app" in g for g in r["gaps"]))
    def test_api_unknown_has_nonpromoting_state_even_with_missing_values(self):
        r=v.probe_status([{"type":"deletion"}],{"_error":"403"},{"protected":True},EXPECT)
        self.assertEqual(r["probe_status"],"UNKNOWN_API_READBACK")
        self.assertTrue(r["red"])
        self.assertTrue(r["gaps"])

if __name__=="__main__":unittest.main()
