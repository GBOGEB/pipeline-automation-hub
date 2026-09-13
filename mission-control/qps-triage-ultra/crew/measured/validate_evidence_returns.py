#!/usr/bin/env python3
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
HISTORY = ROOT / "history"
manifest = json.loads((ROOT / "MEASURED_TASK_MANIFEST_v1.json").read_text(encoding="utf-8"))
expected = {t["task_id"]: t for t in manifest["tasks"]}
sha_re = re.compile(r"^[0-9a-f]{40}$")
digest_re = re.compile(r"^sha256:[0-9a-f]{64}$")

seen_runs = set()
seen_shas = set()
returns = []
for path in sorted(HISTORY.glob("RUN_RETURN_*.json")):
    doc = json.loads(path.read_text(encoding="utf-8"))
    assert doc["schema"] == "missioncontrol.measured_task_run_return.v1", path
    assert doc["status"] == "ACCEPTED_EXACT_SHA_RUNTIME_RETURN", path
    assert doc["authority_transfer"] is False, path
    assert doc["run_conclusion"] == "success", path
    assert doc["exact_sha_asserted"] is True, path
    assert doc["rex_checklist_status"] == "PASS_REX_REUSE_CHECKLIST", path
    assert doc["competency_promotions"] == 0, path
    assert sha_re.match(doc["source_sha"]), path
    assert doc["run_id"] not in seen_runs, path
    assert doc["source_sha"] not in seen_shas, path
    seen_runs.add(doc["run_id"])
    seen_shas.add(doc["source_sha"])
    artifact = doc["artifact"]
    assert isinstance(artifact["id"], int) and artifact["id"] > 0, path
    assert artifact["size_in_bytes"] > 0, path
    assert digest_re.match(artifact["digest"]), path
    observations = doc["task_observations"]
    assert len(observations) == len(expected), path
    seen_tasks = set()
    for obs in observations:
        tid = obs["task_id"]
        assert tid in expected and tid not in seen_tasks, (path, tid)
        seen_tasks.add(tid)
        task = expected[tid]
        for key in ("assignment_id", "crew_id", "task_type", "competency_dimension", "predeclared_task_level"):
            assert obs[key] == task[key], (path, tid, key)
        assert obs["disposition"] == "ACCEPT", (path, tid)
        assert float(obs["execute_seconds"]) >= 0, (path, tid)
        assert isinstance(obs.get("rex_ids_observed", []), list), (path, tid)
    assert seen_tasks == set(expected), path
    rex = doc["rex_postflight"]
    for level in ("recurring", "persistent", "regression"):
        assert isinstance(rex[level], list), (path, level)
    returns.append(doc)

assert len(returns) >= 2, "need at least two accepted evidence returns"
print(json.dumps({
    "status": "PASS_MEASURED_EVIDENCE_RETURNS",
    "accepted_run_returns": len(returns),
    "distinct_run_ids": len(seen_runs),
    "distinct_source_shas": len(seen_shas),
    "task_observations": sum(len(x["task_observations"]) for x in returns),
    "competency_promotions": 0,
    "authority_transfer": False
}, sort_keys=True))
