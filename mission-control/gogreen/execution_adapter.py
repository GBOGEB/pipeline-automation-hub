#!/usr/bin/env python3
"""Governed local-pilot executor for canonical SIPOC process-instance waves.

Only built-in, path-allowlisted file tasks and a pre-existing Golden Thread
recompute function may run. This does not authorize Crew, GitHub writes, cloud
credentials, merge, or engineering acceptance. The subprocess worker uses a
fixed argv, no shell, and an isolated scratch directory.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import importlib.util
import json
import os
import re
import sqlite3
import subprocess
import sys
import tempfile
import time
from pathlib import Path

SCHEMA = "missioncontrol.gogreen.task-execution.v1"
POLICY_SCHEMA = "missioncontrol.gogreen.local-pilot-policy.v1"
OPS = frozenset({"SOURCE_DIGEST", "JSON_INDEX", "JSON_CANONICAL", "GOLDEN_THREAD_CONE", "OUTPUT_FANIN", "AUDIT_GATE"})
KEY = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,95}\Z")
SHA = re.compile(r"[0-9a-f]{40}\Z")
SCRIPT = Path(__file__).resolve()


class ExecutionHold(RuntimeError):
    pass


def encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n").encode()


def digest(value):
    return hashlib.sha256(value).hexdigest()


def checked_relative(name):
    if (not isinstance(name, str) or not name or name.startswith(("/", "\\"))
            or "\\" in name or "\x00" in name):
        raise ExecutionHold("unsafe relative path")
    parts = name.split("/")
    if any(x in {"", ".", ".."} for x in parts) or ":" in name:
        raise ExecutionHold("unsafe path segments")
    return name


def beneath(root, relative, *, reject_symlinks=True):
    relative = checked_relative(relative)
    root = Path(root).resolve()
    cursor = root
    for part in relative.split("/"):
        cursor = cursor / part
        if reject_symlinks and cursor.is_symlink():
            raise ExecutionHold("symlink path denied")
    if not cursor.resolve().is_relative_to(root):
        raise ExecutionHold("path escapes approved root")
    return cursor


def git(repo, *args):
    p = subprocess.run(["git", "-C", str(repo), *args], capture_output=True,
                       text=True, check=False, timeout=10)
    if p.returncode:
        raise ExecutionHold("git source validation failed")
    return p.stdout.strip()


def verify_source(repo, sha, relative):
    """Reject dirty, untracked or mismatched source bytes before any execution."""
    path = beneath(repo, relative)
    if not path.is_file() or path.is_symlink():
        raise ExecutionHold("missing regular tracked source")
    stored = git(repo, "rev-parse", "HEAD:" + checked_relative(relative))
    actual = git(repo, "hash-object", "--", relative)
    if stored != actual:
        raise ExecutionHold("tracked source bytes differ from source commit")
    return path


def load_module(path, unique):
    spec = importlib.util.spec_from_file_location(unique, path)
    if spec is None or spec.loader is None:
        raise ExecutionHold("declared source module cannot load")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def validate_input(plan, atlas, taskset, policy, source_sha):
    if not isinstance(source_sha, str) or not SHA.fullmatch(source_sha):
        raise ExecutionHold("exact source SHA required")
    if (policy.get("schema") != POLICY_SCHEMA or policy.get("scope") != "LOCAL_PILOT_ONLY"
            or policy.get("remote_dispatch") is not False or policy.get("github_write") is not False
            or policy.get("production_authorized") is not False
            or policy.get("owner_issue") != 529 or policy.get("pilot_enabled") is not True):
        raise ExecutionHold("unapproved execution authority")
    if policy.get("approval_state") != "OWNER_REVIEW_REQUIRED_FOR_PRODUCTION":
        raise ExecutionHold("unexpected pilot approval claim")
    if taskset.get("schema") != SCHEMA or taskset.get("authority_transfer") is not False:
        raise ExecutionHold("wrong task contract")
    if taskset.get("owner_issue") != policy["owner_issue"]:
        raise ExecutionHold("task owner not bound to policy")
    if not isinstance(taskset.get("tasks"), dict):
        raise ExecutionHold("task map missing")
    if type(policy.get("max_parallel")) is not int or not (1 <= policy["max_parallel"] <= 3):
        raise ExecutionHold("concurrency out of bounds")
    if type(policy.get("timeout_seconds")) is not int or not (2 <= policy["timeout_seconds"] <= 60):
        raise ExecutionHold("invalid timeout")
    if type(policy.get("max_attempts")) is not int or not (1 <= policy["max_attempts"] <= 3):
        raise ExecutionHold("retry count unbounded")
    input_paths = policy.get("source_allowlist")
    if (not isinstance(input_paths, list) or not input_paths
            or any(checked_relative(x) != x for x in input_paths)
            or len(input_paths) != len(set(input_paths))):
        raise ExecutionHold("unsafe source allowlist")
    expanded = json.loads(json.dumps(plan).replace("__EVALUATED_SHA__", source_sha))
    module = load_module(SCRIPT.with_name("sipoc_instances.py"), "sipoc_current_producer")
    result = module.plan_instances(expanded, atlas)
    if result.get("dispatch_authorized") is not False or result.get("planned_not_executed") is not True:
        raise ExecutionHold("planner attempted authority transfer")
    planned = {x["id"] for wave in result["schedule"]["waves"] for x in wave}
    all_ids = {x["id"] for x in expanded["instances"]}
    if planned != all_ids or set(taskset["tasks"]) != all_ids:
        raise ExecutionHold("held/undeclared work may not execute")
    if result["schedule"]["max_parallel"] > policy["max_parallel"]:
        raise ExecutionHold("planner exceeds pilot capacity")
    owners = {x["id"]: x for x in expanded["instances"]}
    seen_outputs = []
    for ident, task in taskset["tasks"].items():
        if not isinstance(task, dict) or task.get("operation") not in OPS:
            raise ExecutionHold("non-allowlisted operation")
        node = owners[ident]
        if (node["repo"] != "GBOGEB/pipeline-automation-hub"
                or node["source_sha"] != source_sha
                or node["owner_issue"] != policy["owner_issue"]
                or node["state"] != "READY"
                or node["mode"] == "MUTATION_PROPOSAL"):
            raise ExecutionHold("node source/owner/authority not eligible")
        outs = task.get("outputs")
        if not isinstance(outs, list) or not outs or len(outs) > 4:
            raise ExecutionHold("task must declare bounded output files")
        if len(outs) != len(set(outs)):
            raise ExecutionHold("duplicate task outputs")
        for out in outs:
            checked_relative(out)
            if any(out == old or out.startswith(old + "/") or old.startswith(out + "/")
                   for old in seen_outputs):
                raise ExecutionHold("overlapping output leases")
            seen_outputs.append(out)
        inputs = task.get("inputs", [])
        if not isinstance(inputs, list) or len(inputs) > 5:
            raise ExecutionHold("invalid task inputs")
        for inp in inputs:
            checked_relative(inp)
        if any(inp not in input_paths and inp not in seen_outputs for inp in inputs):
            # Recheck below without task ordering: dependency may appear in a later map key.
            if any(inp not in input_paths and inp not in [p for t in taskset["tasks"].values()
                                                         for p in t.get("outputs", [])] for inp in inputs):
                raise ExecutionHold("input is not allowlisted or produced")
        if task["operation"] not in policy.get("allowed_operations", []):
            raise ExecutionHold("operation lacks policy approval")
        if task["operation"] == "GOLDEN_THREAD_CONE" and task.get("input") != \
                "mission-control/golden-thread/fixtures/GT_BD_002_REAL_CONE_BATCH001_v1.json":
            raise ExecutionHold("recompute profile is fixed to trusted fixture")
        if task.get("input") is not None and task["input"] not in input_paths:
            raise ExecutionHold("source input is not policy-allowlisted")
    return expanded, result


def journal_connection(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path, timeout=10, isolation_level=None)
    con.execute("PRAGMA busy_timeout=10000")
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("CREATE TABLE IF NOT EXISTS attempts (key TEXT PRIMARY KEY, task TEXT, "
                "state TEXT, attempts INTEGER, lease_until REAL, outputs TEXT, error TEXT)")
    return con


def take_lease(db, key, task, max_attempts, output_root):
    db.execute("BEGIN IMMEDIATE")
    try:
        row = db.execute("SELECT state, attempts, lease_until, outputs FROM attempts WHERE key=?", (key,)).fetchone()
        if row:
            state, attempts, until, outputs = row
            if state == "SUCCESS":
                values = json.loads(outputs)
                for name, sha in values.items():
                    path = beneath(output_root, name)
                    if not path.is_file() or digest(path.read_bytes()) != sha:
                        raise ExecutionHold("idempotency receipt/output corruption")
                db.execute("COMMIT")
                return "REUSED", values
            if state == "RUNNING":
                if until < time.time():
                    db.execute("UPDATE attempts SET state='RECOVERY_HOLD' WHERE key=?", (key,))
                    db.execute("COMMIT")
                    raise ExecutionHold("expired lease requires explicit recovery review")
                raise ExecutionHold("lease already held by active worker")
            if state in {"RECOVERY_HOLD", "CANCELLED", "PERMANENT_FAILURE"}:
                raise ExecutionHold("state requires operator intervention")
            if attempts >= max_attempts:
                raise ExecutionHold("retry attempts exhausted")
            attempt = attempts + 1
            db.execute("UPDATE attempts SET state='RUNNING', attempts=?, lease_until=?, error=NULL WHERE key=?",
                       (attempt, time.time() + 90, key))
        else:
            db.execute("INSERT INTO attempts VALUES (?,?,?,?,?,?,?)",
                       (key, task, "RUNNING", 1, time.time() + 90, "{}", ""))
        db.execute("COMMIT")
    except Exception:
        if db.in_transaction:
            db.execute("ROLLBACK")
        raise
    return "RUNNING", {}


def operator_recover(db, key, max_attempts, *, explicit_pilot_authorization=False):
    """Unblock an expired local lease only after a distinct operator action."""
    if explicit_pilot_authorization is not True:
        raise ExecutionHold("pilot recovery needs explicit operator authorization")
    db.execute("BEGIN IMMEDIATE")
    try:
        record = db.execute("SELECT state, attempts FROM attempts WHERE key=?", (key,)).fetchone()
        if not record or record[0] != "RECOVERY_HOLD":
            raise ExecutionHold("only expired RECOVERY_HOLD can be resumed")
        if record[1] >= max_attempts:
            raise ExecutionHold("recovery retry budget exhausted")
        db.execute("UPDATE attempts SET state='RETRYABLE_FAILURE', error='manual pilot recovery' WHERE key=?", (key,))
        db.execute("COMMIT")
    except Exception:
        if db.in_transaction:
            db.execute("ROLLBACK")
        raise
    return {"key": key, "status": "RECOVERY_RELEASED_FOR_NEXT_SEPARATE_RUN",
            "remote_dispatch_authorized": False, "merge_authorized": False}


def mark(db, key, state, outputs=None, error=""):
    db.execute("BEGIN IMMEDIATE")
    try:
        db.execute("UPDATE attempts SET state=?, lease_until=0, outputs=?, error=? WHERE key=?",
                   (state, json.dumps(outputs or {}, sort_keys=True), error[:240], key))
        db.execute("COMMIT")
    except Exception:
        db.execute("ROLLBACK")
        raise


def worker(job_path):
    """Child process. No shell, no network client and no source writes."""
    job = json.loads(Path(job_path).read_text(encoding="utf-8"))
    repo, staged, outroot = (Path(job[k]).resolve() for k in ("repo", "staged", "outroot"))
    if not staged.is_relative_to(outroot):
        raise ExecutionHold("staged output must remain in scratch")
    task = job["task"]
    op = task["operation"]
    if op not in OPS:
        raise ExecutionHold("unknown operation")
    if job["source_sha"] != git(repo, "rev-parse", "HEAD"):
        raise ExecutionHold("actual checkout changed")
    if Path(job["cancel"]).is_file():
        raise ExecutionHold("cancelled before execution")
    inputs = task.get("inputs", [])
    def source_bytes(relative):
        return verify_source(repo, job["source_sha"], relative).read_bytes()
    def write(relative, blob):
        path = beneath(staged, relative)
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            raise ExecutionHold("staging path already exists")
        path.write_bytes(blob)
    def from_output(relative):
        path = beneath(outroot, relative)
        if not path.is_file():
            raise ExecutionHold("upstream output unavailable")
        return path.read_bytes()
    if op == "SOURCE_DIGEST":
        raw = source_bytes(task["input"])
        payload = {"path": task["input"], "source_sha": job["source_sha"],
                   "source_sha256": digest(raw), "byte_count": len(raw)}
        write(task["outputs"][0], encoded(payload))
    elif op == "JSON_INDEX":
        doc = json.loads(source_bytes(task["input"]))
        records = doc.get("records", [])
        if not isinstance(records, list):
            raise ExecutionHold("invalid JSON records")
        payload = {"record_count": len(records),
                   "repositories": sorted({r["repository"] for r in records}),
                   "source_sha": job["source_sha"]}
        write(task["outputs"][0], encoded(payload))
    elif op == "JSON_CANONICAL":
        write(task["outputs"][0], encoded(json.loads(source_bytes(task["input"]))))
    elif op == "GOLDEN_THREAD_CONE":
        source_bytes(task["input"])
        for rel in ("mission-control/golden-thread/dependency_recompute.py",
                    "mission-control/golden-thread/federation_frontier.py",
                    "mission-control/golden-thread/occurrence_connector_adapter.py",
                    "mission-control/golden-thread/fixtures/GT_BD_011_BOOTSTRAP_BATCH001_20260917.json"):
            source_bytes(rel)
        module = load_module(repo / "mission-control/golden-thread/dependency_recompute.py", "source_pinned_cone")
        manifest = json.loads(source_bytes(task["input"]))
        prefix = task["outputs"][0].rsplit("/", 1)[0]
        destination = beneath(staged, prefix)
        result = module.execute_cone(manifest, destination)
        if (result["closure"]["status"] != "PASS" or
                result["closure"]["stale_survivor_count"] != 0 or
                result["closure"]["stale_rendition_count"] != 0 or
                result["summary"]["occurrence_count"] != 4):
            raise ExecutionHold("real recomputation not complete")
    elif op == "OUTPUT_FANIN":
        payload = {"inputs_sha256": {p: digest(from_output(p)) for p in inputs},
                   "sources": len(inputs)}
        write(task["outputs"][0], encoded(payload))
    elif op == "AUDIT_GATE":
        doc = json.loads(from_output(inputs[0]))
        if doc.get("sources", 0) < 2:
            raise ExecutionHold("insufficient real producer fan-in")
        write(task["outputs"][0], encoded({"task_observed": True, "merge_authorized": False,
                                            "engineering_acceptance": False,
                                            "source_sha": job["source_sha"]}))
    if sorted(path.relative_to(staged).as_posix() for path in staged.rglob("*") if path.is_file()) != sorted(task["outputs"]):
        raise ExecutionHold("worker output set differs from predeclared outputs")


async def execute_wave(plan_result, plan, taskset, policy, repo, outroot, ledger, source_sha, cancel_file):
    journal = journal_connection(ledger)
    pilot_results = []
    plan_digest = digest(encoded(plan))
    task_digest = digest(encoded(taskset))
    policy_digest = digest(encoded(policy))
    for wave_no, wave in enumerate(plan_result["schedule"]["waves"], 1):
        if cancel_file.is_file():
            raise ExecutionHold("cancelled before wave " + str(wave_no))
        async def once(item):
            name = item["id"]
            task = taskset["tasks"][name]
            key = digest(encoded({"task": task, "name": name, "source_sha": source_sha,
                                  "plan_sha256": plan_digest, "policy_sha256": policy_digest,
                                  "taskset_sha256": task_digest}))
            state, previous = take_lease(journal, key, name, policy["max_attempts"], outroot)
            if state == "REUSED":
                return {"id": name, "state": "REUSED_VERIFIED", "key": key, "outputs": previous}
            with tempfile.TemporaryDirectory(prefix="task-", dir=outroot) as temp:
                staged = Path(temp) / "stage"
                staged.mkdir()
                config = Path(temp) / "job.json"
                config.write_bytes(encoded({"repo": str(repo), "staged": str(staged),
                                            "outroot": str(outroot), "task": task,
                                            "source_sha": source_sha, "cancel": str(cancel_file)}))
                env = {"PATH": os.getenv("PATH", "/usr/bin:/bin"), "HOME": temp,
                       "PYTHONDONTWRITEBYTECODE": "1", "PYTHONUNBUFFERED": "1"}
                proc = await asyncio.create_subprocess_exec(sys.executable, str(SCRIPT), "--worker", str(config),
                                                            cwd=temp, env=env,
                                                            stdout=asyncio.subprocess.PIPE,
                                                            stderr=asyncio.subprocess.PIPE)
                start = time.monotonic()
                while proc.returncode is None:
                    if cancel_file.is_file() or time.monotonic() - start > policy["timeout_seconds"]:
                        proc.kill()
                        await proc.communicate()
                        mark(journal, key, "CANCELLED" if cancel_file.is_file() else "RETRYABLE_FAILURE",
                             error="cancelled or deadline exceeded")
                        raise ExecutionHold(name + ": cancelled or exceeded hard deadline")
                    try:
                        await asyncio.wait_for(proc.wait(), timeout=0.05)
                    except asyncio.TimeoutError:
                        pass
                stdout, stderr = await proc.communicate()
                if proc.returncode:
                    mark(journal, key, "PERMANENT_FAILURE", error=stderr.decode(errors="replace")[:220])
                    raise ExecutionHold(name + ": worker failed: " + stderr.decode(errors="replace")[-240:])
                paths = {}
                for rel in task["outputs"]:
                    staged_path = beneath(staged, rel)
                    if not staged_path.is_file():
                        mark(journal, key, "PERMANENT_FAILURE", error="missing declared output")
                        raise ExecutionHold("missing declared task output: " + rel)
                    paths[rel] = digest(staged_path.read_bytes())
                if cancel_file.is_file():
                    mark(journal, key, "CANCELLED", error="cancelled prior to output publish")
                    raise ExecutionHold("cancelled before atomic output publication")
                for rel in task["outputs"]:
                    target = beneath(outroot, rel)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    if target.exists():
                        mark(journal, key, "PERMANENT_FAILURE", error="output already exists")
                        raise ExecutionHold("would overwrite existing output")
                    os.replace(beneath(staged, rel), target)
                mark(journal, key, "SUCCESS", outputs=paths)
                return {"id": name, "state": "EXECUTED", "key": key,
                        "wall_seconds": round(time.monotonic()-start, 4),
                        "outputs": paths, "stdout_sha256": digest(stdout)}
        # One batch per canonical planner wave. This is genuine local process concurrency.
        wave_results = await asyncio.gather(*(once(x) for x in wave), return_exceptions=True)
        failure = next((x for x in wave_results if isinstance(x, BaseException)), None)
        pilot_results.append({"wave": wave_no, "tasks": [x if isinstance(x, dict)
                                                        else {"state": "FAILED", "error": str(x)}
                                                        for x in wave_results]})
        if failure:
            raise ExecutionHold("wave " + str(wave_no) + " failed; downstream held: " + str(failure))
    journal.close()
    return {"waves": pilot_results, "tasks_executed": sum(x.get("state") == "EXECUTED"
                  for w in pilot_results for x in w.get("tasks", [])),
            "tasks_reused": sum(x.get("state") == "REUSED_VERIFIED"
                  for w in pilot_results for x in w.get("tasks", []))}


def sign_receipt(payload):
    """Cryptographically valid, but ephemeral/untrusted identity for PR pilots."""
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.exceptions import InvalidSignature
    private = Ed25519PrivateKey.generate()
    public = private.public_key()
    public_bytes = public.public_bytes(encoding=serialization.Encoding.Raw,
                                       format=serialization.PublicFormat.Raw)
    signature = private.sign(encoded(payload))
    try:
        public.verify(signature, encoded(payload))
    except InvalidSignature:
        raise ExecutionHold("receipt signature verification failed")
    return {"algorithm": "Ed25519", "signature_hex": signature.hex(),
            "public_key_hex": public_bytes.hex(),
            "public_key_fingerprint_sha256": digest(public_bytes),
            "signer_trust": "EPHEMERAL_SELF_SIGNED_NOT_OWNER_APPROVAL"}


def verify_receipt(receipt):
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    from cryptography.exceptions import InvalidSignature
    proof = receipt["signature"]
    payload = {k: v for k, v in receipt.items() if k != "signature"}
    if proof.get("signer_trust") != "EPHEMERAL_SELF_SIGNED_NOT_OWNER_APPROVAL":
        raise ExecutionHold("unsupported signer identity")
    key = bytes.fromhex(proof["public_key_hex"])
    if digest(key) != proof["public_key_fingerprint_sha256"]:
        raise ExecutionHold("signer fingerprint does not match")
    try:
        Ed25519PublicKey.from_public_bytes(key).verify(bytes.fromhex(proof["signature_hex"]), encoded(payload))
    except (InvalidSignature, ValueError):
        raise ExecutionHold("receipt signature incorrect")
    return True


def run(args):
    repo = Path(args.repo).resolve()
    out = Path(args.out).resolve()
    if out.is_relative_to(repo):
        raise ExecutionHold("outputs may not modify the repository checkout")
    if args.cancel_file:
        cancel = Path(args.cancel_file).resolve()
        if not cancel.is_relative_to(out):
            raise ExecutionHold("cancellation marker outside scratch")
    else:
        cancel = out / "cancel.requested"
    if not args.allow_local_pilot:
        raise ExecutionHold("explicit local pilot opt-in required")
    source_sha = git(repo, "rev-parse", "HEAD")
    if source_sha != args.source_sha:
        raise ExecutionHold("exact checkout SHA does not match supplied identity")
    paths = ("mission-control/gogreen/sipoc_instances.py", "mission-control/gogreen/execution_adapter.py")
    for rel in paths:
        verify_source(repo, source_sha, rel)
    rawfiles = [Path(x).read_bytes() for x in [args.plan, args.atlas, args.tasks, args.policy]]
    plan, atlas, taskset, policy = [json.loads(x) for x in rawfiles]
    expanded, prepared = validate_input(plan, atlas, taskset, policy, source_sha)
    for relative in policy["source_allowlist"]:
        verify_source(repo, source_sha, relative)
    for parameter in (args.plan, args.atlas, args.tasks, args.policy):
        try:
            source_relative = Path(parameter).resolve().relative_to(repo).as_posix()
        except ValueError:
            raise ExecutionHold("untracked/external task policy or manifest")
        verify_source(repo, source_sha, source_relative)
    out.mkdir(parents=True, exist_ok=True)
    ledger = out / "attempts.sqlite3"
    if getattr(args, "recover_id", None):
        db = journal_connection(ledger)
        try:
            response = operator_recover(db, args.recover_id, policy["max_attempts"],
                                        explicit_pilot_authorization=getattr(args, "allow_pilot_recovery", False))
        finally:
            db.close()
        (out / "pilot_recovery.json").write_bytes(encoded(response))
        print(json.dumps(response, sort_keys=True))
        return response
    result = asyncio.run(execute_wave(prepared, expanded, taskset, policy, repo, out,
                                      ledger, source_sha, cancel))
    planned_count = sum(map(len, prepared["schedule"]["waves"]))
    if result["tasks_executed"] + result["tasks_reused"] != planned_count:
        raise ExecutionHold("some planned tasks were not executed")
    receipt = {"schema": "missioncontrol.gogreen.execution-receipt.v1",
               "source_sha": source_sha, "operation": "LOCAL_SIPOC_FILE_TASK_EXECUTION",
               "git_source_verified": True,
               "input_sha256": dict(zip(("plan", "atlas", "tasks", "policy"), (digest(x) for x in rawfiles))),
               "execution": result, "synthetic": False,
               "native_github_run_id": os.environ.get("GITHUB_RUN_ID"),
               "native_github_attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
               "remote_dispatch_authorized": False, "engineering_acceptance": False,
               "independently_approved": False, "merge_authorized": False,
               "signed_by_trusted_owner": False}
    receipt["signature"] = sign_receipt(receipt)
    assert verify_receipt(receipt)
    output = encoded(receipt)
    (out / "execution_receipt.json").write_bytes(output)
    (out / "execution_receipt.sha256").write_text(digest(output) + "\n", encoding="ascii")
    print(json.dumps({"result": "ACTUAL_LOCAL_PILOT_PASS", "source_sha": source_sha,
                      **result}, sort_keys=True))
    return receipt


def main():
    if len(sys.argv) >= 3 and sys.argv[1] == "--worker":
        worker(sys.argv[2])
        return
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--repo", required=True)
    p.add_argument("--plan", required=True)
    p.add_argument("--atlas", required=True)
    p.add_argument("--tasks", required=True)
    p.add_argument("--policy", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--source-sha", required=True)
    p.add_argument("--allow-local-pilot", action="store_true")
    p.add_argument("--cancel-file")
    p.add_argument("--recover-id", help="journal idempotency key in RECOVERY_HOLD only")
    p.add_argument("--allow-pilot-recovery", action="store_true")
    p.add_argument("--verify-receipt", action="store_true")
    a = p.parse_args()
    if a.verify_receipt:
        v = json.loads((Path(a.out)/"execution_receipt.json").read_bytes())
        if not verify_receipt(v):
            raise ExecutionHold("verification failed")
        print("EPHEMERAL_ED25519_SIGNATURE_VERIFIED_NOT_OWNER_ADMISSION")
    else:
        run(a)


if __name__ == "__main__":
    try:
        main()
    except (ExecutionHold, OSError, KeyError, ValueError, sqlite3.Error) as exc:
        print("EXECUTION_HOLD: " + str(exc), file=sys.stderr)
        sys.exit(2)
