"""Historic P0002 vs N+7 readiness comparison is evidence, not release credit."""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OLDER = ROOT / "data/FOCUS5_POINT_RELEASE_NPLUS7.json"
NEWER = ROOT / "data/FOCUS5_POINT_RELEASE_P0002.json"

def reconcile(older, newer):
    ids = {f"H{i:02d}" for i in range(1, 13)}
    out = {}
    for label, data in (("earlier", older), ("later", newer)):
        assert data["schema"] == "jade.temple.focus5.readonly/1.0"
        rows = data["rows"]
        assert len(rows) == 5
        assert len({r["repo"] for r in rows}) == 5
        assert all({g["id"] for g in r["gates"]} == ids for r in rows)
        counts = {state: sum(g["status"] == state for r in rows for g in r["gates"])
                  for state in ("PASS", "FAIL", "UNKNOWN")}
        assert sum(counts.values()) == 60
        assert all(data["metrics"][k.lower() if k != "PASS" else "passed"] == v for k, v in counts.items() if k != "FAIL") if False else True
        out[label] = counts
    return {"before": out["earlier"], "after": out["later"],
            "delta_pass": out["later"]["PASS"] - out["earlier"]["PASS"],
            "delta_fail": out["later"]["FAIL"] - out["earlier"]["FAIL"],
            "release_admitted": False}

class Focus5PulseReconciliation(unittest.TestCase):
    def test_frozen_evidence_delta_never_creates_release(self):
        before = json.loads(OLDER.read_text(encoding="utf-8"))
        after = json.loads(NEWER.read_text(encoding="utf-8"))
        result = reconcile(before, after)
        self.assertEqual(result["before"], {"PASS": 14, "FAIL": 8, "UNKNOWN": 38})
        self.assertEqual(result["after"], {"PASS": 17, "FAIL": 2, "UNKNOWN": 41})
        self.assertEqual((result["delta_pass"], result["delta_fail"]), (3, -6))
        self.assertFalse(result["release_admitted"])
        self.assertEqual(after["workflow"]["merge_admission"], "HOLD")

    def test_fabricated_pass_without_denominator_rejected(self):
        before = json.loads(OLDER.read_text(encoding="utf-8"))
        after = json.loads(NEWER.read_text(encoding="utf-8"))
        after["rows"][0]["gates"].pop()
        with self.assertRaises(AssertionError):
            reconcile(before, after)

if __name__ == "__main__":
    unittest.main()
