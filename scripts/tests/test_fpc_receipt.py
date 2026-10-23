import base64
import contextlib
import importlib.util
import io
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("fpc_receipt", ROOT / "fpc_receipt.py")
fr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fr)
gate = fr.gate

HEAD = "a" * 40
BASE = "c" * 40
REPO = "GBOGEB/example"
PR = 7
PROOF_PATH = ".github/workflows/trusted.yml"
OTHER_PATH = ".github/workflows/other.yml"
WORKFLOW = "name: Trusted Proof\n"
POLICY_PATH = str(ROOT.parent / "mission-control" / "quality" / "FIRST_PASS_CLOSURE_POLICY_v1.json")


def ident(name="Trusted Proof", path=PROOF_PATH):
    return {"repo": REPO, "workflow_name": name, "workflow_path": path}


def policy(allow=None):
    return {
        "protected_control_paths": ["scripts/first_pass_closure_gate.py"],
        "proof_identity_allowlist": allow
        or {p: [ident()] for p in ("canonical_self_test", "mutation_test", "exact_head_ci")},
    }


def content(text):
    return {"encoding": "base64", "content": base64.b64encode(text.encode()).decode()}


def run(run_id, name="Trusted Proof", path=PROOF_PATH, head=HEAD, conclusion="success"):
    return {
        "id": run_id, "name": name, "path": path, "head_sha": head,
        "status": "completed", "conclusion": conclusion,
    }


class FakeClient:
    def __init__(self, runs, body="", head_workflow=WORKFLOW, files=None, extra=None):
        self.patched = []
        self.mapping = {
            f"/repos/{REPO}/pulls/{PR}": {
                "head": {"sha": HEAD}, "base": {"sha": BASE}, "body": body,
            },
            f"/repos/{REPO}/pulls/{PR}/files?per_page=100&page=1": files or [],
            f"/repos/{REPO}/actions/runs?head_sha={HEAD}&status=success&per_page=100&page=1": {
                "workflow_runs": runs
            },
        }
        for r in runs:
            self.mapping[f"/repos/{REPO}/contents/{r['path']}?ref={r['head_sha']}"] = content(head_workflow)
            self.mapping[f"/repos/{REPO}/contents/{r['path']}?ref={BASE}"] = content(WORKFLOW)
        self.mapping.update(extra or {})

    def get(self, path):
        if path not in self.mapping:
            raise AssertionError(f"unexpected gh api call: {path}")
        return self.mapping[path]

    get_all = fr.GhClient.get_all

    def patch_pr_body(self, repo, pr_number, body):
        self.patched.append((repo, pr_number, body))
        self.mapping[f"/repos/{REPO}/pulls/{PR}"]["body"] = body


def call_main(client, *extra, pol=None):
    out, err = io.StringIO(), io.StringIO()
    orig = gate.load_policy
    gate.load_policy = lambda _path: pol or policy()
    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = fr.main(["--pr", str(PR), "--repo", REPO, "--policy", POLICY_PATH, *extra], client=client)
    finally:
        gate.load_policy = orig
    return code, out.getvalue(), err.getvalue()


