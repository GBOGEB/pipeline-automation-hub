"""P0008 source-preserving extension to canonical CP.CLOSE replay."""
import copy
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(HERE))
import cp_close

ALIAS = "CP-GMIC-R2-P0008-20261111"
INTAKE = HERE / "intakes" / f"{ALIAS}.json"
BD = ROOT / "mission-control/federation-atlas/CODE_PURPLE_BD_QUEUE_v1.json"
PROJECTION = HERE / "w11-gmic-r2-p0008/BD_B01_B46_READONLY.json"


class GMICCloseoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.i = json.loads(INTAKE.read_text(encoding="utf-8"))
        cls.b = json.loads(PROJECTION.read_text(encoding="utf-8"))

    def test_canonical_intake_schema_and_authority(self):
        cp_close.validate(self.i)
        self.assertEqual(self.i["source"]["default_branch"], "master")
        self.assertFalse(self.i["authority_transfer"])
        self.assertFalse(self.i["security_waiver"])
        self.assertEqual(self.i["merge_admission"], "HOLD")
        self.assertFalse(self.i["complete_transcript_available"])

    def test_no_fabricated_chat_or_coverage_denominator(self):
        self.assertIsNone(self.i["total_chat_user_prompts"])
        self.assertIsNone(self.i["total_chat_messages"])
        for m in self.i["metric_observations"]:
            if m["numerator"] is None:
                self.assertIsNone(m["denominator"])

    def test_reconstructed_not_original_chat_counts(self):
        self.assertEqual(len(self.i["intents"]), 8)
        self.assertEqual(len(self.i["actions"]), 19)
        self.assertEqual(len(self.i["pr_snapshot"]), 10)
        self.assertEqual(len(self.i["metric_observations"]), 9)
        self.assertTrue(all(x["original_chat_message_id"] is None for x in self.i["intents"]))

    def test_46_unique_ids_retained_no_reset(self):
        rows = self.b["items"]
        self.assertEqual([r["id"] for r in rows],
                         [f"B{n:02d}" for n in range(1, 47)])
        self.assertEqual(sum(r["state"] == "DONE" for r in rows[:38]), 20)
        self.assertEqual(sum(r["state"] == "DONE" for r in rows[38:]), 2)
        self.assertEqual(self.b["counts"]["total"], 46)
        self.assertEqual(self.b["counts"]["done"], 22)
        self.assertEqual(self.b["counts"]["open"], 24)

    def test_cumulative_status_partition_exact(self):
        expected = {"DONE": 22, "REVIEW_WAIT": 8, "ACTIONABLE": 3,
                    "OWNER_HOLD": 8, "DEPENDENCY_HOLD": 5}
        self.assertEqual(self.b["counts"]["by_state"], expected)
        self.assertEqual(sum(expected.values()), 46)
        self.assertIsNone(self.b["counts"]["unique_root_closure"])

    def test_queue_namespace_is_nonadditive(self):
        names = self.b["distinct_not_additive"]
        self.assertEqual(len(names), 3)
        self.assertIn("CODEX SEM-01..SEM-16", names)
        self.assertEqual(self.i["bd_focus"], [])
        self.assertTrue(self.b["additive_without_replacement"])
        self.assertEqual(self.b["source"]["historical_comment_id"], 6779729295)

    def test_merged_fact_is_separate_from_owner_admission(self):
        m = [p for p in self.i["pr_snapshot"] if p["state"] == "MERGED"]
        self.assertEqual({p["repository"] for p in m}, {"GBOGEB/CODEX", "GBOGEB/GEMINI"})
        self.assertTrue(any(p["number"] == 1282 for p in m))
        self.assertEqual(self.i["merge_admission"], "HOLD")
        self.assertTrue(any("independently" in x["done_when"] or
                            "review" in x["done_when"].lower()
                            for x in self.i["actions"] if x["state"] == "HOLD"))

    def test_orphan_and_cycle_negative_guards(self):
        bad = copy.deepcopy(self.i)
        bad["actions"][0]["depends_on"] = ["SC-A016"]
        with self.assertRaisesRegex(ValueError, "cycle"):
            cp_close.validate(bad)
        bad = copy.deepcopy(self.i)
        bad["intents"][0]["actions"] = ["SC-A999"]
        with self.assertRaisesRegex(ValueError, "orphan"):
            cp_close.validate(bad)

    def test_authority_and_prompt_fabrication_rejected(self):
        for change, needle in [
            ({"merge_admission": "PASS"}, "cannot transfer"),
            ({"total_chat_user_prompts": 1}, "unseen chat"),
            ({"security_waiver": True}, "cannot transfer"),
        ]:
            with self.subTest(change=change):
                bad = copy.deepcopy(self.i)
                bad.update(change)
                with self.assertRaisesRegex(ValueError, needle):
                    cp_close.validate(bad)

    def test_nine_artifact_repeat_and_crc(self):
        with tempfile.TemporaryDirectory() as d:
            work = Path(d)
            out = work / "record"
            archive = work / f"{ALIAS}.zip"
            r1 = cp_close.build(INTAKE, BD, out, archive=archive)
            r2 = cp_close.build(INTAKE, BD, out, check=True)
            self.assertEqual(r1["manifest_sha256"], r2["manifest_sha256"])
            self.assertEqual(r1["artifact_count"], 9)
            self.assertEqual(r1["intents"], 8)
            self.assertEqual(r1["actions"], 19)
            with zipfile.ZipFile(archive) as z:
                self.assertIsNone(z.testzip())
                self.assertEqual(len(z.namelist()), 9)


if __name__ == "__main__":
    unittest.main()
