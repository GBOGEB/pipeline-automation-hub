"""Profile and evidence overlays; no new scheduler, critical-path or metric owner."""
from datetime import datetime, timezone
import hashlib
import re
from pathlib import PurePosixPath



def timestamp(value):
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise ValueError("observation timestamp must have a timezone")
    return dt


def read_source(root, sha, path, git, source_link, repo):
    parts = PurePosixPath(path)
    if parts.is_absolute() or ".." in parts.parts or ":" in path or "\\" in path:
        raise ValueError("source path must be repository-relative")
    mode, kind, oid = git(root, "ls-tree", sha, "--", path).decode().split("\t", 1)[0].split()
    if kind != "blob" or mode == "120000":
        raise ValueError("profile source must be a regular Git blob")
    body = git(root, "cat-file", "blob", oid)
    return dict(path=path, blob_oid=oid, sha256=hashlib.sha256(body).hexdigest(),
                source_url=source_link(repo, sha, path)), body.decode("utf-8-sig")


def decision_fields(text):
    """Extract explicit source declarations, never infer acceptance."""
    title = next((x.lstrip("# ") for x in text.splitlines() if x.startswith("# ")), "UNKNOWN")
    declarations = []
    for n, line in enumerate(text.splitlines(), 1):
        plain = line.replace("**", "").strip()
        match = re.match(r"(?i)^(status|owner|authority)\s*:\s*(.+)", plain)
        if match:
            declarations.append(dict(field=match[1].lower(), value=match[2], line=n))
    for match in re.finditer(r"(?im)^##\s+(Status|Owner|Authority)\s*\n+([^\n]+)", text):
        declarations.append(dict(field=match[1].lower(), value=match[2].strip(),
                                 line=text[:match.start(2)].count("\n") + 1))
    return dict(title=title, declarations=declarations, acceptance="NOT_EVALUATED")


def observation(job, wf, snap, records, now, max_age):
    matches = [r for r in records if r.get("repository") == snap["repository"]
               and r.get("workflow") == wf["path"] and r.get("job_key") == job["id"]]
    if not matches:
        return {"state": "UNKNOWN", "reason": "NO_MATCHED_JOB_OBSERVATION"}
    # Select the newest reported observation, never an old green in preference to a newer red.
    try:
        rec = max(matches, key=lambda r: timestamp(r["observed_at"]))
        observed = timestamp(rec["observed_at"])
    except (ValueError, KeyError, TypeError):
        return {"state": "UNKNOWN", "reason": "INVALID_OBSERVATION_TIME"}
    if rec.get("source_sha") != snap["source_sha"] or rec.get("workflow_blob_oid") != wf["blob_oid"]:
        return {"state": "UNKNOWN", "reason": "SOURCE_DRIFT", "record": rec}
    try:
        completed = timestamp(rec["completed_at"])
    except (ValueError, KeyError, TypeError):
        return {"state": "UNKNOWN", "reason": "MISSING_OR_INVALID_COMPLETION_TIME", "record": rec}
    age = (now - completed).total_seconds()
    if observed > now or completed > observed or age < 0 or age > max_age:
        return {"state": "UNKNOWN", "reason": "FUTURE_OR_STALE_OBSERVATION", "record": rec}
    required = ("run_id", "job_id", "run_attempt", "run_url", "job_url")
    if any(not rec.get(k) for k in required):
        return {"state": "UNKNOWN", "reason": "INCOMPLETE_RUN_JOB_IDENTITY", "record": rec}
    if any(type(rec[k]) is not int or rec[k] < 1 for k in ("run_id", "job_id", "run_attempt")):
        return {"state": "UNKNOWN", "reason": "INVALID_RUN_JOB_IDENTITY", "record": rec}
    base = f"https://github.com/{snap['repository']}/actions/runs/{rec['run_id']}"
    if rec['run_url'] != base or rec['job_url'] != f"{base}/job/{rec['job_id']}":
        return {"state": "UNKNOWN", "reason": "INVALID_RUN_SOURCE_URL", "record": rec}
    conclusion = rec.get("conclusion") if rec.get("status") == "completed" else None
    state = "REPORTED_" + conclusion.upper() if conclusion in {"success", "failure", "cancelled", "skipped", "timed_out", "neutral"} else "UNKNOWN"
    return dict(state=state, reason="METADATA_ONLY_NOT_NATIVE_TEST_OR_ADMISSION_PROOF",
                record=rec, age_seconds=age)


