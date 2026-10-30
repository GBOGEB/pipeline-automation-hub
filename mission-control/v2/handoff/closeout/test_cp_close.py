"""CP.CLOSE: privacy, semantically lossless source and BD integrity regression."""
import copy
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import cp_close

ROOT=Path(__file__).resolve().parents[4]
INTAKE=Path(__file__).resolve().parent/"intakes"/"CP-G3P-HTMLQA-20261017.json"
QUEUE=ROOT/"mission-control"/"federation-atlas"/"CODE_PURPLE_BD_QUEUE_v1.json"

class CloseoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base=json.loads(INTAKE.read_text(encoding="utf-8"))
    def invalid(self,mutate,needle=None):
        inp=copy.deepcopy(self.base)
        mutate(inp)
        with self.assertRaisesRegex(ValueError,needle or "CP_CLOSE_FAIL_CLOSED"):
            cp_close.validate(inp)
    def test_canonical_closeout_operator_alias_compatible(self):
        profile=json.loads((Path(__file__).resolve().parents[1]/"CHAT_CLOSEOUT_PROFILE_V1.json").read_text(encoding="utf-8"))
        ext=json.loads((Path(__file__).resolve().parent/"CP_CLOSE_GITHUB_v1.json").read_text(encoding="utf-8"))
        self.assertEqual(profile["moniker"],"CP.CLOSEOUT_ALIAS_OF_CP.CLOSE")
        self.assertEqual(profile["status"],"OPTIONAL_REPORTING_ANNEX_NOT_CANONICAL")
        self.assertEqual(ext["name"],"CP.CLOSE")
        self.assertIn("CP.CLOSEOUT",ext["aliases"])
        self.assertEqual(ext["contract"]["generator"],
                         "mission-control/v2/handoff/closeout/cp_close.py")
        self.assertTrue(ext["compatibility"]["dual_profiles_not_second_ssot"])

    def test_current_intake_valid(self):
        cp_close.validate(self.base)
    def test_observed_main_exact_sha(self):
        self.assertEqual(len(self.base["source"]["observed_main_sha"]),40)
    def test_original_message_count_unknown(self):
        self.assertIsNone(self.base["total_chat_user_prompts"])
        self.assertIsNone(cp_close.prompt_stats(None)["full_chat_total_prompts"])
    def test_no_transcript_in_public_intake(self):
        self.assertNotIn("messages",self.base)
        self.assertNotIn("raw_transcript",self.base)
    def test_privacy_downgrade_rejected(self):
        self.invalid(lambda d:d.update(privacy="RAW_MESSAGES"),"schema/privacy")
    def test_claimed_full_chat_forbidden(self):
        self.invalid(lambda d:d.update(complete_transcript_available=True),"unseen chat")
    def test_fabricated_chat_total_rejected(self):
        self.invalid(lambda d:d.update(total_chat_user_prompts=500),"unseen chat")
    def test_merge_waiver_rejected(self):
        self.invalid(lambda d:d.update(merge_admission="PASS"),"cannot transfer")
    def test_security_waiver_rejected(self):
        self.invalid(lambda d:d.update(security_waiver=True),"cannot transfer")
    def test_bad_main_sha_rejected(self):
        self.invalid(lambda d:d["source"].update(observed_main_sha="123"),"source identity")
    def test_duplicate_actions_rejected(self):
        self.invalid(lambda d:d["actions"].append(copy.deepcopy(d["actions"][0])),"action identities")
    def test_missing_action_owner_rejected(self):
        self.invalid(lambda d:d["actions"][0].update(owner=""),"action needs")
    def test_orphan_action_rejected(self):
        self.invalid(lambda d:d["intents"][0].update(actions=["SC-A999"]),"orphan")
    def test_dependency_cycle_rejected(self):
        def change(d):
            d["actions"][0]["depends_on"]=["SC-A002"]
        self.invalid(change,"cycle")
    def test_unknown_dependency_rejected(self):
        self.invalid(lambda d:d["actions"][0].update(depends_on=["SC-A999"]),"dependency")
    def test_false_original_chat_timestamp_rejected(self):
        self.invalid(lambda d:d["intents"][0].update(original_chat_timestamp="2026-10-17"),"unproven")
    def test_bad_external_link_rejected(self):
        self.invalid(lambda d:d["actions"][0].update(evidence_urls=["https://evil.example"]), "evidence")
    def test_merged_pr_requires_sha(self):
        self.invalid(lambda d:d["pr_snapshot"][2].update(merge_sha=None),"merge SHA")
    def test_metric_partial_denominator_fails(self):
        self.invalid(lambda d:d["metric_observations"][0].update(denominator=None),"numerator/denominator")
    def test_metric_invalid_numerator_fails(self):
        self.invalid(lambda d:d["metric_observations"][0].update(numerator=999),"invalid metric")
    def test_misidentified_bd_fails(self):
        with self.assertRaisesRegex(ValueError,"canonical BD"):
            cp_close.bd_snapshot(QUEUE,["CPQ-999"])
    def test_real_bd_snapshot_stays_read_only(self):
        a=cp_close.bd_snapshot(QUEUE,self.base["bd_focus"])
        self.assertEqual(len(a["focus"]),3)
        self.assertEqual(a["new_canonical_bd_items"],0)
        self.assertIn("global_lifecycle_counts",a)
    def test_unprovided_messages_not_zero(self):
        a=cp_close.prompt_stats(None)
        self.assertIsNone(a["sample_user_prompts"])
        self.assertEqual(a["completeness"],"UNAVAILABLE")
    def test_opt_in_messages_count_only(self):
        with tempfile.TemporaryDirectory() as x:
            p=Path(x)/"messages.json"
            p.write_text(json.dumps({"schema":"missioncontrol.user_supplied_messages.v1","declared_complete":False,
                 "messages":[{"role":"user","text":"Plan a closeout"},{"role":"assistant","text":"Plan"},{"role":"user","text":"Ship the PR"}]}), encoding="utf-8", newline="\n")
            a=cp_close.prompt_stats(p)
            self.assertEqual((a["sample_user_prompts"],a["sample_assistant_messages"]), (2,1))
            self.assertIsNone(a["full_chat_total_prompts"])
            self.assertIsNone(a["duration_hours"])
    def test_timestamp_coverage_is_not_guessed(self):
        with tempfile.TemporaryDirectory() as x:
            p=Path(x)/"messages.json"
            p.write_text(json.dumps({"schema":"missioncontrol.user_supplied_messages.v1","messages":[
                {"role":"user","text":"one","created_at":"2026-10-17T09:00:00Z"},
                {"role":"assistant","text":"two","created_at":"2026-10-17T10:30:00Z"}]}), encoding="utf-8", newline="\n")
            self.assertEqual(cp_close.prompt_stats(p)["duration_hours"],1.5)
    def test_deterministic_render_and_manifest(self):
        with tempfile.TemporaryDirectory() as d:
            out=Path(d)/"out"
            a=cp_close.build(INTAKE,QUEUE,out)
            self.assertEqual(a["artifact_count"],9)
            self.assertEqual(a["intents"],6)
            self.assertEqual(a["actions"],7)
            self.assertIsNone(a["prompt_count"])
            c=cp_close.build(INTAKE,QUEUE,out,check=True)
            self.assertEqual(a["manifest_sha256"],c["manifest_sha256"])
    def test_reject_generated_drift(self):
        with tempfile.TemporaryDirectory() as d:
            out=Path(d)/"out"
            cp_close.build(INTAKE,QUEUE,out)
            (out/"STATE.json").write_text("{}", encoding="utf-8", newline="\n")
            with self.assertRaisesRegex(ValueError,"drift"):
                cp_close.build(INTAKE,QUEUE,out,check=True)
    def test_zip_no_path_escape_and_crc(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)
            out=path/"out"
            zip_path=path/"closeout.zip"
            cp_close.build(INTAKE,QUEUE,out,archive=zip_path)
            with zipfile.ZipFile(zip_path) as z:
                self.assertIsNone(z.testzip())
                self.assertTrue(all(not x.startswith("/") and ".." not in x for x in z.namelist()))
                self.assertEqual(len(z.namelist()),9)
    def test_snapshot_does_not_modify_canonical_queue(self):
        before=QUEUE.read_bytes()
        with tempfile.TemporaryDirectory() as d:
            cp_close.build(INTAKE,QUEUE,Path(d)/"out")
        self.assertEqual(QUEUE.read_bytes(),before)
    def test_generated_handover_contains_all_actions_and_intents(self):
        with tempfile.TemporaryDirectory() as d:
            out=Path(d)/"out"
            cp_close.build(INTAKE,QUEUE,out)
            narrative=(out/"LOSSLESS_HANDOVER.md").read_text(encoding="utf-8")
            for action in self.base["actions"]:
                self.assertIn(action["id"],narrative)
            for intent in self.base["intents"]:
                self.assertIn(intent["id"],narrative)
            self.assertIn("UNKNOWN",narrative)
    def test_closed_action_not_in_todo_csv(self):
        d=copy.deepcopy(self.base)
        d["actions"][0]["state"]="DONE"
        out=cp_close.render(d,cp_close.bd_snapshot(QUEUE,d["bd_focus"]),cp_close.prompt_stats(None))
        rows=list(__import__("csv").DictReader(out["TODO_BD_QUEUE.csv"].decode().splitlines()))
        open_ids=[r["id"] for r in rows]
        self.assertNotIn("SC-A001",open_ids)
        self.assertIn("SC-A002",open_ids)
        self.assertIn("SC-A001",next(r["depends_on"] for r in rows if r["id"]=="SC-A002"))
    def test_current_prs_are_source_claims_not_release_admission(self):
        d=copy.deepcopy(self.base)
        self.assertEqual(sum(p["state"]=="MERGED" for p in d["pr_snapshot"]),2)
        self.assertEqual(d["merge_admission"],"HOLD")
    def test_unseen_model_tokens_unavailable(self):
        self.assertIsNone(cp_close.prompt_stats(None)["model_tokens"])
    def test_archive_reproducibility(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            cp_close.build(INTAKE,QUEUE,root/"out",archive=root/"a.zip")
            cp_close.build(INTAKE,QUEUE,root/"out2",archive=root/"b.zip")
            self.assertEqual((root/"a.zip").read_bytes(),(root/"b.zip").read_bytes())


    def test_cp_closeout_alias_has_one_canonical_source(self):
        source=Path(__file__).resolve().parent
        protocol=json.loads((source/"CP_CLOSE_GITHUB_v1.json").read_text(encoding="utf-8"))
        outer=json.loads((source.parent/"CP_HANDOFF_RESUME_V1.json").read_text(encoding="utf-8"))
        self.assertEqual(protocol["name"],"CP.CLOSE")
        self.assertIn("CP.CLOSEOUT",protocol["aliases"])
        self.assertEqual(outer["monikers"]["CP.CLOSEOUT"]["canonical"],"CP.CLOSE")
        self.assertEqual(outer["monikers"]["CP.CLOSE"]["generator"],
                         "mission-control/v2/handoff/closeout/cp_close.py")
        self.assertTrue((source/"cp_close.py").is_file())
        self.assertFalse(protocol["contract"]["autonomous_merge"])
        self.assertIsNone(protocol["contract"]["disclosure"]["full_chat_prompts_without_export"])

# Additive sidecar test population, exercised by the EXISTING CP.CLOSE QA workflow.
from test_hv02_fidelity_sidecar import HV02Tests

if __name__=="__main__":
    unittest.main()
