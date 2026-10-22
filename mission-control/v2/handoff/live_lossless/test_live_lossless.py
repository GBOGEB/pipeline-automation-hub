"""Live Lossless source, lineage, privacy and publication contract tests."""
import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

import build_live_lossless as mod


class LiveLosslessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.state,cls.stats,cls.ledger,cls.bd,cls.provenance=mod.validate_frozen()
        cls.delta,_=mod.read(mod.HERE/"FOLLOWUP_DELTA_20261017.json")
        cls.obs,_=mod.read(mod.HERE/"GITHUB_OBSERVED_20261017.json")
    def changed(self,mutator,expected):
        delta,obs=copy.deepcopy(self.delta),copy.deepcopy(self.obs)
        mutator(delta,obs)
        with self.assertRaisesRegex(ValueError,expected):
            mod.validate_delta(delta,obs,self.ledger)

    def test_valid_current_sources(self):
        mod.validate_delta(self.delta,self.obs,self.ledger)
    def test_frozen_original_is_6_plus_7_not_transcript(self):
        self.assertEqual((len(self.ledger["intents"]),len(self.ledger["actions"])),(6,7))
        self.assertIsNone(self.stats["full_chat_total_prompts"])
    def test_addition_is_1_plus_4_and_six_subrequests(self):
        self.assertEqual((len(self.delta["actions"]),len(self.delta["subrequests"])),(4,6))
        self.assertEqual(self.delta["intent"]["id"],"SC-I007")
    def test_total_is_7_intents_and_11_actions(self):
        p=mod.build_data()
        self.assertEqual((p["summary"]["reconstructed_intents"],p["summary"]["tracked_actions"]),(7,11))
        self.assertEqual(p["summary"]["current_new_intents"],1)
    def test_missing_message_counts_stay_null(self):
        p=mod.build_data()
        self.assertIsNone(p["summary"]["full_chat_user_prompts"])
        self.assertIsNone(p["summary"]["full_chat_tokens"])
        self.assertIsNone(p["summary"]["n_accepted"])
        self.assertIsNone(p["summary"]["global_code_coverage"])
    def test_bd_authority_readonly_no_shadow_items(self):
        p=mod.build_data()
        self.assertEqual(len(p["bd_queue"]["focus"]),3)
        self.assertEqual(p["bd_queue"]["new_canonical_bd_items"],0)
    def test_canonical_moniker_is_closeout(self):
        p=mod.build_data()
        self.assertEqual(p["monikers"][0]["name"],"CP.CLOSEOUT")
        self.assertEqual(p["monikers"][1]["name"],"CP.LIVE")
        self.assertEqual(p["monikers"][2]["name"],"CP.CLOSE")
        self.assertIn("CP.RESUME",[m["name"] for m in p["monikers"]])
    def test_canonical_alias_is_bound_to_one_source_owner(self):
        profile,_ = mod.read(mod.CLOSE/"CHAT_CLOSEOUT_PROFILE_V1.json")
        contract,_ = mod.read(mod.CLOSE/"CP_HANDOFF_RESUME_V1.json")
        canonical,_ = mod.read(mod.CLOSE/"closeout/CP_CLOSE_GITHUB_v1.json")
        self.assertTrue(mod.validate_closeout_moniker(profile, contract, canonical))
        generated = mod.build_data()
        self.assertEqual(generated["monikers"][0]["scope"], "COMPATIBILITY_ALIAS_TO_CP_CLOSE")
        self.assertEqual(generated["monikers"][2]["scope"], "CANONICAL_NINE_ARTIFACT_SESSION_OPERATOR")
        self.assertIn("canonical_closeout_protocol_sha256", generated["provenance"])
        self.assertNotIn("/pull/642", generated["monikers"][2]["url"])

    def test_alias_ownership_fails_closed_on_mutation(self):
        profile,_ = mod.read(mod.CLOSE/"CHAT_CLOSEOUT_PROFILE_V1.json")
        contract,_ = mod.read(mod.CLOSE/"CP_HANDOFF_RESUME_V1.json")
        canonical,_ = mod.read(mod.CLOSE/"closeout/CP_CLOSE_GITHUB_v1.json")
        for field,bad in (("moniker", "CP.CLOSEOUT"),
                          ("status", "CANONICAL"),
                          ("control", "shadow/CP_CLOSE.json"),
                          ("no_second_producer", False),
                          ("invocation", "CP.FORGE()")):
            mutated = copy.deepcopy(profile)
            mutated[field] = bad
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, "LIVE_LOSSLESS_FAIL_CLOSED"):
                mod.validate_closeout_moniker(mutated, contract, canonical)
        mutated = copy.deepcopy(contract)
        mutated["monikers"]["CP.CLOSEOUT"]["canonical"] = "CP.CLOSEOUT"
        with self.assertRaisesRegex(ValueError, "alias ownership mismatch"):
            mod.validate_closeout_moniker(profile, mutated, canonical)
        mutated = copy.deepcopy(canonical)
        mutated["aliases"] = []
        with self.assertRaisesRegex(ValueError, "canonical CP.CLOSE protocol mismatch"):
            mod.validate_closeout_moniker(profile, contract, mutated)

    def test_source_delta_is_user_summarized_not_provider_export(self):
        p=mod.build_data()
        self.assertEqual(p["privacy"],"SANITIZED_NOT_VERBATIM")
        self.assertFalse(p["session"]["complete_transcript_available"])
    def test_old_manifest_member_sha_binds_state(self):
        m,_=mod.read(mod.FROZEN/"MANIFEST.json")
        raw=(mod.FROZEN/"STATE.json").read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(),m["member_sha256"]["STATE.json"])
    def test_frozen_history_not_mutated_by_builder(self):
        before=(mod.FROZEN/"INTENT_ACTION_LEDGER.json").read_bytes()
        with tempfile.TemporaryDirectory() as d:mod.build(Path(d)/"site")
        self.assertEqual((mod.FROZEN/"INTENT_ACTION_LEDGER.json").read_bytes(),before)
    def test_all_intents_have_action_edge(self):
        p=mod.build_data();ids={a["id"] for a in p["actions"]}
        self.assertTrue(all(set(i["actions"])<=ids for i in p["intents"]))
    def test_all_subrequests_have_current_owned_action(self):
        p=mod.build_data();latest={a["id"] for a in self.delta["actions"]}
        self.assertTrue(all(set(i["actions"])<=latest for i in p["subrequests"]))
    def test_main_run_scope_is_closeout_only(self):
        p=mod.build_data()
        m=p["summary"]["native_closeout_tests"]
        self.assertEqual((m["k"],m["d"]),(34,34))
        self.assertEqual(m["population"],"CP.CLOSE_EXACT_MAIN_ONLY")
    def test_no_auto_admission(self):
        p=mod.build_data()
        self.assertEqual(p["merge_admission"],"INDEPENDENT_HOLD")
        self.assertFalse(p["authority_transfer"])
        self.assertFalse(p["security_waiver"])
    def test_pr_source_census_not_global(self):
        p=mod.build_data();self.assertEqual(len(p["prs"]),10)
        self.assertEqual(p["source"]["current_observed_main_sha"],self.obs["main_sha"])
    def test_duplicate_delta_action_id_fail(self):
        self.changed(lambda d,o:d["actions"][1].update(id=d["actions"][0]["id"]),"coverage/identities")
    def test_delta_crosses_existing_action_id_fail(self):
        self.changed(lambda d,o:d["actions"][0].update(id="SC-A001"),"coverage/identities")
    def test_unqualified_pr_merged_missing_sha_fail(self):
        self.changed(lambda d,o:o["prs"][3].pop("merge"),"missing SHA")
    def test_duplicate_pr_number_fail(self):
        self.changed(lambda d,o:o["prs"][1].update(number=o["prs"][0]["number"]),"duplicate")
    def test_observation_source_owner_mismatch_fail(self):
        self.changed(lambda d,o:o.update(repository="OTHER/repo"),"GitHub authority")
    def test_observation_head_not_full_sha_fail(self):
        self.changed(lambda d,o:o.update(main_sha="fake"),"GitHub authority")
    def test_native_run_not_exact_main_fail(self):
        self.changed(lambda d,o:o["native_run"].update(head_sha="f"*40),"native matched")
    def test_negative_run_denominator_fail(self):
        self.changed(lambda d,o:o["native_run"].update(tests_total=0),"QA denominator")
    def test_false_security_waiver_fail(self):
        self.changed(lambda d,o:d.update(security_waiver=True),"authority")
    def test_false_merge_admission_fail(self):
        self.changed(lambda d,o:d.update(merge_admission="PASS"),"authority")
    def test_original_chat_id_invented_fail(self):
        self.changed(lambda d,o:d.update(original_chat_message_id="fake"),"source scope")
    def test_cycle_among_new_actions_fail(self):
        self.changed(lambda d,o:d["actions"][0].update(depends_on=["SC-A011"]),"cycle")
    def test_orphan_subrequest_action_fail(self):
        self.changed(lambda d,o:d["subrequests"][0].update(actions=["SC-A999"]),"unowned")
    def test_untrusted_external_evidence_link_fail(self):
        self.changed(lambda d,o:d["actions"][0].update(evidence_urls=["https://example.com"]), "delta action")
    def test_overpoll_fails(self):
        self.changed(lambda d,o:o["live_monitor"].update(default_frequency_minutes=1),"polling")
    def test_repeated_build_is_byte_deterministic(self):
        with tempfile.TemporaryDirectory() as d:
            out=Path(d)/"generated"
            result=mod.build(out)
            second=mod.build(out,check=True)
            self.assertEqual(result,second)
            self.assertEqual(result["artifacts"],5)
    def test_sha_manifest_matches_four_page_assets(self):
        with tempfile.TemporaryDirectory() as d:
            out=Path(d)/"generated";mod.build(out)
            m=json.loads((out/"manifest.json").read_text())
            self.assertEqual(len(m["files_sha256"]),4)
            for rel,expected in m["files_sha256"].items():
                self.assertEqual(hashlib.sha256((out/rel).read_bytes()).hexdigest(),expected)
    def test_generated_artifact_drift_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            out=Path(d)/"generated";mod.build(out)
            (out/"snapshot.json").write_text("{}")
            with self.assertRaisesRegex(ValueError,"byte drift"):mod.build(out,check=True)
    def test_extra_file_makes_check_fail(self):
        with tempfile.TemporaryDirectory() as d:
            out=Path(d)/"generated";mod.build(out)
            (out/"unapproved.txt").write_text("PRIVATE")
            with self.assertRaisesRegex(ValueError,"extra"):mod.build(out,check=True)
    def test_unsafe_frozen_original_change_rejected(self):
        prior=mod.FROZEN
        with tempfile.TemporaryDirectory() as d:
            temp=Path(d);temp.mkdir(exist_ok=True)
            for name in ("MANIFEST.json","STATE.json","CHAT_STATS.json","INTENT_ACTION_LEDGER.json","BD_QUEUE_READONLY.json","LOSSLESS_HANDOVER.md","NEXT_CHAT_DROPIN.md","START_HERE.md","TODO_BD_QUEUE.csv"):
                (temp/name).write_bytes((prior/name).read_bytes())
            (temp/"STATE.json").write_text("{}")
            try:
                mod.FROZEN=temp
                with self.assertRaisesRegex(ValueError,"SHA256 mismatch"):mod.validate_frozen()
            finally:
                mod.FROZEN=prior
    def test_snapshot_source_and_future_refresh_separated(self):
        p=mod.build_data()
        self.assertTrue(p["source"]["live_head_only_after_remote_readback"])
        self.assertEqual(p["github_monitor"]["default_frequency_minutes"],15)
    def test_remote_API_values_never_used_to_compute_native_test_totals(self):
        p=mod.build_data()
        self.assertEqual(p["summary"]["native_closeout_tests"]["k"],34)
        self.assertEqual(p["provenance"]["native_run"]["head_sha"],self.obs["main_sha"])
    def test_page_has_all_five_selections_and_openable_details(self):
        html=(mod.HERE/"index.html").read_text()
        for x in ("panel-overview","panel-intents","panel-actions","panel-evidence","panel-monikers","intent-cards","subrequest-cards","bd-cards","moniker-cards","role=\"tab\""):
            self.assertIn(x,html)
    def test_client_no_nonowned_API_endpoint_or_secret(self):
        js=(mod.HERE/"app.js").read_text()
        self.assertIn("https://api.github.com/repos/GBOGEB/pipeline-automation-hub",js)
        self.assertNotIn("GITHUB_TOKEN",js)
        self.assertIn("Promise.allSettled",js)
        self.assertIn("LIVE_PARTIAL",js)


if __name__=="__main__":unittest.main()