def extend(snap, profile, root, git, source_link, parser, observations=(), now=None, max_age=86400):
    now = now or datetime.now(timezone.utc)
    if max_age <= 0:
        raise ValueError("freshness limit must be positive")
    sha, repo = snap["source_sha"], snap["repository"]
    bios_source, _ = read_source(root, sha, profile["purpose_source"], git, source_link, repo)
    pipelines = profile.get("pipelines", [])
    ids = [p["id"] for p in pipelines]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate pipeline profile IDs")
    decision_rows = []
    for item in profile.get("decisions", []):
        if set(item["informs"]) - set(ids) or item.get("relation") != "REVIEW_CROSSWALK":
            raise ValueError("decision crosswalk must name existing pipelines and be review-only")
        source, text = read_source(root, sha, item["path"], git, source_link, repo)
        decision_rows.append(dict(source, **decision_fields(text), informs=item["informs"],
                                  relation="REVIEW_CROSSWALK_NOT_HARD_DEPENDENCY"))
    wf_by_path = {w["path"]: w for w in snap["workflows"]}
    views = []
    for p in pipelines:
        if not p.get("entries"):
            raise ValueError("pipeline scope must name at least one entry file")
        scope, _ = read_source(root, sha, p["scope_source"], git, source_link, repo)
        entries = []
        for path in sorted(set(p["entries"])):
            src, body = read_source(root, sha, path, git, source_link, repo)
            entries.append(dict(src, physical_loc=len(body.splitlines())))
        wf = wf_by_path.get(p.get("workflow")) if p.get("workflow") else None
        if p.get("workflow") and wf is None:
            raise ValueError("pipeline names a missing/inactive workflow")
        nodes, context = [], []
        if wf:
            _, body = read_source(root, sha, wf["path"], git, source_link, repo)
            raw = parser.parse(body, path=wf["path"], blob_oid=wf["blob_oid"], repo=repo)
            rawjobs = {j["id"]: j for j in raw["jobs"]}
            for j in wf["jobs"]:
                evidence = observation(j, wf, snap, observations, now, max_age)
                nodes.append(dict(j, evidence=evidence, lane=profile["lane"],
                                  execution_readiness="NOT_EVALUATED",
                                  reported_failed_prerequisites=[], unobserved_prerequisites=[]))
                original = rawjobs[j["id"]]
                if original.get("uses"):
                    context.append(dict(from_job=j["id"], kind="REUSABLE_CALL", target=original["uses"], hard_edge=False))
                if original.get("environment"):
                    context.append(dict(from_job=j["id"], kind="ENVIRONMENT_GATE", target=original["environment"], hard_edge=False))
            states = {n["id"]: n["evidence"]["state"] for n in nodes}
            for n in nodes:
                n["reported_failed_prerequisites"] = [up for up in n["upstream"]
                    if states.get(up) in {"REPORTED_FAILURE", "REPORTED_CANCELLED", "REPORTED_TIMED_OUT"}]
                n["unobserved_prerequisites"] = [up for up in n["upstream"] if states.get(up, "UNKNOWN") == "UNKNOWN"]
        views.append(dict(id=p["id"], label=p["label"], lane=profile["lane"],
            scope_qualification="EXPLICIT_REVIEW_SCOPE_NOT_TRANSITIVE_MAIN_PIPELINE",
            scope_source=scope, entry_files=entries, entry_loc=sum(e["physical_loc"] for e in entries),
            sipoc={k: p[k] for k in ("supplier", "input", "process", "output", "customer")},
            workflow=p.get("workflow"), layers=wf.get("layers") if wf else None,
            graph_error=(wf.get("parse_error") or wf.get("graph_error")) if wf else None,
            nodes=nodes, context_relations=context, critical_path_owner="PAH PR #1276 / existing cicd_dag.py",
            adr_sources=[d for d in decision_rows if p["id"] in d["informs"]]))
    snap["development"] = dict(schema="jade.repo-bios.development.v1", purpose=profile["purpose"],
        lane=profile["lane"], visibility=profile["visibility"], purpose_source=bios_source,
        scope_state=profile.get("scope_state", "EXPLICIT_REVIEW_SCOPE"), pipelines=views,
        decision_records=decision_rows, freshness_limit_seconds=max_age,
        observed_at=now.isoformat(), authorization="NOT_EVALUATED")
    # Union avoids double-counting shared entry files across multiple pipeline cards.
    selected = {e["path"]: e for e in snap["selected_pipeline_entries"]}
    selected.update({e["path"]: e for p in views for e in p["entry_files"]})
    if selected:
        snap["selected_pipeline_entries"] = list(selected.values())
        snap["selected_pipeline_entry_loc"] = sum(e["physical_loc"] for e in selected.values())
    return snap
