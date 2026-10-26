"""#529 G01 controls: canonical registry, tiers, drift, reader, binary census (offline)."""
import json
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import census as c  # noqa: E402

NOW = datetime(2026, 10, 20, 16, 0, tzinfo=timezone.utc)


class Repos(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.reg, cls.tier = c.repo_census(HERE / "seed/ORG_LISTING_20261020.tsv", c.HUB, Path(cls.tmp.name), NOW)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_single_canonical_population(self):
        self.assertTrue(self.reg["canonical"])
        self.assertEqual(self.reg["population"], 90)
        self.assertEqual(sorted(x["rank"] for x in self.reg["repositories"]), list(range(1, 91)))

    def test_score_is_recomputable_from_parts(self):
        for r in self.reg["repositories"]:
            self.assertEqual(r["score"], sum(r["score_parts"].values()), r["name"])

    def test_core_five_lead_and_forks_never_outrank_owned_peers(self):
        self.assertEqual(set(self.tier["all"]["top_7"][:5]),
                         {"ABACUS", "CODEX", "cryoplant-project", "pipeline-automation-hub", "gg_MATH"})
        self.assertTrue(all(not r["fork"] for r in self.reg["repositories"][:7]))

    def test_tier_shapes(self):
        a = self.tier["all"]
        for n in c.TIERS:
            self.assertEqual(len(a[f"top_{n}"]), min(n, 90))
        self.assertNotIn("bottom_100", a)
        self.assertEqual(a["bottom_3"][0], self.reg["repositories"][-1]["name"])
        self.assertTrue(all(not r["fork"] for r in self.reg["repositories"] if r["name"] in self.tier["owned"]["top_100"]))

    def test_drift_reports_legacy_lists(self):
        d = self.tier["legacy_list_drift"]
        self.assertEqual(d["LIVE_CENSUS_REPOS"]["only_in_legacy"], [])
        self.assertIn("document-organization-system", d["TOP7_CENSUS"]["only_in_legacy"])
        self.assertTrue(d["TOP21_COHORT_ROSTER"]["only_in_legacy"])

    def test_jade_fields_carried(self):
        ab = next(r for r in self.reg["repositories"] if r["name"] == "ABACUS")
        self.assertEqual(ab["jade"]["priority"], "P0")

    def test_reader(self):
        f = Path(self.tmp.name) / "REPO_TIERS.yaml"
        self.assertEqual(c.get(f, "all.top_3"), self.tier["all"]["top_3"])
        with self.assertRaises(KeyError):
            c.get(f, "all.top_999")

    def test_committed_registry_matches_generator(self):
        committed = yaml.safe_load((HERE / "REPO_REGISTRY.yaml").read_text())
        fresh = yaml.safe_load((Path(self.tmp.name) / "REPO_REGISTRY.yaml").read_text())
        strip = lambda d: [(r["name"], r["score_parts"]["core_federation"], r["score_parts"]["top7"], r["fork"]) for r in d["repositories"]]
        self.assertEqual(sorted(strip(committed)), sorted(strip(fresh)))


class Binaries(unittest.TestCase):
    def test_census_oid_duplicates_refs_and_canonical(self):
        with tempfile.TemporaryDirectory() as t:
            r = Path(t)
            run = lambda *a: subprocess.run(["git", "-C", t, *a], check=True, capture_output=True)
            run("init", "-q")
            (r / "docs").mkdir()
            blob = b"%PDF-1.7\0" + b"x" * 500
            (r / "docs/spec.pdf").write_bytes(blob)
            (r / "copy_of_spec.pdf").write_bytes(blob)
            (r / "logo.png").write_bytes(b"\x89PNG\0" + b"y" * 50)
            (r / "README.md").write_text("See docs/spec.pdf and spec.pdf again.\n")
            run("add", "-A")
            reg, tiers = c.binary_census({"demo": t}, r / "out", NOW)
            idx = json.loads((r / "out/BINARY_INDEX.json").read_text())
            spec = [b for b in idx if b["name"] in ("spec.pdf", "copy_of_spec.pdf")]
            self.assertEqual({b["oid"] for b in spec}.__len__(), 1)
            canon = [b for b in spec if b["canonical"]][0]
            self.assertEqual(canon["path"], "docs/spec.pdf")
            self.assertEqual(canon["refs"], 2)
            self.assertEqual(reg["totals"]["duplicate_copies"], 1)
            self.assertEqual(reg["repositories"]["demo"]["unreferenced"], 2)
            self.assertEqual(tiers["priority.top_3"][0]["path"], "docs/spec.pdf")
            self.assertEqual(len(canon["oid"]), 40)


if __name__ == "__main__":
    unittest.main()
