"""Operational and adversarial controls for the governed pilot task executor."""
from __future__ import annotations

import copy
import importlib.util
import json
import pathlib
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest
from types import SimpleNamespace

HERE = pathlib.Path(__file__).resolve().parent
GOGREEN = HERE.parent
spec = importlib.util.spec_from_file_location("execution_adapter_tested", GOGREEN / "execution_adapter.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class ExecutionAdapterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.repo = pathlib.Path(cls.tmp.name) / "repo"
        cls.repo.mkdir()
        for rel in ["mission-control/gogreen/execution_adapter.py",
                    "mission-control/gogreen/sipoc_instances.py",
                    "mission-control/gogreen/samples/execution_plan_pilot_v1.json",
                    "mission-control/gogreen/samples/task_bindings_pilot_v1.json",
                    "mission-control/gogreen/samples/execution_policy_pilot_v1.json",
                    "mission-control/federation-atlas/PROCESS_LANES_v1.json"]:
            src = GOGREEN.parents[1] / rel
            dst = cls.repo / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, dst)
        fixtures = cls.repo / "mission-control/golden-thread/fixtures"
        fixtures.mkdir(parents=True)
        records = [{"repository": f"GBOGEB/repo-{i}", "object_type": "issue",
                    "anchor_sha": "a" * 40, "snapshot": {"number": i}} for i in range(4)]
        (fixtures/"GT_BD_011_BOOTSTRAP_BATCH001_20260917.json").write_text(json.dumps({"records": records}))
        (fixtures/"GT_BD_002_REAL_CONE_BATCH001_v1.json").write_text(json.dumps({"expected": {"status": "PASS"}}))
        gt = cls.repo / "mission-control/golden-thread"
        for fname in ["federation_frontier.py", "occurrence_connector_adapter.py"]:
            (gt/fname).write_text("# pinned test stub\n")
        (gt/"dependency_recompute.py").write_text('''import json
from pathlib import Path

def execute_cone(manifest, out):
    out=Path(out); out.mkdir(parents=True,exist_ok=True)
    for fname in ("bootstrap-summary.json", "normalized-occurrence-projection.json"):
        (out/fname).write_text(json.dumps({"source": "real_file", "occurrence_count": 4}) + "\\n")
    return {"closure":{"status":"PASS", "stale_survivor_count":0, "stale_rendition_count":0},
            "summary":{"occurrence_count":4}}
''')
        subprocess.run(["git", "init", "-q", str(cls.repo)], check=True)
        subprocess.run(["git", "-C", str(cls.repo), "config", "user.email", "test@example.invalid"], check=True)
        subprocess.run(["git", "-C", str(cls.repo), "config", "user.name", "SIPOC Test"], check=True)
        subprocess.run(["git", "-C", str(cls.repo), "add", "."], check=True)
        subprocess.run(["git", "-C", str(cls.repo), "commit", "-qm", "source fixture"], check=True)
        cls.sha = mod.git(cls.repo, "rev-parse", "HEAD")
        s = cls.repo / "mission-control/gogreen/samples"
        cls.plan_file=s/"execution_plan_pilot_v1.json"
        cls.policy_file=s/"execution_policy_pilot_v1.json"
        cls.tasks_file=s/"task_bindings_pilot_v1.json"
        cls.atlas_file=cls.repo/"mission-control/federation-atlas/PROCESS_LANES_v1.json"
        cls.plan = json.loads(cls.plan_file.read_text())
        cls.policy = json.loads(cls.policy_file.read_text())
        cls.tasks = json.loads(cls.tasks_file.read_text())
        cls.atlas = json.loads(cls.atlas_file.read_text())
        cls.cached_out=pathlib.Path(cls.tmp.name)/"base-real-run"
        cls.cached_args=SimpleNamespace(repo=str(cls.repo),plan=str(cls.plan_file),
                                       atlas=str(cls.atlas_file),tasks=str(cls.tasks_file),
                                       policy=str(cls.policy_file),out=str(cls.cached_out),
                                       source_sha=cls.sha,allow_local_pilot=True,cancel_file=None)
        cls.cached_receipt=mod.run(cls.cached_args)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def setUp(self):
        self.output = tempfile.TemporaryDirectory()
        self.out = pathlib.Path(self.output.name)/"run"

    def tearDown(self):
        self.output.cleanup()

    def args(self, allow=True):
        return SimpleNamespace(repo=str(self.repo),plan=str(self.plan_file),
                               atlas=str(self.atlas_file),tasks=str(self.tasks_file),
                               policy=str(self.policy_file),out=str(self.out),
                               source_sha=self.sha,allow_local_pilot=allow,cancel_file=None)

    def test_real_asyncio_local_runner_produces_outputs(self):
        receipt = self.cached_receipt
        self.out = self.cached_out
        self.assertFalse(receipt["synthetic"])
        self.assertEqual(receipt["execution"]["tasks_executed"], 6)
        self.assertTrue(mod.verify_receipt(receipt))
        self.assertEqual(json.loads((self.out/"i/source_index.json").read_text())["record_count"], 4)
        self.assertEqual(len(list((self.out/"p-cone").glob("*.json"))), 2)
        self.assertEqual(json.loads((self.out/"o/projection_index.json").read_text())["sources"], 3)
        self.assertFalse(receipt["signed_by_trusted_owner"])
        self.assertFalse(receipt["remote_dispatch_authorized"])

    def test_repeated_execution_is_idempotently_reused(self):
        self.out = self.cached_out
        first = self.cached_receipt
        sha = mod.digest((self.out/"p-canon/canonical.json").read_bytes())
        second = mod.run(self.args())
        self.assertEqual(first["execution"]["tasks_executed"], 6)
        self.assertEqual(second["execution"]["tasks_executed"], 0)
        self.assertEqual(second["execution"]["tasks_reused"], 6)
        self.assertEqual(mod.digest((self.out/"p-canon/canonical.json").read_bytes()), sha)

    def test_corrupted_output_fails_closed_on_reuse(self):
        shutil.copytree(self.cached_out,self.out)
        (self.out/"s/source_digest.json").write_text('changed')
        with self.assertRaisesRegex(mod.ExecutionHold, "corruption"):
            mod.run(self.args())

    def test_preexisting_cancel_marker_rejects_all_waves(self):
        self.out.mkdir()
        (self.out/"cancel.requested").touch()
        with self.assertRaisesRegex(mod.ExecutionHold, "cancelled"):
            mod.run(self.args())
        self.assertFalse((self.out/"execution_receipt.json").exists())

    def test_missing_explicit_opt_in_rejected(self):
        with self.assertRaisesRegex(mod.ExecutionHold, "opt-in"):
            mod.run(self.args(allow=False))

    def test_unexpected_source_sha_rejected(self):
        a=self.args(); a.source_sha='f'*40
        with self.assertRaisesRegex(mod.ExecutionHold, "SHA does not match"):
            mod.run(a)

    def test_wrong_policy_authority_denied(self):
        policy=copy.deepcopy(self.policy);policy["remote_dispatch"]=True
        with self.assertRaisesRegex(mod.ExecutionHold, "authority"):
            mod.validate_input(self.plan,self.atlas,self.tasks,policy,self.sha)

    def test_unknown_command_rejected_without_shell(self):
        jobs=copy.deepcopy(self.tasks)
        jobs["tasks"]["P-CANON"]["operation"]="SHELL_EXECUTE"
        with self.assertRaisesRegex(mod.ExecutionHold, "non-allowlisted"):
            mod.validate_input(self.plan,self.atlas,jobs,self.policy,self.sha)

    def test_absolute_or_traversal_output_rejected(self):
        for path in ["../escape", "/etc/passwd", "other/../../escape"]:
            with self.subTest(path=path):
                jobs=copy.deepcopy(self.tasks)
                jobs["tasks"]["P-CANON"]["outputs"]=[path]
                with self.assertRaises(mod.ExecutionHold):
                    mod.validate_input(self.plan,self.atlas,jobs,self.policy,self.sha)

    def test_overlapping_mutation_lease_rejected(self):
        jobs=copy.deepcopy(self.tasks)
        jobs["tasks"]["P-CANON"]["outputs"]=["p-canon/canonical.json", "p-cone"]
        with self.assertRaisesRegex(mod.ExecutionHold, "overlapping"):
            mod.validate_input(self.plan,self.atlas,jobs,self.policy,self.sha)

    def test_proof_pending_task_does_not_execute(self):
        plan=copy.deepcopy(self.plan)
        plan["instances"][2]["state"]="PROOF_PENDING"
        with self.assertRaisesRegex(mod.ExecutionHold, "held/undeclared"):
            mod.validate_input(plan,self.atlas,self.tasks,self.policy,self.sha)

    def test_receipt_tampering_invalidates_signature(self):
        doc=copy.deepcopy(self.cached_receipt)
        doc["execution"]["tasks_executed"]=900
        with self.assertRaisesRegex(mod.ExecutionHold, "signature"):
            mod.verify_receipt(doc)

    def test_symlink_escape_denied(self):
        self.out.mkdir()
        (self.out/"escape").symlink_to("/tmp")
        with self.assertRaisesRegex(mod.ExecutionHold, "symlink"):
            mod.beneath(self.out,"escape/data.json")

    def test_stale_lease_requires_explicit_recovery(self):
        db=mod.journal_connection(self.out/"journal.db")
        db.execute("INSERT INTO attempts VALUES (?,?,?,?,?,?,?)",
                   ('deadbeef', 'P-CANON', 'RUNNING', 1, time.time()-10,'{}',''))
        with self.assertRaisesRegex(mod.ExecutionHold, "recovery review"):
            mod.take_lease(db,'deadbeef','P-CANON',2,self.out)
        self.assertEqual(db.execute("SELECT state FROM attempts").fetchone()[0],"RECOVERY_HOLD")
        with self.assertRaisesRegex(mod.ExecutionHold, "intervention"):
            mod.take_lease(db,'deadbeef','P-CANON',2,self.out)
        db.close()

    def test_operator_only_recovery_preserves_retry_budget(self):
        db=mod.journal_connection(self.out/"journal.db")
        db.execute("INSERT INTO attempts VALUES (?,?,?,?,?,?,?)",
                   ('recover','P-CANON','RECOVERY_HOLD',1,0,'{}',''))
        with self.assertRaisesRegex(mod.ExecutionHold,"operator"):
            mod.operator_recover(db,'recover',2)
        result=mod.operator_recover(db,'recover',2,explicit_pilot_authorization=True)
        self.assertEqual(result['status'], 'RECOVERY_RELEASED_FOR_NEXT_SEPARATE_RUN')
        self.assertEqual(db.execute("SELECT state FROM attempts").fetchone()[0], 'RETRYABLE_FAILURE')
        self.assertEqual(mod.take_lease(db,'recover','P-CANON',2,self.out)[0], 'RUNNING')
        self.assertEqual(db.execute("SELECT attempts FROM attempts").fetchone()[0], 2)
        db.close()

    def test_active_lease_does_not_run_twice(self):
        db=mod.journal_connection(self.out/"journal.db")
        db.execute("INSERT INTO attempts VALUES (?,?,?,?,?,?,?)",
                   ('occupied','P-CANON','RUNNING',1,time.time()+60,'{}',''))
        with self.assertRaisesRegex(mod.ExecutionHold, "held"):
            mod.take_lease(db,'occupied','P-CANON',2,self.out)
        db.close()

    def test_exhausted_retry_budget_withholds(self):
        db=mod.journal_connection(self.out/"journal.db")
        db.execute("INSERT INTO attempts VALUES (?,?,?,?,?,?,?)",
                   ('failed','P-CANON','RETRYABLE_FAILURE',2,0,'{}',''))
        with self.assertRaisesRegex(mod.ExecutionHold, "exhausted"):
            mod.take_lease(db,'failed','P-CANON',2,self.out)
        db.close()

    def test_untracked_task_manifest_rejected(self):
        file=pathlib.Path(self.output.name)/"external.json"
        file.write_text(self.tasks_file.read_text())
        args=self.args();args.tasks=str(file)
        with self.assertRaisesRegex(mod.ExecutionHold, "external"):
            mod.run(args)

    def test_actual_file_source_drift_is_detected(self):
        raw=(self.repo/"mission-control/golden-thread/fixtures/GT_BD_011_BOOTSTRAP_BATCH001_20260917.json")
        original=raw.read_bytes()
        try:
            raw.write_bytes(original+b"\n")
            with self.assertRaisesRegex(mod.ExecutionHold, "tracked source bytes differ"):
                mod.verify_source(self.repo,self.sha,
                   "mission-control/golden-thread/fixtures/GT_BD_011_BOOTSTRAP_BATCH001_20260917.json")
        finally:
            raw.write_bytes(original)

if __name__=="__main__":
    unittest.main()
