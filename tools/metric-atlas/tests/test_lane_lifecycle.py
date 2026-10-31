"""W379 lane-stage crosswalk: positive, negative and fail-closed tests."""
import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from metric_atlas import lane_lifecycle as M

SHA = "a"*40
DIGEST = "b"*64
NOW = "2026-10-28T14:00:00Z"
REPO = "GBOGEB/pipeline-automation-hub"


def snapshot():
    return {"schema":M.SCHEMA,"cohort":"w379.p0","observed_at":NOW,
            "mode":"READ_ONLY_SOURCE_DECLARED","source_heads":{REPO:SHA},
            "observations":[],"authority_transfer":False,"merge_admission":"HOLD"}


def receipt(lane="A",stage="S0_PLAN",result="PASS"):
    return {"lane":lane,"stage":stage,"repo":REPO,"head_sha":SHA,
            "receipt_sha256":DIGEST,"result":result,"observed_at":NOW,
            "evidence_url":"https://github.com/GBOGEB/pipeline-automation-hub/actions/runs/123"}


class LaneStageTests(unittest.TestCase):
    def test_population_and_authoritative_keys(self):
        p=M.project(snapshot())
        self.assertEqual(len(p["cells"]),70)
        self.assertEqual(p["stage_keys"],list(M.OWNER.STAGE_KEYS))
        self.assertEqual(p["counts"]["UNKNOWN"],70)
        self.assertFalse(p["real_lane_maturity_verified"])
        self.assertEqual(p["merge_admission"],"HOLD")
        self.assertTrue(p["same_pulse_stages_acyclic"])
        self.assertEqual(len(p["next_pulse_feedback_only"]),1)
        self.assertTrue(all(c["maturity_level"] is None for c in p["cells"]))
        self.assertEqual(set(M.LANES),set("ABCDEFG"))

    def test_deterministic_and_manifest(self):
        p=M.project(snapshot())
        self.assertEqual(p,M.project(snapshot()))
        with tempfile.TemporaryDirectory() as d:
            manifest=M.emit(p,d)
            for name,hash_ in manifest["files_sha256"].items():
                self.assertEqual(hashlib.sha256((Path(d)/name).read_bytes()).hexdigest(),hash_)
            self.assertEqual(len(manifest["files_sha256"]),3)
            self.assertIn("A Census", (Path(d)/"lane-stage.md").read_text())
            self.assertEqual(len((Path(d)/"lane-stage.csv").read_text().splitlines()),71)

    def test_observation_never_yields_independently_verified_maturity(self):
        s=snapshot()
        s["observations"]=[receipt("A","S0_PLAN","PASS"),receipt("G","S3_TEST","FAIL")]
        p=M.project(s)
        self.assertEqual(p["counts"],{"UNKNOWN":68,"OBSERVED_PASS_UNVERIFIED":1,
                                       "OBSERVED_FAIL_HOLD":1})
        self.assertTrue(all(c["maturity_level"] is None for c in p["cells"]))
        self.assertFalse(p["real_lane_maturity_verified"])

    def test_bad_snapshots_fail_closed(self):
        variants=[
            lambda s:s.update(authority_transfer=True),
            lambda s:s.update(merge_admission="PASS"),
            lambda s:s.update(mode="LIVE_AUTHORIZED"),
            lambda s:s.update(cohort="bad name"),
            lambda s:s.update(source_heads={REPO:"z"*40}),
            lambda s:s.update(observed_at="tomorrow"),
            lambda s:s.update(foo=0),
        ]
        for mutation in variants:
            with self.subTest(mutation=repr(mutation)):
                s=snapshot();mutation(s)
                with self.assertRaises((ValueError,KeyError)):M.project(s)

    def test_bad_evidence_rejected(self):
        variants=[
            lambda x:x.update(lane="Z"),
            lambda x:x.update(stage="S10_MERGE"),
            lambda x:x.update(repo="Other/repo"),
            lambda x:x.update(head_sha="c"*40),
            lambda x:x.update(receipt_sha256="bad"),
            lambda x:x.update(result="APPROVED"),
            lambda x:x.update(observed_at="2026-10-29T14:00:00Z"),
            lambda x:x.update(evidence_url="http://github.com/GBOGEB/pipeline-automation-hub/actions/runs/123"),
            lambda x:x.update(evidence_url="https://github.com.evil.test/GBOGEB/pipeline-automation-hub/actions/runs/123"),
            lambda x:x.update(evidence_url="https://github.com/Other/repo/actions/runs/123"),
            lambda x:x.update(evidence_url="https://github.com/GBOGEB/pipeline-automation-hub/actions/runs/123#fake"),
            lambda x:x.update(fake=True),
        ]
        for mutation in variants:
            with self.subTest(mutation=repr(mutation)):
                s=snapshot();r=receipt();mutation(r);s["observations"]=[r]
                with self.assertRaises((ValueError,KeyError)):M.project(s)

    def test_duplicate_and_capacity_rejected(self):
        s=snapshot();s["observations"]=[receipt(),receipt()]
        with self.assertRaisesRegex(ValueError,"DUPLICATE"):M.project(s)
        s=snapshot();s["observations"]=[receipt()]*71
        with self.assertRaisesRegex(ValueError,"COUNT"):M.project(s)

    def test_stage_contract_crosswalk_is_complete(self):
        p=M.project(snapshot())
        for cell in p["cells"]:
            self.assertEqual(len(cell["canonical_probe_ids"]),5)
            self.assertIn(cell["stage"],M.STAGES)
            self.assertTrue(cell["activity"])
            self.assertTrue(cell["owner"])

    def test_negative_optimized_python_still_rejects(self):
        s=snapshot();s["observations"]=[receipt()]
        s["observations"][0]["receipt_sha256"]="0"
        with self.assertRaises(ValueError):M.project(s)


