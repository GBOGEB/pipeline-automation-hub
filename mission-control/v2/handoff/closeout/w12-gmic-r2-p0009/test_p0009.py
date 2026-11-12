"""P0009 post-merge acceptance audit, bound to the frozen P0008 CP.CLOSE."""
from __future__ import annotations

import datetime as dt
import hashlib
import importlib.util
import json
import os
import re
import shutil
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
AUDIT = json.loads((HERE / "POSTMERGE_AUDIT.json").read_text(encoding="utf-8"))
GRAPH = json.loads((HERE / "DAG.json").read_text(encoding="utf-8"))


def _lifecycle(name):
    f = ROOT / "mission-control/jade_temple/devops/lifecycle.py"
    spec = importlib.util.spec_from_file_location(name, f)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class SourceBoundP0009(unittest.TestCase):
    def test_ten_selected_prs_not_population_claim(self):
        rows = AUDIT["rows"]
        self.assertEqual(AUDIT["sample_size"], 10)
        self.assertEqual(len(rows), 10)
        self.assertEqual({r["number"] for r in rows},
                         {1135, 1138, 1152, 1160, 1164, 1173, 1175, 1179, 1193, 1190})
        self.assertIn("NOT_FULL_PORTFOLIO", AUDIT["scope"])

    def test_failing_status_predates_merge_for_every_row(self):
        for row in AUDIT["rows"]:
            with self.subTest(pr=row["number"]):
                failed = dt.datetime.fromisoformat(row["fpc_failure_at"].replace("Z", "+00:00"))
                merged = dt.datetime.fromisoformat(row["merged_at"].replace("Z", "+00:00"))
                self.assertLess(failed, merged)
                self.assertIn("/actions/runs/", row["fpc_failure_run"])
                self.assertFalse(row["merge_admission_qualified"])
                self.assertEqual(row["historical_outcome"], "MERGED_WITH_PREMERGE_FPC_FAILURE")
                self.assertRegex(row["head_sha"], r"^[0-9a-f]{40}$")
                self.assertRegex(row["merge_commit_sha"], r"^[0-9a-f]{40}$")
        self.assertEqual(AUDIT["premerge_failure_count"], 10)

    def test_reviews_are_observations_not_approvals(self):
        self.assertEqual(AUDIT["approved_review_count"], 0)
        self.assertTrue(all(row["approved_review_count"] == 0 for row in AUDIT["rows"]))
        self.assertFalse(AUDIT["merge_admission_authorized"])
        self.assertFalse(AUDIT["authority_transfer"])
        self.assertEqual(AUDIT["formal_credit_delta"], 0)
        self.assertEqual(AUDIT["issue_closure_delta"], 0)
        self.assertFalse(AUDIT["current_ruleset"]["fpc_exact_context_required"])
        self.assertEqual(AUDIT["current_ruleset"]["historical_config_at_merge"], "NOT_VERIFIED")

    def test_historical_46_row_cp_close_unchanged(self):
        base = ROOT / AUDIT["baseline"]["path"]
        raw = base.read_bytes()
        oid = hashlib.sha1(b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw).hexdigest()
        self.assertEqual(oid, AUDIT["baseline"]["git_blob_sha"])
        d = json.loads(raw)
        self.assertEqual((d["counts"]["total"], d["counts"]["done"], d["counts"]["open"]), (46, 22, 24))
        self.assertEqual([r["id"] for r in d["items"]], [f"B{i:02d}" for i in range(1, 47)])

    def test_kahn_uses_canonical_jade_owner(self):
        m = _lifecycle("gmic_p0009_kahn")
        waves = m.topo_layers(GRAPH["nodes"], GRAPH["edges"])
        order = [node for wave in waves for node in wave]
        self.assertEqual(len(order), len(GRAPH["nodes"]))
        for src, dst, kind in GRAPH["edges"]:
            if not kind.startswith("FEEDBACK"):
                self.assertLess(order.index(src), order.index(dst))
        self.assertEqual(set(GRAPH["W4_AND_JOIN"]),
                         {"W0_POSTMERGE_DOV", "W1_W2_OWNER", "GEM_12_IC3", "GEM_50_RULE"})
        self.assertFalse(GRAPH["promotion_authorized"])

    def test_cycle_and_missing_endpoint_fail_closed(self):
        m = _lifecycle("gmic_p0009_negative")
        with self.assertRaisesRegex(ValueError, "cycle"):
            m.topo_layers(GRAPH["nodes"], GRAPH["edges"] + [
                ["W6_CONTROL", "W4_JOIN", "FEEDFORWARD"]])
        with self.assertRaisesRegex(ValueError, "unknown edge"):
            m.topo_layers(GRAPH["nodes"], GRAPH["edges"] + [
                ["UNKNOWN_NODE", "W4_JOIN", "FEEDFORWARD"]])

    def test_owner_authorization_boundaries_remain_open(self):
        self.assertEqual(AUDIT["owner_issue"], "https://github.com/GBOGEB/pipeline-automation-hub/issues/336")
        self.assertEqual(GRAPH["owner_scope"]["HUB_RULE_EFFECTIVE"], "ADMIN_ONLY")
        self.assertEqual(GRAPH["owner_scope"]["GEM_12_IC3"], "GOOGLE_GITHUB_OWNER")


