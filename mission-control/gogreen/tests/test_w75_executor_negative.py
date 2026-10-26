"""W75 governed local executor: bounded authority, source and lease adversarial controls."""
from __future__ import annotations

import copy
import importlib.util
import json
import pathlib
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("w75_executor", ROOT / "execution_adapter.py")
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)
SHA = "a" * 40


class W75ExecutorNegatives(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        samples = ROOT / "samples"
        cls.plan = json.loads((samples / "execution_plan_pilot_v1.json").read_text(encoding="utf-8"))
        cls.taskset = json.loads((samples / "task_bindings_pilot_v1.json").read_text(encoding="utf-8"))
        cls.policy = json.loads((samples / "execution_policy_pilot_v1.json").read_text(encoding="utf-8"))
        cls.atlas = json.loads((ROOT.parent / "federation-atlas" / "PROCESS_LANES_v1.json").read_text(encoding="utf-8"))

    def check(self, *, policy=None, tasks=None, plan=None, sha=SHA):
        return MOD.validate_input(plan if plan is not None else copy.deepcopy(self.plan),
                                  self.atlas, tasks if tasks is not None else copy.deepcopy(self.taskset),
                                  policy if policy is not None else copy.deepcopy(self.policy), sha)

    def policy_with(self, key, value):
        policy = copy.deepcopy(self.policy)
        policy[key] = value
        return policy

    def task_with(self, ident, key, value):
        tasks = copy.deepcopy(self.taskset)
        tasks["tasks"][ident][key] = value
        return tasks

    def test_control_plan_is_valid_and_has_no_execution_authority(self):
        expanded, result = self.check()
        self.assertEqual(len(expanded["instances"]), 6)
        self.assertIs(result["dispatch_authorized"], False)
        self.assertIs(result["planned_not_executed"], True)

    def test_source_sha_type_and_length_are_fail_closed(self):
        for sha in (None, False, True, 1, "x" * 40, "a" * 39, "A" * 40):
            with self.subTest(sha=sha), self.assertRaisesRegex(MOD.ExecutionHold, "exact source SHA"):
                self.check(sha=sha)

    def test_remote_and_production_authority_are_denied(self):
        for key, bad in (("remote_dispatch", True), ("github_write", True),
                         ("production_authorized", True), ("pilot_enabled", False),
                         ("scope", "PRODUCTION"), ("owner_issue", 530)):
            with self.subTest(key=key), self.assertRaisesRegex(MOD.ExecutionHold, "authority"):
                self.check(policy=self.policy_with(key, bad))

    def test_policy_schema_and_approval_drift_are_denied(self):
        for key, bad in (("schema", "other"), ("approval_state", "APPROVED")):
            with self.subTest(key=key), self.assertRaises(MOD.ExecutionHold):
                self.check(policy=self.policy_with(key, bad))

    def test_boolean_parallelism_is_not_an_integer_budget(self):
        for value in (True, False):
            with self.subTest(value=value), self.assertRaisesRegex(MOD.ExecutionHold, "concurrency"):
                self.check(policy=self.policy_with("max_parallel", value))

    def test_parallelism_overflow_underflow_and_fraction_denied(self):
        for value in (0, -1, 4, 100, 2.0, "2", None):
            with self.subTest(value=value), self.assertRaisesRegex(MOD.ExecutionHold, "concurrency"):
                self.check(policy=self.policy_with("max_parallel", value))

    def test_timeout_requires_strict_bounded_integer(self):
        for value in (None, False, True, 0, 1, 61, 20.0, "20", -1):
            with self.subTest(value=value), self.assertRaisesRegex(MOD.ExecutionHold, "timeout"):
                self.check(policy=self.policy_with("timeout_seconds", value))

    def test_retries_require_strict_bounded_integer(self):
        for value in (None, False, True, 0, 4, 2.0, "2", -1):
            with self.subTest(value=value), self.assertRaisesRegex(MOD.ExecutionHold, "retry"):
                self.check(policy=self.policy_with("max_attempts", value))

    def test_all_allowed_lower_and_upper_budget_edges(self):
        for parallel, timeout, attempts in ((2, 2, 1), (3, 60, 3)):
            policy = copy.deepcopy(self.policy)
            policy.update(max_parallel=parallel, timeout_seconds=timeout, max_attempts=attempts)
            with self.subTest(policy=policy):
                self.assertIs(self.check(policy=policy)[1]["planned_not_executed"], True)

    def test_allowlist_must_be_nonempty_unique_and_safe(self):
        first = self.policy["source_allowlist"][0]
        for value in ([], (), [first, first], ["/absolute"], ["../escape"],
                      ["a\\b"], [""], ["a//b"]):
            with self.subTest(value=value), self.assertRaises(MOD.ExecutionHold):
                self.check(policy=self.policy_with("source_allowlist", value))

    def test_unknown_or_unapproved_operation_is_denied(self):
        with self.assertRaisesRegex(MOD.ExecutionHold, "non-allowlisted"):
            self.check(tasks=self.task_with("P-CANON", "operation", "REMOTE_COMMAND"))
        with self.assertRaisesRegex(MOD.ExecutionHold, "policy approval"):
            self.check(policy=self.policy_with("allowed_operations", ["SOURCE_DIGEST"]))

    def test_untracked_input_and_policy_unlisted_source_denied(self):
        with self.assertRaisesRegex(MOD.ExecutionHold, "allowlisted"):
            self.check(tasks=self.task_with("P-CANON", "input", "other/file.json"))
        with self.assertRaisesRegex(MOD.ExecutionHold, "not allowlisted or produced"):
            self.check(tasks=self.task_with("O-JOIN", "inputs", ["unknown/upstream.json"]))

    def test_golden_cone_must_use_fixed_source(self):
        with self.assertRaisesRegex(MOD.ExecutionHold, "fixed"):
            self.check(tasks=self.task_with("P-CONE", "input", self.policy["source_allowlist"][1]))

    def test_output_aliases_duplicate_and_escape_denied(self):
        for outputs in (["same.json", "same.json"], ["../escape"], ["/escape"],
                        ["a\\b"], [], ["1","2","3","4","5"]):
            with self.subTest(outputs=outputs), self.assertRaises(MOD.ExecutionHold):
                self.check(tasks=self.task_with("P-CANON", "outputs", outputs))

    def test_output_parent_child_overlap_denied(self):
        with self.assertRaisesRegex(MOD.ExecutionHold, "overlapping"):
            self.check(tasks=self.task_with("P-CANON", "outputs",
                                            ["p-canon/canonical.json", "p-cone"]))

    def test_too_many_or_unsafe_task_inputs_denied(self):
        for inputs in (["a"] * 6, ["/etc/passwd"], ["../out"]):
            with self.subTest(inputs=inputs), self.assertRaises(MOD.ExecutionHold):
                self.check(tasks=self.task_with("O-JOIN", "inputs", inputs))

    def test_task_owner_and_taskset_roster_mismatch_denied(self):
        tasks = copy.deepcopy(self.taskset)
        tasks["owner_issue"] = 1
        with self.assertRaisesRegex(MOD.ExecutionHold, "task owner"):
            self.check(tasks=tasks)
        tasks = copy.deepcopy(self.taskset)
        del tasks["tasks"]["S-READ"]
        with self.assertRaisesRegex(MOD.ExecutionHold, "held/undeclared"):
            self.check(tasks=tasks)

    def test_node_source_owner_and_ready_state_cannot_drift(self):
        for key, bad in (("repo", "GBOGEB/ABACUS"), ("owner_issue", 530),
                         ("source_sha", "b" * 40), ("state", "BLOCKED")):
            p = copy.deepcopy(self.plan)
            p["instances"][0][key] = bad
            with self.subTest(key=key), self.assertRaises((MOD.ExecutionHold, ValueError)):
                self.check(plan=p)

    def test_task_contract_and_unknown_task_map_denied(self):
        for key, value in (("schema", "other"), ("authority_transfer", True),
                           ("tasks", [])):
            t = copy.deepcopy(self.taskset)
            t[key] = value
            with self.subTest(key=key), self.assertRaises(MOD.ExecutionHold):
                self.check(tasks=t)

    def test_relative_path_grammar_reverse_edges(self):
        for path in ("", ".", "..", "a/../b", "a/./b", "//srv", "\\root", "C:/disk",
                     "a//b", "a\\b", "bad\x00key"):
            with self.subTest(path=repr(path)), self.assertRaises(MOD.ExecutionHold):
                MOD.checked_relative(path)
        for path in ("a.json", "folder/a.json", "dash-name/under_score.txt"):
            self.assertEqual(MOD.checked_relative(path), path)

    def test_symlink_path_denied_without_external_write(self):
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            (root / "shortcut").symlink_to(root)
            with self.assertRaisesRegex(MOD.ExecutionHold, "symlink"):
                MOD.beneath(root, "shortcut/payload.json")
            self.assertEqual(MOD.beneath(root, "safe/file.json"), root / "safe/file.json")


if __name__ == "__main__":
    unittest.main()