class ReceiptBuildingTests(unittest.TestCase):
    def test_reuses_gate_module(self):
        self.assertIs(fr.gate.MARKER_RE, gate.MARKER_RE)
        self.assertTrue(hasattr(gate, "allowed_purposes"))

    def test_newest_trusted_run_covers_all_purposes(self):
        client = FakeClient([run(100), run(200), run(150, name="Other", path=OTHER_PATH)])
        receipt, missing, notes, _ = fr.generate(client, REPO, PR, policy())
        self.assertEqual(missing, [])
        self.assertEqual(receipt, {
            "schema": "first_pass_closure/v1",
            "head_sha": HEAD,
            "required_runs": [{"repo": REPO, "run_id": 200}],
        })
        # Round-trips through the gate's own strict parser.
        parsed = gate.parse_receipt(fr.render_marker(receipt))
        self.assertEqual(parsed, receipt)

    def test_split_purposes_select_one_run_each(self):
        allow = {
            "canonical_self_test": [ident()],
            "mutation_test": [ident()],
            "exact_head_ci": [ident("Other", OTHER_PATH)],
        }
        client = FakeClient([run(10), run(11, name="Other", path=OTHER_PATH)])
        receipt, missing, _, _ = fr.generate(client, REPO, PR, policy(allow))
        self.assertEqual(missing, [])
        self.assertEqual(
            sorted(r["run_id"] for r in receipt["required_runs"]), [10, 11]
        )

    def test_filters_wrong_head_and_failed_runs(self):
        runs = [run(5, head="b" * 40), run(6, conclusion="failure")]
        client = FakeClient([])
        client.mapping[
            f"/repos/{REPO}/actions/runs?head_sha={HEAD}&status=success&per_page=100&page=1"
        ] = {"workflow_runs": runs}
        self.assertEqual(fr.list_success_runs(client, REPO, HEAD), [])

    def test_mutated_proof_workflow_is_rejected_with_note(self):
        client = FakeClient([run(300)], head_workflow="name: Tampered\n")
        receipt, missing, notes, _ = fr.generate(client, REPO, PR, policy())
        self.assertEqual(receipt["required_runs"], [])
        self.assertEqual(missing, sorted(gate.REQUIRED_PURPOSES))
        self.assertTrue(any("PROOF_WORKFLOW_MUTATED_FROM_TRUSTED_BASE" in n for n in notes))

    def test_protected_path_change_is_reported(self):
        files = [{"filename": "scripts/first_pass_closure_gate.py"}]
        client = FakeClient([run(1)], files=files)
        _, _, notes, _ = fr.generate(client, REPO, PR, policy())
        self.assertTrue(any("CONTROL_PLANE_CHANGE_REQUIRES_BOOTSTRAP" in n for n in notes))


class PolicyTests(unittest.TestCase):
    def test_default_policy_loads_via_gate(self):
        loaded = gate.load_policy(str(fr.DEFAULT_POLICY))
        self.assertTrue(gate.REQUIRED_PURPOSES <= set(loaded["proof_identity_allowlist"]))


class MissingPurposeTests(unittest.TestCase):
    def test_missing_purposes_listed(self):
        self.assertEqual(
            fr.missing_purposes({"exact_head_ci"}), ["canonical_self_test", "mutation_test"]
        )
        self.assertEqual(fr.missing_purposes(set(gate.REQUIRED_PURPOSES)), [])

    def test_partial_coverage_exits_nonzero_and_does_not_write(self):
        allow = {
            "canonical_self_test": [ident()],
            "mutation_test": [ident("Mut", OTHER_PATH)],
            "exact_head_ci": [ident()],
        }
        client = FakeClient([run(1)])
        code, out, err = call_main(client, "--write", pol=policy(allow))
        self.assertEqual(code, 1)
        self.assertIn("missing_purposes=mutation_test", err)
        self.assertEqual(client.patched, [])

    def test_no_runs_exits_nonzero(self):
        code, _, err = call_main(FakeClient([]))
        self.assertEqual(code, 1)
        self.assertIn("canonical_self_test,exact_head_ci,mutation_test", err)

    def test_gh_failure_exits_two(self):
        client = FakeClient([])
        del client.mapping[f"/repos/{REPO}/pulls/{PR}"]

        def boom(path):
            raise gate.GateError("GH_CLI_FAILED: boom")

        client.get = boom
        code, _, err = call_main(client)
        self.assertEqual(code, 2)
        self.assertIn("GH_CLI_FAILED", err)