def _builder():
    spec = importlib.util.spec_from_file_location("gmic_p0009_build", HERE / "build_p0009.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ReproducibleRelease(unittest.TestCase):
    """Equal sources give byte-equal ZIPs; a changed source changes the hash."""

    SOURCES = ("POSTMERGE_AUDIT.json", "DAG.json", "DAG.mmd",
               "README.md", "test_p0009.py", "build_p0009.py")

    def setUp(self):
        self.builder = _builder()
        self.tmp = Path(tempfile.mkdtemp(prefix="gmic_p0009_"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        patcher = mock.patch.dict(os.environ)
        patcher.start()
        self.addCleanup(patcher.stop)
        os.environ.pop("SOURCE_DATE_EPOCH", None)

    def _sha(self, archive):
        return hashlib.sha256(archive.read_bytes()).hexdigest()

    def test_two_builds_at_different_times_are_byte_identical(self):
        with mock.patch("time.time", return_value=1_700_000_000.0):
            first = self.builder.build(self.tmp / "a")
        with mock.patch("time.time", return_value=1_800_000_000.0):
            second = self.builder.build(self.tmp / "b")
        self.assertEqual(self._sha(first), self._sha(second))
        receipt = (first.parent / (first.name + ".sha256")).read_bytes()
        self.assertEqual(receipt, (second.parent / (second.name + ".sha256")).read_bytes())
        self.assertEqual(receipt, f"{self._sha(first)}  {first.name}\n".encode("ascii"))
        with zipfile.ZipFile(first) as archive:
            infos = archive.infolist()
            self.assertEqual([i.filename for i in infos], sorted(i.filename for i in infos))
            for info in infos:
                with self.subTest(entry=info.filename):
                    self.assertEqual(info.date_time, (1980, 1, 1, 0, 0, 0))
                    self.assertEqual(info.compress_type, zipfile.ZIP_DEFLATED)
                    self.assertEqual(info.create_system, 3)
                    self.assertEqual(info.external_attr, 0o100644 << 16)

    def test_changed_source_changes_hash(self):
        src = self.tmp / "src"
        src.mkdir()
        for name in self.SOURCES:
            shutil.copyfile(HERE / name, src / name)
        base = self._sha(self.builder.build(self.tmp / "base", src))
        with (src / "README.md").open("a", encoding="utf-8", newline="\n") as stream:
            stream.write("\nchanged\n")
        changed = self._sha(self.builder.build(self.tmp / "changed", src))
        self.assertNotEqual(base, changed)

    def test_source_date_epoch_sets_entry_time_and_is_clamped(self):
        os.environ["SOURCE_DATE_EPOCH"] = "1700000000"  # 2023-11-14T22:13:20Z
        with zipfile.ZipFile(self.builder.build(self.tmp / "sde")) as archive:
            self.assertEqual({i.date_time for i in archive.infolist()},
                             {(2023, 11, 14, 22, 13, 20)})
        os.environ["SOURCE_DATE_EPOCH"] = "0"
        with zipfile.ZipFile(self.builder.build(self.tmp / "clamp")) as archive:
            self.assertEqual({i.date_time for i in archive.infolist()},
                             {(1980, 1, 1, 0, 0, 0)})


if __name__ == "__main__":
    unittest.main()