PILOT = Path(__file__).with_name("pilot_3topic.json")


class PilotBindingTests(unittest.TestCase):
    """A W378 pilot attaches only when it is from the snapshot's pulse."""

    def setUp(self):
        self.pilot = json.loads(PILOT.read_text())
        self.snap = snapshot()
        self.snap["source_heads"] = {r["packet"]["producer_repo"]: r["packet"]["producer_head"]
                                     for r in self.pilot["packets"]}

    def test_same_pulse_pilot_attached_with_its_identity(self):
        p = M.project(self.snap, self.pilot)["pilot"]
        self.assertEqual(p["declared_pilot_cohort"], self.pilot["cohort"])
        self.assertEqual(p["declared_pilot_observed_at"], self.pilot["observed_at"])
        self.assertEqual([tuple(x) for x in p["producer_heads"]],
                         sorted(self.snap["source_heads"].items()))

    def test_future_pilot_rejected(self):
        self.snap["observed_at"] = "2026-10-28T12:39:59Z"
        with self.assertRaisesRegex(ValueError, "W378_PILOT_FROM_FUTURE"):
            M.project(self.snap, self.pilot)

    def test_pilot_from_other_producer_head_rejected(self):
        repo = next(iter(self.snap["source_heads"]))
        self.snap["source_heads"][repo] = "c"*40
        with self.assertRaisesRegex(ValueError, "W378_PILOT_SOURCE_HEAD_MISMATCH"):
            M.project(self.snap, self.pilot)

    def test_graph_node_head_outside_snapshot_rejected(self):
        node = next(n for n in self.pilot["nodes"] if n["kind"] == "PROCESS")
        node["head_sha"] = "d"*40
        with self.assertRaisesRegex(ValueError, "W378_PILOT_GRAPH_HEAD_MISMATCH"):
            M.project(self.snap, self.pilot)

    def test_graph_node_head_of_other_bound_repo_rejected(self):
        heads = self.snap["source_heads"]
        node = next(n for n in self.pilot["nodes"] if n["owner"] in heads)
        node["head_sha"] = next(sha for repo, sha in heads.items() if repo != node["owner"])
        with self.assertRaisesRegex(ValueError, "W378_PILOT_GRAPH_HEAD_MISMATCH"):
            M.project(self.snap, self.pilot)

    def test_graph_node_owner_repo_unbound_by_snapshot_rejected(self):
        # Borrows a bound head, but names a repository the snapshot never recorded.
        node = next(n for n in self.pilot["nodes"] if n["owner"] in self.snap["source_heads"])
        node["owner"] = "GBOGEB/unbound-repo"
        with self.assertRaisesRegex(ValueError, "W378_PILOT_GRAPH_HEAD_MISMATCH"):
            M.project(self.snap, self.pilot)

    def test_pilot_repo_unbound_by_snapshot_rejected(self):
        self.snap["source_heads"] = {REPO: SHA}
        with self.assertRaisesRegex(ValueError, "W378_PILOT_SOURCE_HEAD_MISMATCH"):
            M.project(self.snap, self.pilot)


if __name__=="__main__":
    unittest.main()