class MarkerUpsertTests(unittest.TestCase):
    receipt = {"schema": "first_pass_closure/v1", "head_sha": HEAD,
               "required_runs": [{"repo": REPO, "run_id": 9}]}

    def test_insert_into_body_without_marker(self):
        body = "## Description\nhello\n"
        new = fr.upsert_marker(body, self.receipt)
        self.assertTrue(new.startswith(body.rstrip("\n")))
        self.assertIn(fr.SECTION_HEADING, new)
        self.assertEqual(gate.parse_receipt(new), self.receipt)

    def test_insert_into_empty_body(self):
        new = fr.upsert_marker(None, self.receipt)
        self.assertEqual(gate.parse_receipt(new), self.receipt)

    def test_replaces_template_skeleton_in_place(self):
        skeleton = (
            '<!-- FPC_RECEIPT_V1 {"schema": "first_pass_closure/v1", '
            '"head_sha": "<40-char PR head SHA>", "required_runs": '
            '[{"repo": "GBOGEB/pipeline-automation-hub", "run_id": 0}]} -->'
        )
        body = f"before\n\n{skeleton}\n\nafter\n"
        new = fr.upsert_marker(body, self.receipt)
        self.assertTrue(new.startswith("before\n\n"))
        self.assertTrue(new.endswith("\n\nafter\n"))
        self.assertEqual(len(gate.MARKER_RE.findall(new)), 1)
        self.assertEqual(gate.parse_receipt(new), self.receipt)

    def test_upsert_is_idempotent(self):
        once = fr.upsert_marker("body", self.receipt)
        twice = fr.upsert_marker(once, self.receipt)
        self.assertEqual(once, twice)
        newer = dict(self.receipt, required_runs=[{"repo": REPO, "run_id": 10}])
        updated = fr.upsert_marker(twice, newer)
        self.assertEqual(len(gate.MARKER_RE.findall(updated)), 1)
        self.assertEqual(gate.parse_receipt(updated), newer)

    def test_pr_template_skeleton_is_replaceable(self):
        template = (ROOT.parent / ".github" / "PULL_REQUEST_TEMPLATE.md").read_text(encoding="utf-8")
        self.assertEqual(len(gate.MARKER_RE.findall(template)), 1)
        with self.assertRaises(gate.GateError):
            gate.parse_receipt(template)  # placeholder must never pass the gate
        new = fr.upsert_marker(template, self.receipt)
        self.assertEqual(gate.parse_receipt(new), self.receipt)


class WriteModeTests(unittest.TestCase):
    def test_write_patches_once_then_unchanged(self):
        client = FakeClient([run(42)], body="desc")
        code, out, err = call_main(client, "--write")
        self.assertEqual(code, 0, err)
        self.assertIn("FPC_RECEIPT=WRITTEN", err)
        self.assertEqual(len(client.patched), 1)
        self.assertEqual(gate.parse_receipt(client.patched[0][2])["required_runs"],
                         [{"repo": REPO, "run_id": 42}])
        code, _, err = call_main(client, "--write")
        self.assertEqual(code, 0)
        self.assertIn("FPC_RECEIPT=UNCHANGED", err)
        self.assertEqual(len(client.patched), 1)

    def test_dry_run_default_does_not_patch(self):
        client = FakeClient([run(42)], body="desc")
        code, out, _ = call_main(client)
        self.assertEqual(code, 0)
        self.assertEqual(client.patched, [])
        self.assertIn("FPC_RECEIPT_V1", out)

    def test_ghclient_uses_runner(self):
        calls = []

        def runner(args, stdin):
            calls.append((args, stdin))
            return json.dumps({"ok": True})

        c = fr.GhClient(runner)
        self.assertEqual(c.get("/repos/x/y"), {"ok": True})
        c.patch_pr_body("x/y", 3, "B")
        self.assertEqual(calls[0][0], ["api", "repos/x/y"])
        self.assertEqual(calls[1][0][:4], ["api", "--method", "PATCH", "repos/x/y/pulls/3"])
        self.assertEqual(json.loads(calls[1][1]), {"body": "B"})


if __name__ == "__main__":
    unittest.main()
