"""Read-only manifest-to-source replay regression and attack cases."""
import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from prepare_sources import prepare, validate

MANIFEST=HERE.parent/"federation-atlas"/"G3P_LIVE_SOURCES_v1.json"


def fake_wave(wave):
    index=wave["start"]
    sha=lambda n:f"{n:040x}"
    receipts=[{"ordinal":n, "pulse_id":"TEST", "input_source_sha":sha(n-1),
               "output_source_sha":sha(n), "merge_admission":"HOLD",
               "authority_transfer":False} for n in range(index,index+3)]
    return {"schema":"missioncontrol.n3_continuation.v1",
            "mission":{"id":"CBD-GOLDEN-GRAPH-604","repo":"GBOGEB/pipeline-automation-hub","wave":wave["wave"]},
            "start_ordinal":index-1,
            "policy":{"security_waiver":False},
            "authority_transfer":False,"receipts":receipts}


class SourceReplayTests(unittest.TestCase):
    def setUp(self):
        self.manifest=json.loads(MANIFEST.read_text(encoding="utf-8"))

    def test_local_four_wave_sources(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            for w in self.manifest["waves"]:
                (root/Path(w["path"]).name).write_text(json.dumps(fake_wave(w)))
            dest=root/"output"
            result=prepare(MANIFEST,Path("."),dest,local_source=root)
            self.assertEqual(result["all_ordinals_present"],12)
            self.assertEqual(len(result["sources"]),4)
            self.assertTrue(all(r["native_attestation"] is False for r in result["sources"]))
            self.assertEqual(json.loads((dest/"source-readback.json").read_text())["merge_admission"],"HOLD")

    def test_authority_guard(self):
        w=self.manifest["waves"][0]
        d=fake_wave(w)
        d["authority_transfer"]=True
        with self.assertRaisesRegex(ValueError,"authority"):
            validate(d,w)

    def test_false_merge_pulse_rejected(self):
        w=self.manifest["waves"][1]
        d=fake_wave(w)
        d["receipts"][0]["merge_admission"]="PASS"
        with self.assertRaisesRegex(ValueError,"unsafe pulse"):
            validate(d,w)

    def test_missing_pulse_rejected(self):
        w=self.manifest["waves"][2]
        d=fake_wave(w)
        d["receipts"].pop()
        with self.assertRaisesRegex(ValueError,"missing pulse"):
            validate(d,w)

    def test_mismatched_source_sha_rejected(self):
        w=self.manifest["waves"][1]
        d=fake_wave(w)
        d["receipts"][1]["input_source_sha"]="f"*40
        with self.assertRaisesRegex(ValueError,"head drift"):
            validate(d,w)

    def test_path_traversal_rejected(self):
        w=copy.deepcopy(self.manifest["waves"][0])
        w["path"]="mission-control/federation-atlas/../secret.json"
        source=copy.deepcopy(self.manifest)
        source["waves"][0]=w
        with tempfile.TemporaryDirectory() as temp:
            fake=Path(temp)/"manifest.json"
            fake.write_text(json.dumps(source))
            with self.assertRaisesRegex(ValueError,"unsafe manifest"):
                prepare(fake,Path(temp),Path(temp)/"output",local_source=Path(temp))

    def test_foreign_repo_rejected(self):
        w=self.manifest["waves"][0]
        d=fake_wave(w)
        d["mission"]["repo"]="OTHER/fork"
        with self.assertRaisesRegex(ValueError,"identity"):
            validate(d,w)

    def test_missing_source_file_fail_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(FileNotFoundError):
                prepare(MANIFEST,Path("."),Path(temp)/"out",local_source=Path(temp))

    def test_manifest_bad_schema_rejected(self):
        source=copy.deepcopy(self.manifest)
        source["schema"]="fake"
        with tempfile.TemporaryDirectory() as temp:
            fake=Path(temp)/"manifest.json"
            fake.write_text(json.dumps(source))
            with self.assertRaisesRegex(ValueError,"unsafe Pages manifest"):
                prepare(fake,Path(temp),Path(temp)/"output",local_source=Path(temp))


if __name__=="__main__":
    unittest.main()
