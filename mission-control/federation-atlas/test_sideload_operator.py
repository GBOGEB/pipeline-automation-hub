"""Negative controls for read-only side-load and Kubernetes operator projection."""
import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
import build_sideload_operator as m

class OperatorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data=json.loads(m.SOURCE.read_text(encoding="utf-8"))
    def case(self):
        return copy.deepcopy(self.data)
    def test_four_owner_lanes_and_source_contract(self):
        self.assertTrue(m.validate(self.case()))
        self.assertEqual({x["id"] for x in self.data["lanes"]},{"QPS","KEB","DOW","MC"})
    def test_cannot_promote_authority_or_release(self):
        for field,value in (("authority_transfer",True),("engineering_credit_delta",1),("formal_credit_delta",1)):
            d=self.case();d[field]=value
            with self.assertRaisesRegex(ValueError,"promotion"):m.validate(d)
        d=self.case();d["safe_defaults"]["release"]="PASS"
        with self.assertRaisesRegex(ValueError,"bypass"):m.validate(d)
    def test_cannot_forge_cluster_runtime_or_hops(self):
        for key,value in (("cluster_api_proven",True),("workload_proven",True),("edge_qualified",True),("authenticated_hops",4),("matched_coverage_gain",1)):
            d=self.case();d["safe_defaults"][key]=value
            with self.assertRaisesRegex(ValueError,"unverified"):m.validate(d)
    def test_reject_duplicate_lanes_or_reordered_gates(self):
        d=self.case();d["lanes"][-1]=d["lanes"][0]
        with self.assertRaisesRegex(ValueError,"four named"):m.validate(d)
        d=self.case();d["promotion_gates"][0],d["promotion_gates"][1]=d["promotion_gates"][1],d["promotion_gates"][0]
        with self.assertRaisesRegex(ValueError,"sequence"):m.validate(d)
    def test_trust_enum_must_match_keb(self):
        d=self.case();d["trust_levels"].append("ACCEPTED")
        with self.assertRaisesRegex(ValueError,"trust"):m.validate(d)
    def test_html_is_deterministic_and_hashed(self):
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            x=m.build(a);y=m.build(b)
            self.assertEqual(x,y)
            page=(Path(a)/"sideload-operator.html").read_bytes()
            self.assertEqual(hashlib.sha256(page).hexdigest(),x["html_sha256"])
            self.assertIn(b'aria-pressed=',page)
            self.assertIn(b'Admission HOLD',page)
            self.assertIn(b'QPS disposition DEFER',page)
            self.assertNotIn(b'K8S API PASS',page)
    def test_xss_html_escape_for_untrusted_label(self):
        d=self.case();d["lanes"][0]["label"]='<script>alert("x")</script>'
        page=m.render(d)
        self.assertNotIn('<script>alert("x")</script>',page)
        self.assertIn('&lt;script&gt;',page)
    def test_no_owner_removed(self):
        d=self.case();d["lanes"].pop()
        with self.assertRaisesRegex(ValueError,"four named"):m.validate(d)

if __name__=="__main__":
    unittest.main()
