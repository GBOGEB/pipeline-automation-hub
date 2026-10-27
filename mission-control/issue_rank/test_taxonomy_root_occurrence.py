"""N6 A-B-A and exactly-once root/occurrence negative tests."""
import copy
import json
import tempfile
import unittest
from pathlib import Path

import taxonomy_root_occurrence as root

HEAD="a"*40
H2="b"*40
R="c"*64
R2="d"*64


def event(run,status,head=HEAD,wave=1,root_id=R,steps=8,attempt=1,when=None):
    return {"head_sha":head,"root_fingerprint":root_id,
            "run_id":run,"attempt":attempt,"job_id":run*10,"step_id":2,
            "conclusion":status,"wave":wave,"steps_executed":steps,
            "observed_at":when or f"2026-10-26T{10+wave:02d}:00:00Z"}


def payload(events):
    return {"schema":root.INPUT,"source_repository":root.OWNER,
            "source_head":HEAD,"events":events}


class RootReceipt(unittest.TestCase):
    def test_a_b_a_regression_and_idempotent_duplicate_delivery(self):
        items=[event(1,"RED",HEAD,1),event(2,"GREEN",H2,2),
               event(3,"RED",HEAD,3)]
        data=payload(items+[copy.deepcopy(items[0])])
        r=root.calculate(data)
        self.assertEqual(r["raw_delivery_count"],4)
        self.assertEqual(r["deduplicated_occurrences"],3)
        self.assertEqual(r["duplicate_deliveries"],1)
        self.assertEqual(r["unique_roots"],1)
        self.assertEqual(r["regression_roots"],1)
        self.assertEqual(r["root_summary"][0]["status_flips"],2)
        self.assertEqual(r["root_summary"][0]["head_count"],2)
        self.assertEqual(r["currently_red_observed"],1)
        self.assertEqual(r["root_closure_credit"],0)

    def test_red_to_green_is_displacement_not_root_closure(self):
        r=root.calculate(payload([event(1,"RED"),event(2,"GREEN",H2,2)]))
        self.assertEqual(r["displaced_diagnostic_roots"],1)
        self.assertFalse(r["root_summary"][0]["verified_root_closed"])
        self.assertTrue(r["absence_is_not_closure"])
        self.assertEqual(r["merge_admission"],"HOLD")

    def test_two_roots_are_not_two_deliveries(self):
        r=root.calculate(payload([event(1,"RED"),event(2,"GREEN",H2,2),
            event(3,"RED",H2,3,R2)]))
        self.assertEqual(r["unique_roots"],2)
        self.assertEqual(r["deduplicated_occurrences"],3)
        self.assertEqual(r["currently_red_observed"],1)
        self.assertEqual(r["formal_credit_delta"],0)

    def test_identical_delivery_with_changed_head_is_mutation(self):
        first=event(1,"RED")
        other=copy.deepcopy(first)
        other["head_sha"]=H2
        with self.assertRaisesRegex(ValueError,"MUTATED_DELIVERY"):
            root.calculate(payload([first,other]))

    def test_zero_step_green_and_red_rejected(self):
        for conclusion in ("GREEN","RED"):
            with self.subTest(conclusion=conclusion):
                with self.assertRaisesRegex(ValueError,"ZERO_STEP"):
                    root.calculate(payload([event(1,conclusion,steps=0)]))
        # Queueing is not native execution.
        r=root.calculate(payload([event(1,"QUEUED",steps=0)]))
        self.assertEqual(r["currently_red_observed"],0)
        self.assertEqual(r["root_closure_credit"],0)
        with self.assertRaisesRegex(ValueError,"QUEUED_WITH_EXECUTION"):
            root.calculate(payload([event(1,"QUEUED",steps=1)]))

    def test_bad_schema_source_head_fingerprint_and_ids(self):
        a=payload([event(1,"RED")])
        a["source_repository"]="GBOGEB/cryoplant-project"
        with self.assertRaisesRegex(ValueError,"PUBLIC_HUB_ONLY"):
            root.calculate(a)
        a=payload([event(1,"RED")])
        a["events"][0]["root_fingerprint"]="semantic-guess"
        with self.assertRaisesRegex(ValueError,"ROOT_UNBOUND"):
            root.calculate(a)
        a=payload([event(1,"RED")])
        a["events"][0]["attempt"]=0
        with self.assertRaisesRegex(ValueError,"RUN_JOB_STEP"):
            root.calculate(a)
        a=payload([event(1,"RED")])
        a["source_head"]="bad"
        with self.assertRaisesRegex(ValueError,"SOURCE_HEAD"):
            root.calculate(a)

    def test_empty_data_has_zero_denominators_not_inferred_closure(self):
        r=root.calculate(payload([]))
        self.assertEqual(r["raw_delivery_count"],0)
        self.assertEqual(r["unique_roots"],0)
        self.assertIsNone(r["latest_wave"])
        self.assertEqual(r["formal_credit_delta"],0)

    def test_invariant_under_reordering_and_cli(self):
        events=[event(1,"RED"),event(2,"GREEN",H2,2)]
        first=root.calculate(payload(events))
        second=root.calculate(payload(list(reversed(events))))
        self.assertEqual(first["receipt_sha256"],second["receipt_sha256"])
        with tempfile.TemporaryDirectory() as d:
            src=Path(d)/"in.json";out=Path(d)/"out.json"
            src.write_text(json.dumps(payload(events)),encoding="utf-8")
            old=src.read_bytes()
            self.assertEqual(root.main(["--in",str(src),"--out",str(out)]),0)
            self.assertEqual(src.read_bytes(),old)
            self.assertEqual(json.loads(out.read_text())["unique_roots"],1)


if __name__=="__main__":
    unittest.main()
