"""Read-only SIPOC process-instance DAG planner and bounded asyncio dry-run.

Consume the existing Method Atlas lane definitions; never dispatch GitHub,
Crew, source mutations, or claim synthetic execution as engineering proof.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

SCHEMA = "missioncontrol.sipoc-process-instances.v1"
OUTPUT_SCHEMA = "missioncontrol.sipoc-instance-receipt.v1"
ROLES = "SIPOC"
STATES = {"READY", "BLOCKED", "PROOF_PENDING"}
MODES = {"OBSERVE", "NATIVE_PROVE", "MUTATION_PROPOSAL"}
EXECUTIONS = {"SYNC", "ASYNCIO"}
SHA40 = re.compile(r"[0-9a-f]{40}\Z")
KEY = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,95}\Z")


def _integer(value, name, lower=1, upper=100):
    if type(value) is not int or not lower <= value <= upper:
        raise ValueError(f"invalid {name}")
    return value


def _identifier(value, name):
    if not isinstance(value, str) or not KEY.fullmatch(value):
        raise ValueError(f"invalid {name}")
    return value


def _canonical_path(path):
    if not isinstance(path, str) or not path or path.startswith(("/", "\\")):
        raise ValueError("invalid path lease")
    if "\\" in path or any(p in {".", "..", ""} for p in path.split("/")):
        raise ValueError("noncanonical path lease")
    return path.casefold()


def _intersects(a, b):
    return a == b or a.startswith(b + "/") or b.startswith(a + "/")


def _stage_ids(atlas):
    if (not isinstance(atlas, dict)
            or atlas.get("schema") != "missioncontrol.federation_atlas.process_lanes.v1"
            or atlas.get("observer_authority") != "READ_ONLY"):
        raise ValueError("canonical Method Atlas source missing")
    if [s.get("key") for s in atlas.get("sipoc", [])] != list(ROLES):
        raise ValueError("canonical SIPOC order mismatch")
    stages = []
    for lane in atlas.get("lanes", []):
        if not isinstance(lane, dict) or not lane.get("id"):
            raise ValueError("invalid lane")
        for item in lane.get("stages", []):
            if not isinstance(item, list) or len(item) != 6:
                raise ValueError("invalid Method Atlas stage")
            stages.append(f"{lane['id']}:{item[0]}")
    if not stages or len(stages) != len(set(stages)):
        raise ValueError("empty or duplicate Method Atlas stage")
    return set(stages)


def validate(plan, atlas):
    allowed = _stage_ids(atlas)
    if (not isinstance(plan, dict) or plan.get("schema") != SCHEMA
            or plan.get("authority_transfer") is not False
            or plan.get("dispatch_authorized") is not False):
        raise ValueError("process schema or authority boundary")
    capacity = _integer(plan.get("max_parallel"), "max_parallel", upper=6)
    repo_capacity = _integer(plan.get("max_parallel_per_repo"), "repo capacity", upper=capacity)
    items = plan.get("instances")
    if not isinstance(items, list) or not 0 < len(items) <= 64:
        raise ValueError("invalid process instances")
    by_id, roots, incarnations = {}, {}, set()
    for item in items:
        if not isinstance(item, dict):
            raise ValueError("invalid process instance")
        ident = _identifier(item.get("id"), "instance id")
        if ident in by_id:
            raise ValueError("duplicate instance identity")
        by_id[ident] = item
        _identifier(item.get("incarnation"), "incarnation")
        incarnation_key = (item.get("repo"), item.get("stage_ref"),
                           item.get("sipoc_role"), item["incarnation"])
        if incarnation_key in incarnations:
            raise ValueError("duplicate process incarnation")
        incarnations.add(incarnation_key)
        if item.get("sipoc_role") not in ROLES or item.get("stage_ref") not in allowed:
            raise ValueError("unregistered SIPOC role or stage")
        if item.get("state") not in STATES or item.get("mode") not in MODES:
            raise ValueError("invalid instance state or mode")
        if item.get("execution") not in EXECUTIONS:
            raise ValueError("invalid execution kind")
        if not isinstance(item.get("repo"), str) or item["repo"].count("/") != 1:
            raise ValueError("invalid source repository")
        if not SHA40.fullmatch(str(item.get("source_sha", ""))):
            raise ValueError("source SHA missing")
        _integer(item.get("owner_issue"), "owner issue", upper=999999999)
        if not isinstance(item.get("success_predicate"), str) or not item["success_predicate"].strip():
            raise ValueError("missing success predicate")
        dependencies = item.get("depends_on")
        if not isinstance(dependencies, list) or not all(
                isinstance(d, str) for d in dependencies):
            raise ValueError("invalid dependency identity")
        if len(dependencies) != len(set(dependencies)):
            raise ValueError("duplicate dependencies")
        paths = item.get("mutation_paths", [])
        if not isinstance(paths, list):
            raise ValueError("mutation paths must be a list")
        normalized = [_canonical_path(p) for p in paths]
        if len(set(normalized)) != len(normalized):
            raise ValueError("duplicate mutation path")
        if item["mode"] == "MUTATION_PROPOSAL" and not paths:
            raise ValueError("mutation proposal needs source path lease")
        if item["mode"] != "MUTATION_PROPOSAL" and paths:
            raise ValueError("read-only instance cannot lease mutation paths")
        blockers = item.get("blockers", [])
        if not isinstance(blockers, list) or not all(isinstance(b, str) and b for b in blockers):
            raise ValueError("invalid blockers")
        if item["state"] == "BLOCKED" and not blockers:
            raise ValueError("blocked instance needs reason")
        if item["state"] == "READY" and blockers:
            raise ValueError("ready instance cannot carry blockers")
        root = item.get("root_id")
        if root is not None:
            _identifier(root, "root id")
            owner = (item["repo"], item["owner_issue"])
            if root in roots and roots[root] != owner:
                raise ValueError("root owner mismatch")
            roots[root] = owner
    for item in items:
        if item["id"] in item["depends_on"] or any(d not in by_id for d in item["depends_on"]):
            raise ValueError("unknown or self dependency")
    visiting, visited = set(), set()

    def walk(ident):
        if ident in visiting:
            raise ValueError("same-pulse DAG cycle")
        if ident not in visited:
            visiting.add(ident)
            for parent in by_id[ident]["depends_on"]:
                walk(parent)
            visiting.remove(ident)
            visited.add(ident)

    for ident in by_id:
        walk(ident)
    feedback = plan.get("next_pulse_feedback", [])
    if not isinstance(feedback, list):
        raise ValueError("invalid next-pulse feedback")
    for edge in feedback:
        if (not isinstance(edge, dict) or edge.get("from") not in by_id
                or edge.get("to_stage_ref") not in allowed
                or edge.get("phase") != "NEXT_PULSE"):
            raise ValueError("feedback must target an explicit next pulse")
    return capacity, repo_capacity, by_id



_HANDOFF_SHA = re.compile(r'[0-9a-f]{40}\Z')
_HANDOFF_DIGEST = re.compile(r'[0-9a-f]{64}\Z')
_HANDOFF_EDGE_TYPES = {'CONTINUE_NEXT', 'SELF_REENTRY', 'PAY_IT_FORWARD'}
_HANDOFF_EVIDENCE = {'OBSERVED', 'DECLARED', 'SYNTHETIC'}


def _project_handoffs(plan, by_id, allowed):
    """Opt-in typed edge projection; no native admission or work dispatch."""
    edges = plan.get('handoffs', [])
    if not isinstance(edges, list) or len(edges) > 128:
        raise ValueError('invalid handoff population')
    keys, projection = set(), []
    for edge in edges:
        if not isinstance(edge, dict) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._:-]{0,95}', str(edge.get('id', ''))):
            raise ValueError('invalid handoff identity')
        ident = edge['id']
        if ident in keys:
            raise ValueError('duplicate handoff identity')
        keys.add(ident)
        kind = edge.get('edge_type')
        if kind not in _HANDOFF_EDGE_TYPES:
            raise ValueError('unknown handoff edge type')
        producer = by_id.get(edge.get('producer'))
        if producer is None:
            raise ValueError('unknown handoff producer')
        for name in ('authority_transfer', 'dispatch_authorized', 'merge_authorized'):
            if edge.get(name) is not False:
                raise ValueError('handoff cannot grant execution or authority')
        if edge.get('source_sha') != producer['source_sha']:
            raise ValueError('handoff source SHA mismatch')
        receipt = edge.get('producer_receipt_sha256')
        proof = edge.get('consumer_receipt_sha256')
        if receipt is not None and (not isinstance(receipt, str) or not _HANDOFF_DIGEST.fullmatch(receipt)):
            raise ValueError('malformed handoff producer receipt')
        if proof is not None and (not isinstance(proof, str) or not _HANDOFF_DIGEST.fullmatch(proof)):
            raise ValueError('malformed handoff consumer receipt')
        consumer_head = edge.get('consumer_source_sha')
        if consumer_head is not None and (not isinstance(consumer_head, str) or not _HANDOFF_SHA.fullmatch(consumer_head)):
            raise ValueError('malformed consumer source SHA')
        if edge.get('evidence_class') not in _HANDOFF_EVIDENCE:
            raise ValueError('invalid handoff evidence class')
        sp, tp = edge.get('source_pulse'), edge.get('target_pulse')
        if type(sp) is not int or type(tp) is not int or not 0 <= sp <= 100000 or not 0 <= tp <= 100000:
            raise ValueError('invalid handoff pulse identity')
        consumer_id = edge.get('consumer')
        consumer = by_id.get(consumer_id) if isinstance(consumer_id, str) else None
        if kind == 'CONTINUE_NEXT':
            if sp != tp or consumer is None or edge['producer'] not in consumer['depends_on']:
                raise ValueError('same-pulse continuation must follow executable DAG')
            if edge.get('consumer_repo') != consumer['repo']:
                raise ValueError('same-pulse consumer repo mismatch')
            if consumer_head is not None and consumer_head != consumer['source_sha']:
                raise ValueError('same-pulse consumer head mismatch')
        else:
            if consumer_id is not None or edge.get('target_stage_ref') not in allowed:
                raise ValueError('cross-process handoff requires declared target stage')
            target_repo = edge.get('consumer_repo')
            if not isinstance(target_repo, str) or target_repo.count('/') != 1:
                raise ValueError('invalid target process repository')
            if kind == 'SELF_REENTRY':
                if (tp <= sp or target_repo != producer['repo'] or
                        edge['target_stage_ref'] != producer['stage_ref']):
                    raise ValueError('self reentry needs same owner and later pulse')
            elif tp < sp or (target_repo == producer['repo'] and edge['target_stage_ref'] == producer['stage_ref']):
                raise ValueError('pay-it-forward must target an adjacent process without temporal reversal')
        reasons = []
        if edge['evidence_class'] != 'OBSERVED':
            reasons.append('EVIDENCE_NOT_NATIVE_OBSERVED')
        if receipt is None:
            reasons.append('PRODUCER_RECEIPT_UNPROVEN')
        if proof is None or consumer_head is None:
            reasons.append('INDEPENDENT_CONSUMER_RECEIPT_UNPROVEN')
        if edge.get('independent_consumer_proof') is not True:
            reasons.append('CONSUMER_PROOF_UNVERIFIED')
        if kind == 'PAY_IT_FORWARD' and edge.get('sanitized') is not True:
            reasons.append('PRIVACY_SANITIZATION_UNVERIFIED')
        projection.append({
            'id': ident, 'edge_type': kind, 'producer': edge['producer'],
            'consumer': consumer_id if consumer_id else edge.get('target_stage_ref'),
            'source_pulse': sp, 'target_pulse': tp,
            'advisory_status': 'ELIGIBLE_FOR_EXTERNAL_ADMISSION' if not reasons else 'DEFER',
            'reasons': reasons,
            'native_consumer_accepted': False,
            'dispatch_authorized': False, 'merge_authorized': False,
            'authority_transfer': False, 'formal_credit_delta': 0,
        })
    return projection


def plan_instances(plan, atlas):
    capacity, repo_capacity, by_id = validate(plan, atlas)
    refused = {}
    for ident, item in by_id.items():
        if item["state"] != "READY":
            refused[ident] = [item["state"], *item.get("blockers", [])]
    changed = True
    while changed:
        changed = False
        for ident, item in by_id.items():
            if ident not in refused and any(d in refused for d in item["depends_on"]):
                refused[ident] = ["UPSTREAM_NOT_READY"]
                changed = True
    pending = set(by_id) - set(refused)
    waves, scheduled = [], set()
    while pending:
        eligible = sorted((by_id[i] for i in pending if set(by_id[i]["depends_on"]) <= scheduled),
                          key=lambda v: (ROLES.index(v["sipoc_role"]), v["stage_ref"], v["id"]))
        wave, per_repo = [], Counter()
        for item in eligible:
            if len(wave) >= capacity or per_repo[item["repo"]] >= repo_capacity:
                continue
            prior_mutations = [w for w in wave if w["mode"] == "MUTATION_PROPOSAL"
                               and w["repo"] == item["repo"]]
            if item["mode"] == "MUTATION_PROPOSAL" and any(
                    (item.get("root_id") and item.get("root_id") == p.get("root_id"))
                    or any(_intersects(_canonical_path(x), _canonical_path(y))
                           for x in item["mutation_paths"] for y in p["mutation_paths"])
                    for p in prior_mutations):
                continue
            wave.append(item)
            per_repo[item["repo"]] += 1
        if not wave:
            raise ValueError("DAG scheduler deadlock")
        waves.append([{k: v[k] for k in ("id", "incarnation", "sipoc_role", "stage_ref",
                                           "repo", "source_sha", "mode", "execution")}
                      for v in wave])
        ids = {v["id"] for v in wave}
        scheduled.update(ids)
        pending -= ids
    return {
        "schema": OUTPUT_SCHEMA,
        "cohort": plan.get("cohort"),
        "authority_transfer": False, "dispatch_authorized": False,
        "merge_authorized": False, "security_waiver": False,
        "planned_not_executed": True,
        "schedule": {"waves": waves, "max_parallel": capacity,
                     "max_parallel_per_repo": repo_capacity},
        "kpi": {"instances_declared": len(by_id), "incarnations_by_role": dict(
            sorted(Counter(v["sipoc_role"] for v in by_id.values()).items())),
            "scheduled_proposals": len(scheduled), "held_or_blocked": len(refused),
            "waves_planned": len(waves), "asyncio_proposals": sum(
                v["execution"] == "ASYNCIO" for v in by_id.values() if v["id"] in scheduled),
            "actual_worker_runs": None, "queue_p95_seconds": None,
            "accepted_root_closures": 0, "native_proof_passes": None},
        "held": [{"id": i, "reasons": refused[i]} for i in sorted(refused)],
        "next_pulse_feedback": plan.get("next_pulse_feedback", []),
        **({"handoff_admission": _project_handoffs(plan, by_id, _stage_ids(atlas))}
           if "handoffs" in plan else {}),
    }


async def synthetic_asyncio_replay(receipt, inject_failure=None):
    """Simulate wave barriers; no subprocess, I/O, network or remote worker."""
    waves = receipt["schedule"]["waves"]
    known = {n["id"] for wave in waves for n in wave}
    if inject_failure is not None and inject_failure not in known:
        raise ValueError("injected ID not part of the planned DAG")
    finished, failed = [], []
    for wave in waves:
        async def simulated(node):
            await asyncio.sleep(0)
            if node["id"] == inject_failure:
                raise RuntimeError(node["id"])
            return node["id"]

        results = await asyncio.wait_for(
            asyncio.gather(*(simulated(n) for n in wave), return_exceptions=True),
            timeout=1,
        )
        for outcome in results:
            if isinstance(outcome, Exception):
                failed.append(str(outcome))
            else:
                finished.append(outcome)
        if failed:
            break
    return {"schema": "missioncontrol.sipoc-asyncio-synthetic.v1",
            "synthetic": True, "actual_worker_runs": None,
            "independent_trials": None, "completed_simulated": len(finished),
            "faults_simulated": failed, "waves_total": len(waves),
            "result": "EXPECTED_FAILURE" if failed else "SYNTHETIC_ONLY_PASS",
            "native_proof": False, "merge_authorized": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--atlas", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--synthetic-replay", action="store_true")
    opts = parser.parse_args()
    raw_input, raw_atlas = opts.input.read_bytes(), opts.atlas.read_bytes()
    receipt = plan_instances(json.loads(raw_input), json.loads(raw_atlas))
    receipt["input_sha256"] = hashlib.sha256(raw_input).hexdigest()
    receipt["canonical_atlas_sha256"] = hashlib.sha256(raw_atlas).hexdigest()
    opts.out.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(receipt, sort_keys=True, indent=2) + "\n").encode()
    (opts.out / "sipoc_instance_receipt.json").write_bytes(raw)
    (opts.out / "sipoc_instance_receipt.sha256").write_text(
        hashlib.sha256(raw).hexdigest() + "\n", encoding="ascii", newline="\n")
    if opts.synthetic_replay:
        replay = asyncio.run(synthetic_asyncio_replay(receipt))
        (opts.out / "asyncio_synthetic_only.json").write_text(
            json.dumps(replay, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(receipt["kpi"], sort_keys=True))


if __name__ == "__main__":
    main()
