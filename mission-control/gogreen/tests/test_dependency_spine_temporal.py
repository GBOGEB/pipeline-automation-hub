"""Mission Control additive temporal N-1/N/N+1 stage projection tests."""
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
FILE=Path(__file__).resolve().parents[1]/"mission-control"/"gogreen"/"dependency_spine_temporal.py"
spec=importlib.util.spec_from_file_location("dep_spine_temporal",FILE)
assert spec and spec.loader
mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
HEAD="a"*40;SOURCE="b"*40;REPO="GBOGEB/CODEX"

def fixture():
    v={"schema":"qps.dependency_spine.peer_census.v1","repo":REPO,"head_sha":SOURCE,
       "exact_head_verified":True,"workflow_count":2,"action_reference_count":4,"dependabot_present":True,
       "runtime_proof":"NATIVE_SCAN_JOB_ONLY_NOT_DEPENDABOT_UPGRADE_PROOF",
       "governance":{"authority_transfer":False,"remote_dispatch_authorized":False,
                     "mutation_enabled":False,"formal_credit_delta":0,"merge_admission":"HOLD"}}
    m={"schema":"qps.dependency_spine.peer_sha256.v1","repo":REPO,"head_sha":SOURCE,
       "files":{"PEER_CENSUS.json":mod.digest(mod.canonical(v))}}
    return v,m

class TemporalTests(unittest.TestCase):
    def test_empty_peers_are_not_failed_attempts(self):
        r=mod.build(HEAD,mod.collect({},{}))
        mod.verify(r)
        self.assertEqual(r["current_n"],0)
        self.assertIsNone(r["historical_n_minus_1"])
        self.assertEqual(r["metrics"]["peer_missing"],4)
        self.assertIsNone(r["metrics"]["reference_upgrade_coverage_pct"])
    def test_synthetic_source_stage_bytes_not_authenticated(self):
        v,m=fixture()
        with tempfile.TemporaryDirectory() as tmp:
            directory=Path(tmp)
            (directory/"PEER_CENSUS.json").write_bytes(mod.canonical(v))
            (directory/"PEER_SHA256.json").write_bytes(mod.canonical(m))
            records=mod.collect({REPO:directory},{REPO:SOURCE})
            result=mod.build(HEAD,records);mod.verify(result)
            self.assertEqual(result["current_n"],1)
            self.assertEqual(result["metrics"]["native_peer_authenticated_count"],0)
            self.assertEqual(result["metrics"]["native_cross_repo_hops_accepted"],0)
    def test_wrong_head_rejected(self):
        v,m=fixture()
        with self.assertRaisesRegex(ValueError,"PEER_IDENTITY_DRIFT"):
            mod.validate_peer(v,m,REPO,"c"*40)
    def test_digest_tamper_rejected(self):
        v,m=fixture();v["workflow_count"]=999
        with self.assertRaisesRegex(ValueError,"PEER_DIGEST"):
            mod.validate_peer(v,m,REPO,SOURCE)
    def test_false_promotion_rejected(self):
        v,m=fixture();v["governance"]["remote_dispatch_authorized"]=True
        m["files"]["PEER_CENSUS.json"]=mod.digest(mod.canonical(v))
        with self.assertRaisesRegex(ValueError,"PEER_AUTHORITY_ESCALATION"):
            mod.validate_peer(v,m,REPO,SOURCE)
    def test_not_in_fleet_rejected(self):
        with self.assertRaisesRegex(ValueError,"PEER_PIN_INVALID"):
            mod.validate_peer(*fixture(),"unauthorized/repo",SOURCE)
    def test_observer_rehashed_accept_rejected(self):
        r=mod.build(HEAD,mod.collect({},{}))
        r["merge_admission"]="PASS"
        r["semantic_sha256"]=mod.digest(mod.canonical({k:v for k,v in r.items() if k!="semantic_sha256"}))
        with self.assertRaisesRegex(ValueError,"MISSIONCONTROL_FALSE_ACCEPT"):
            mod.verify(r)
    def test_correct_temporal_previous(self):
        previous=mod.build(HEAD,mod.collect({},{}))
        r=mod.build(HEAD,mod.collect({},{}),previous=previous)
        self.assertEqual(r["improvement_delta"],0)
        self.assertTrue(r["comparison_same_scope"])
    def test_invalid_previous_fails(self):
        bad=mod.build(HEAD,mod.collect({},{}))
        bad["formal_credit_delta"]=1
        with self.assertRaisesRegex(ValueError,"HISTORICAL_SOURCE_NOT_ACCEPTED"):
            mod.build(HEAD,mod.collect({},{}),previous=bad)
    def test_bad_mapping_scope(self):
        with self.assertRaisesRegex(ValueError,"UNAUTHORIZED_PEER_SCOPE"):
            mod.collect({"unknown/repo":Path(".")},{})
    def test_missing_observation_dir_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError,"PEER_STAGE_MISSING_OR_INVALID"):
                mod.collect({REPO:Path(tmp)},{REPO:SOURCE})
