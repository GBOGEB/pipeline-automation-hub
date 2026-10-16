"""Visual HTML must remain a zero-delta, source-bound Golden Thread projection."""
import copy
import json
import unittest
from pathlib import Path

import golden_thread as gt
import rendition_family as rf

HERE=Path(__file__).resolve().parent
SOURCE=HERE/"fixtures"/"COLD_TAIL_BOOTSTRAP_LEDGER_v1.json"


class HumanRenditionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ledger=json.loads(SOURCE.read_text(encoding="utf-8"))

    def test_bitemporal_cards_are_readable_and_truth_preserved(self):
        truth=gt.rebuild_known_at(self.ledger,"2026-09-17T00:56:13Z")
        result=rf.render_html(truth)
        self.assertIn("Known at:",result)
        self.assertIn("Unknown-reader items",result)
        self.assertIn("GT-0013",result)
        self.assertEqual(truth,rf.extract_rendition("html",result))
        self.assertEqual(rf.canonical_truth_digest(truth),gt.digest(truth))

    def test_frozen_truth_generates_identical_html_bytes(self):
        truth=gt.rebuild_known_at(self.ledger,"2026-09-17T00:56:11Z")
        self.assertEqual(rf.render_html(truth),rf.render_html(truth))
        self.assertEqual("PASS",rf.verify_family(truth,rf.render_family(truth))["status"])

    def test_no_false_zero_in_missing_metrics(self):
        result=rf.render_html({"schema":"read-only","authority_transfer":False})
        self.assertIn("UNKNOWN",result)
        self.assertEqual({"schema":"read-only","authority_transfer":False},
                         rf.extract_rendition("html",result))

    def test_untrusted_fields_are_html_escaped(self):
        truth=gt.rebuild_known_at(self.ledger,"2026-09-17T00:56:13Z")
        truth=copy.deepcopy(truth)
        truth["boundary"]='</script><img src=x onerror="alert(1)">'
        result=rf.render_html(truth)
        self.assertNotIn('</script><img src=x',result)
        self.assertIn('&lt;/script&gt;&lt;img',result)
        self.assertEqual(truth,rf.extract_rendition("html",result))

    def test_knowledge_difference_alters_digest_not_history(self):
        before=gt.rebuild_known_at(self.ledger,"2026-09-17T00:56:11Z")
        after=gt.rebuild_known_at(self.ledger,"2026-09-17T00:56:13Z")
        self.assertNotEqual(rf.canonical_truth_digest(before),
                            rf.canonical_truth_digest(after))
        self.assertEqual("PASS",gt.verify(self.ledger)["status"])


if __name__=="__main__":
    unittest.main()
