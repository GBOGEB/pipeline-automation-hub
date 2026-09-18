import json
import tempfile
import unittest
from pathlib import Path

from recursive_doc_engine.cd_gate import gate
from recursive_doc_engine.engine import build_candidate, write_run


class RoundTripTests(unittest.TestCase):
    def test_exact_roundtrip_unicode_and_structure(self):
        source = "# MASTER\n\n- α block\n- emoji ✅\nPlain text without final newline"
        blocks, candidate, cd = build_candidate(source)
        self.assertEqual(source, candidate)
        self.assertTrue(cd["metrics"]["roundtrip_exact"])
        self.assertTrue(cd["metrics"]["sha256_equal"])
        self.assertGreaterEqual(len(blocks), 1)
        self.assertEqual([b["sequence"] for b in blocks], list(range(1, len(blocks) + 1)))

    def test_gate_passes_then_detects_tamper(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            master = root / "master.md"
            out = root / "run"
            master.write_text("# A\nB\n", encoding="utf-8")
            write_run(master, out)
            self.assertTrue(gate(out)["passed"])
            (out / "candidate.md").write_text("tampered\n", encoding="utf-8")
            result = gate(out)
            self.assertFalse(result["passed"])
            self.assertIn("candidate_hash_bound", result["reasons"])

    def test_cd_is_json_serializable(self):
        _, _, cd = build_candidate("x\n")
        json.dumps(cd)


if __name__ == "__main__":
    unittest.main()
