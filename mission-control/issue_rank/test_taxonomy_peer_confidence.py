"""N9 peer cohort variance, Wilson and redaction source contracts."""
import copy
import json
import tempfile
import unittest
from pathlib import Path

import title_taxonomy as taxonomy
import taxonomy_peer_confidence as peers
import taxonomy_pulse as pulse

HUB="GBOGEB/pipeline-automation-hub"
QPS="GBOGEB/cryoplant-project"


def row(repo,num,title,kind="Issue",private=False):
    return {"key":f"{repo}#{num}","repo":repo,"number":num,
            "type":kind,"title":title,"private":private,
            "title_taxonomy":taxonomy.parse_title(title,kind)}


def model(items=None,at="2026-10-26T12:00:00Z"):
    return {"schema":pulse.RANK_SCHEMA,"fetched_at":at,
            "heads":{HUB:{"head_sha":"a"*40,"private":False},
                     QPS:{"head_sha":"b"*40,"private":True}},
            "items":items if items is not None else [
                row(HUB,1,"fix(jade devops): census fails closed","PullRequest"),
                row(HUB,2,"feat(watch): code-purple and gogreen telemetry"),
                row(QPS,3,"fix(secret contract): TOP-SECRET-OM",private=True)]}


class PeerConfidence(unittest.TestCase):
    def test_wilson_never_fakes_certainty(self):
        self.assertIsNone(peers.wilson(0,0))
        self.assertLess(peers.wilson(10,10)[0],1)
        self.assertGreater(peers.wilson(0,10)[1],0)
        self.assertEqual(peers.wilson(2,2)[1],1)

    def test_public_disjoint_peer_groups_sum_to_open_items(self):
        out=peers.analyze(model())
        now=out["current"]
        self.assertEqual(now["items"],2)
        self.assertEqual(now["issues"],1)
        self.assertEqual(now["prs"],1)
        self.assertEqual(now["reconciled_peer_sum"],2)
        self.assertEqual(sum(v["count"] for v in now["peers"].values()),2)
        self.assertEqual(now["private_excluded"],1)
        self.assertNotIn(QPS,json.dumps(out))
        self.assertNotIn("TOP-SECRET-OM",json.dumps(out))
        self.assertFalse(out["delta_is_causal"])

    def test_multiple_topics_are_not_independent_work_items(self):
        out=peers.analyze(model())
        themes=out["current"]["topic_memberships_nonadditive"]
        self.assertTrue(themes)
        self.assertGreater(sum(themes.values()),out["current"]["items"])
        self.assertEqual(out["root_burndown_credit"],0)

    def test_zero_populations_and_missing_peer_cohort(self):
        out=peers.analyze(model([]))
        self.assertEqual(out["current"]["items"],0)
        self.assertEqual(out["current"]["peers"],{})
        self.assertEqual(out["current"]["repositories"][HUB],0)

    def test_matched_current_prior_loses_peer_without_closure_credit(self):
        old=model([row(HUB,1,"fix(watch): status")])
        now=model([row(HUB,1,"feat(watch): status"),row(HUB,2,"docs: new")],
                  at="2026-10-26T13:00:00Z")
        out=peers.analyze(now,old)
        self.assertTrue(out["previous_population_comparable"])
        self.assertFalse(out["delta_is_causal"])
        self.assertEqual(out["formal_credit_delta"],0)
        self.assertTrue(all(x["verified_root_closure"] is None
                            for x in out["peer_delta"].values()))

    def test_changed_population_cannot_be_compared_as_closure(self):
        old=model([row(HUB,1,"fix: red")])
        now=model([row(HUB,1,"fix: red")],at="2026-10-26T13:00:00Z")
        now["heads"].pop(QPS)
        out=peers.analyze(now,old)
        self.assertFalse(out["previous_population_comparable"])
        self.assertEqual(out["population_comparison"],"WITHHELD_SOURCE_OR_PRIVACY_SCOPE_DRIFT")
        self.assertEqual(out["peer_delta"],{})
        self.assertEqual(out["root_burndown_credit"],0)

    def test_no_private_scope_details_emitted_when_repositories_drift(self):
        old=model([row(HUB,1,"fix(watch): status")])
        now=model([row(HUB,1,"fix(watch): status")],
                  at="2026-10-26T13:00:00Z")
        now["heads"].pop(QPS)
        out=peers.analyze(now,old)
        self.assertFalse(out["previous_population_comparable"])
        self.assertFalse(out["peer_delta"])
        self.assertNotIn(QPS,json.dumps(out))
        self.assertNotIn("TOP-SECRET",json.dumps(out))

    def test_source_privacy_reclassification_blocks_peer_comparison(self):
        old=model([row(HUB,1,"fix(watch): status")])
        now=model([row(HUB,1,"fix(watch): status")],
                  at="2026-10-26T13:00:00Z")
        now["heads"][QPS]["private"]=False
        with self.assertRaisesRegex(ValueError,"SOURCE_VISIBILITY_CHANGED"):
            peers.analyze(now,old)

    def test_reverse_pulse_and_bad_model_fail(self):
        old=model([row(HUB,1,"fix: x")],at="2026-10-26T14:00:00Z")
        with self.assertRaisesRegex(ValueError,"REVERSED_PULSE"):
            peers.analyze(model([row(HUB,1,"fix: x")]),old)
        a=model()
        a["heads"][HUB]["head_sha"]="bad"
        with self.assertRaisesRegex(ValueError,"INVALID_SOURCE_HEAD"):
            peers.analyze(a)

    def test_private_local_is_opt_in_and_deterministic(self):
        m=model()
        public=peers.analyze(m)
        private=peers.analyze(m,public=False)
        self.assertEqual(private["current"]["items"],3)
        self.assertIn(QPS,private["source_heads"])
        self.assertEqual(public["receipt_sha256"],peers.analyze(copy.deepcopy(m))["receipt_sha256"])

    def test_cli_sends_no_git_mutations(self):
        with tempfile.TemporaryDirectory() as tmp:
            source,out=Path(tmp)/"source.json",Path(tmp)/"out.json"
            source.write_text(json.dumps(model()))
            before=source.read_bytes()
            self.assertEqual(peers.main(["--current",str(source),"--out",str(out)]),0)
            self.assertEqual(source.read_bytes(),before)
            self.assertEqual(json.loads(out.read_text())["current"]["items"],2)


if __name__=="__main__":
    unittest.main()
