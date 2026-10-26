"""CODE PURPLE scaled convergence reducer.

Folds ledger files and transcribed chat pulses into one convergence receipt.
Rules enforced here (not just documented):
  * UNKNOWN != ZERO != VERIFIED NONE  -> every measure is an Evidence dict.
  * Occurrences are never counted as roots; accepted_root_id stays None until
    an owner assigns one.
  * A population is comparable only with an exact 40-hex head SHA.
  * Plateau is derived from *fresh* comparable measurements; a replayed
    snapshot or a re-asserted historical anchor is not a fresh measurement.

Run from the repository root:
    python -m federation.convergence.converge
The receipt is written only after it validates against
contracts/convergence-receipt.schema.json; without jsonschema it refuses to write.
"""
import argparse
import hashlib
import json
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
EVIDENCE_DIR = Path(__file__).resolve().parent / "evidence" / "20261022"

LEDGER_FILES = {
    "zip": "CODE_PURPLE_VERIFIED_ZIP_LEDGER_20261022.json",
    "members": "CODE_PURPLE_TERMINAL_MEMBER_LEDGER_20261022.json",
    "terminal": "CODE_PURPLE_TERMINAL_PULSE_20261022.json",
    "new_terminals": "CODE_PURPLE_PULSE_20261022_NEW_TERMINALS.json",
}
CHAT_FILE = "pasted_pulses_20261022.json"
REPOS = {
    "ABACUS": "GBOGEB/ABACUS",
    "QPS": "GBOGEB/cryoplant-project",
    "HUB": "GBOGEB/pipeline-automation-hub",
    "CODEX": "GBOGEB/CODEX",
    "gg_MATH": "GBOGEB/gg_MATH",
}
NOVEL_CLASSES = {"NEW_TERMINAL_EVENT", "NEW_TERMINAL_RED", "NEW_FIRST_RED", "ATTRIBUTABLE_RED",
                 "MEANINGFUL_MISMATCH", "NEW_TERMINAL_MISMATCH"}
STABLE_HOLD_TRANSITIONS = 3
SHA40 = re.compile(r"^[0-9a-f]{40}$")
C18_ID = "C18_abacus_2367_conflict"
RESOLUTION_SCHEMA = "codepurple/convergence-resolution/1"
RESOLUTION_AUTHORITY = "GH_API_READONLY"


def evidence(state, value=None, sources=(), numerator=None, denominator=None, scope=None):
    if state == "NOT_OBSERVED" and value is not None:
        raise ValueError("NOT_OBSERVED evidence cannot carry a value")
    if state == "OBSERVED_NONEMPTY" and (value is None or value == 0 or value in ([], "", {})):
        raise ValueError("OBSERVED_NONEMPTY evidence needs a non-empty value")
    if numerator is not None and (denominator is None or scope is None):
        raise ValueError("a numerator needs its denominator and scope")
    ev = {"state": state, "value": value, "sources": list(sources)}
    if numerator is not None:
        ev.update(numerator=numerator, denominator=denominator, scope=scope)
    return ev


def count_evidence(raw, sources, verified=False):
    """Map a raw ledger count onto the four-state model without coercing None to 0."""
    if raw is None:
        return evidence("NOT_OBSERVED", sources=sources)
    if verified:
        return evidence("VERIFIED", raw, sources)
    return evidence("OBSERVED_EMPTY" if raw == 0 else "OBSERVED_NONEMPTY", raw, sources)


def sha256_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(inputs_dir):
    d = Path(inputs_dir)
    data = {k: json.loads((d / f).read_text(encoding="utf-8")) for k, f in LEDGER_FILES.items()}
    data["chat"] = json.loads((d / CHAT_FILE).read_text(encoding="utf-8"))
    manifest = [{"file": f, "sha256": sha256_file(d / f), "authority": "LEDGER_FILE"}
                for f in LEDGER_FILES.values()]
    manifest.append({"file": CHAT_FILE, "sha256": sha256_file(d / CHAT_FILE),
                     "authority": "CHAT_TRANSCRIPT_UNVERIFIED"})
    return data, manifest


def load_resolutions(path):
    """Optional resolution addendum: {item id: record}. No path -> no resolutions (behaviour unchanged)."""
    if path is None:
        return {}, None
    p = Path(path).resolve()
    doc = json.loads(p.read_text(encoding="utf-8"))
    if doc.get("schema") != RESOLUTION_SCHEMA or doc.get("authority") != RESOLUTION_AUTHORITY:
        raise ValueError(f"{p.name}: not a {RESOLUTION_SCHEMA} addendum with authority {RESOLUTION_AUTHORITY}")
    try:
        name = p.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        name = p.name
    return doc["resolutions"], {"file": name, "sha256": sha256_file(p), "authority": RESOLUTION_AUTHORITY}


# --------------------------------------------------------------------------- resolutions

def _sha40(v):
    return isinstance(v, str) and bool(SHA40.match(v))


def validate_supersession(rec, reported_prefix, reported_runs):
    """Return the reasons a supersession record does not prove 'old head replaced by merged head'.
    An empty list means the record is valid. A prefix is never accepted in place of an exact SHA."""
    errs = []
    if rec.get("kind") != "SUPERSESSION":
        errs.append(f"kind {rec.get('kind')!r} is not SUPERSESSION")
    old = rec.get("old_head", {}).get("sha")
    new = rec.get("new_head", {}).get("sha")
    for label, sha in (("old_head", old), ("new_head", new)):
        if not _sha40(sha):
            errs.append(f"{label} {sha!r} is not an exact 40-hex SHA")
    if errs:
        return errs
    if not reported_prefix or not old.startswith(reported_prefix):
        errs.append(f"old_head {old} does not extend the reported prefix {reported_prefix!r}")
    if rec["old_head"].get("reported_prefix") != reported_prefix:
        errs.append(f"record prefix {rec['old_head'].get('reported_prefix')!r} != reported {reported_prefix!r}")
    if old == new:
        errs.append("old_head equals new_head: nothing was superseded")
    run = rec.get("run", {})
    if run.get("head_sha") != old:
        errs.append(f"run {run.get('id')} headSha {run.get('head_sha')!r} != old_head {old}")
    if run.get("id") not in reported_runs:
        errs.append(f"run {run.get('id')} is not among the reported runs {reported_runs}")
    anc = rec.get("ancestry", {})
    if (anc.get("base"), anc.get("head"), anc.get("merge_base")) != (old, new, old) \
            or anc.get("behind_by") != 0 or not isinstance(anc.get("ahead_by"), int) or anc["ahead_by"] < 1:
        errs.append(f"ancestry does not show {old} as a strict ancestor of {new}: {anc}")
    if rec.get("pr_state") != "MERGED":
        errs.append(f"PR state {rec.get('pr_state')!r} is not MERGED")
    merge = rec.get("merge_commit", {})
    if not _sha40(merge.get("sha")) or new not in merge.get("parents", []):
        errs.append(f"merge commit {merge.get('sha')!r} does not have new_head {new} as a parent")
    checks = rec.get("checks_at_new_head", {})
    for label, part, want in (("old_head", rec["old_head"], old), ("new_head", rec["new_head"], new),
                              ("run", run, old), ("merge_commit", merge, merge.get("sha")),
                              ("checks_at_new_head", checks, new)):
        if part.get("read_at_sha") != want or not _sha40(want):
            errs.append(f"{label} read_at_sha {part.get('read_at_sha')!r} is not the exact SHA {want!r}")
    total, failed, names = checks.get("total"), checks.get("failed"), checks.get("failed_names")
    if not (isinstance(total, int) and isinstance(failed, int) and isinstance(names, list)
            and 0 <= failed <= total and failed == len(names)):
        errs.append(f"check counts inconsistent: total={total} failed={failed} names={names}")
    return errs


def grade_supersession(rec):
    """PASS only when no check failed, or every failure is shown non-required AND pre-existing on the base.
    A missing required-check reading is NOT_OBSERVED (unknown), never 'no required checks'."""
    checks = rec["checks_at_new_head"]
    if checks["failed"] == 0:
        return "PASS", "0 failed checks at the merged head"
    req = checks.get("required_checks") or evidence("NOT_OBSERVED")
    req_names = set(req.get("value") or [])
    failed_jobs = set(checks.get("failed_preexisting_on_base_parent") or []) | \
        set(checks.get("failed_not_shown_unrelated") or [])
    non_required = req.get("state") in ("OBSERVED_EMPTY", "VERIFIED") and not (req_names & failed_jobs)
    unexplained = checks.get("failed_not_shown_unrelated")
    unrelated = unexplained == []
    if non_required and unrelated:
        return "PASS", f"{checks['failed']} failed checks, all non-required and pre-existing on the base parent"
    why = [f"{checks['failed']}/{checks['total']} checks FAILED at merged head {rec['new_head']['sha']}"]
    why.append("non-required by ruleset (required set " + req["state"] + ")" if non_required
               else "required-check set " + req.get("state", "NOT_OBSERVED") + ": non-required not shown")
    why.append("not shown unrelated: " + (", ".join(unexplained) if unexplained else "UNKNOWN"))
    return "WARN", "; ".join(why)


def resolve_c18(check, rec, chat_event):
    """Apply an optional supersession record to the C18 result; invalid records leave it FAIL."""
    if rec is None:
        return check
    errs = validate_supersession(rec, chat_event["head_sha"], chat_event.get("run_ids", []))
    if errs:
        return {**check, "detail": check["detail"] + "; supersession record REJECTED", "resolution_rejected": errs}
    result, why = grade_supersession(rec)
    run, checks = rec["run"], rec["checks_at_new_head"]
    detail = (f"SUPERSEDED: #{rec['pr']} head {rec['old_head']['sha']} (chat prefix {rec['old_head']['reported_prefix']}) "
              f"run {run['id']} conclusion {run['conclusion']} was superseded by {rec['new_head']['sha']}, merged as "
              f"{rec['merge_commit']['sha']}; the two reports describe different heads/attempts, not a contradiction. "
              + why)
    return {**check, "result": result, "detail": detail, "resolution": "SUPERSEDED",
            "resolution_evidence": {
                "pr": rec["pr"], "old_head_sha": rec["old_head"]["sha"], "new_head_sha": rec["new_head"]["sha"],
                "merge_commit_sha": rec["merge_commit"]["sha"], "run_id": run["id"],
                "run_head_sha": run["head_sha"], "run_conclusion": run["conclusion"],
                "checks_total": checks["total"], "checks_failed": checks["failed"],
                "failed_names": checks["failed_names"]}}


# --------------------------------------------------------------------------- events

def normalise_events(data):
    """Return one flat list of events with a common shape and their origin."""
    out = []

    def add(src, pulse, repo, pr, head, fp, cls, occ=None, artifacts=(), extra=None):
        out.append({
            "source": src, "pulse": pulse, "repo": repo, "pr": pr,
            "head_sha": head, "head_sha_exact": bool(head and SHA40.match(head)),
            "fingerprint": fp, "class": cls, "occurrences": occ,
            "artifact_ids": [a for a in artifacts if a is not None], **(extra or {}),
        })

    for p in data["chat"]["pulses"]:
        for e in p["events"]:
            arts = [a["artifact_id"] for a in e.get("artifacts", [])]
            extra = {k: e[k] for k in ("pass", "fail", "approvals", "tests", "run_ids", "job_ids",
                                       "artifact_integrity", "merged_utc") if k in e}
            extra["artifact_claims"] = [{"artifact_id": a["artifact_id"], "integrity": a["integrity"]}
                                        for a in e.get("artifacts", [])]
            add("chat", p["pulse_id"], e["repo"], e["pr"], e["head_sha"], e["fingerprint"],
                e["class"], e.get("occurrences"), arts, extra)

    t = data["terminal"]
    for e in t["new_meaningful_events"]:
        if e["class"] == "ATTRIBUTABLE_RED":
            add("terminal", "TERMINAL", e["repo"], e["pr"], e["head_sha"], "QPS_ICD_PDF_OVERFLOW",
                e["class"], e["occurrences"]["ICD_pack_failures"], [r["artifact_id"] for r in e["runs"]],
                {"run_ids": [r["id"] for r in e["runs"]], "job_ids": [r["job"] for r in e["runs"]]})
        elif e["class"] == "SOURCE_BOUND_CANDIDATE_PASS":
            add("terminal", "TERMINAL", e["repo"], e["pr"], e["head_sha"], None, e["class"], None,
                [e["artifact_id"]], {"tests": e["tests"], "run_ids": [e["run_id"]], "job_ids": [e["job"]]})
        elif e["class"] == "MEANINGFUL_MISMATCH":
            add("terminal", "TERMINAL", e["repo"], e["pr"], e["head_sha"], e["finding"]["id"],
                e["class"], 1, [], {"run_ids": [e["run_id"]], "job_ids": [e["job"]]})

    for e in data["new_terminals"]["events"]:
        fp = e.get("fingerprint") or (e.get("advisory") if "advisory" in e else None)
        tests = None
        if e.get("tests_executed") is not None:
            tests = {"executed": e["tests_executed"], "passed": e["tests_pass"],
                     "failed": e["tests_fail"], "skipped": e["tests_skip"]}
        add("new_terminals", "NEW_TERMINALS", e["repository"], None, e["exact_sha"], fp,
            e["classification"], 1 if fp else None, e.get("artifact_ids", []),
            {"run_ids": [e["run_id"]], "tests": tests})
    return out


# --------------------------------------------------------------------------- integrity

def archive_status(data):
    """Per-archive integrity from both ledgers. An archive counts as verified only when its digest,
    CRC and member accounting all hold in every ledger that lists it, and the ledgers agree on its digest."""
    status = {}
    for a in data["zip"]["archives"]:
        status[a["artifact_id"]] = {
            "run": a["run_id"], "zip_bytes": a["zip_bytes"], "members": a["members_count"],
            "member_bytes": a["member_bytes"], "sha256": a["archive_sha256"],
            "digest_ok": bool(a["checksum_verified"]), "crc_ok": bool(a["crc_verified"]),
            "consistent": a["members_count"] == len(a["members"])
            and a["member_bytes"] == sum(x["uncompressed_bytes"] for x in a["members"]),
        }
    for a in data["members"]:
        rec = {
            "run": a["run"], "zip_bytes": a["zip_bytes"], "members": a["member_count"],
            "member_bytes": a["uncompressed_member_bytes"], "sha256": a["observed_sha256"],
            "digest_ok": bool(a["digest_match"]) and a["expected_sha256"] == a["observed_sha256"],
            "crc_ok": bool(a["crc_all_members_pass"]),
            "consistent": a["member_count"] == len(a["members"])
            and a["uncompressed_member_bytes"] == sum(x["bytes"] for x in a["members"]),
        }
        prev = status.get(a["artifact_id"])
        if prev:
            # two self-consistent records can still disagree with each other: require the same run and totals
            same_meta = all(prev[k] == rec[k] for k in ("run", "zip_bytes", "members", "member_bytes"))
            rec = {**prev,
                   "digest_ok": prev["digest_ok"] and rec["digest_ok"] and prev["sha256"] == rec["sha256"],
                   "crc_ok": prev["crc_ok"] and rec["crc_ok"],
                   "consistent": prev["consistent"] and rec["consistent"] and same_meta}
        status[a["artifact_id"]] = rec
    for rec in status.values():
        rec["verified"] = rec["digest_ok"] and rec["crc_ok"] and rec["consistent"]
    return status


# --------------------------------------------------------------------------- cross-checks

def crosschecks(data, events, resolutions=None):
    z, m, t, n = data["zip"], data["members"], data["terminal"], data["new_terminals"]
    zi = {a["artifact_id"]: a for a in z["archives"]}
    mi = {a["artifact_id"]: a for a in m}
    res = []

    def chk(cid, ok, detail, fail="FAIL"):
        res.append({"id": cid, "result": "PASS" if ok else fail, "detail": detail})

    totals = (len(z["archives"]), sum(a["members_count"] for a in z["archives"]),
              sum(a["zip_bytes"] for a in z["archives"]), sum(a["member_bytes"] for a in z["archives"]))
    s = z["summary"]
    chk("C01_zip_summary_totals", totals == (s["validated_archive_count"], s["validated_members"],
                                             s["zip_bytes_total"], s["member_bytes_total"]),
        f"recomputed archives/members/zip/member bytes = {totals}")
    bad = [a["artifact_id"] for a in z["archives"]
           if a["members_count"] != len(a["members"])
           or a["member_bytes"] != sum(x["uncompressed_bytes"] for x in a["members"])
           or not (a["checksum_verified"] and a["crc_verified"])]
    chk("C02_zip_per_archive", not bad, f"archives with count/byte/flag mismatch: {bad}")
    bad = [a["artifact_id"] for a in m
           if a["member_count"] != len(a["members"])
           or a["uncompressed_member_bytes"] != sum(x["bytes"] for x in a["members"])
           or a["expected_sha256"] != a["observed_sha256"] or not a["digest_match"]
           or not a["crc_all_members_pass"]]
    chk("C03_member_ledger_per_archive", not bad, f"archives with count/byte/digest/CRC mismatch: {bad}")
    mt = (len(m), sum(a["member_count"] for a in m), sum(a["zip_bytes"] for a in m),
          sum(a["uncompressed_member_bytes"] for a in m))
    ts = t["zip_verification_summary"]
    chk("C04_terminal_summary_vs_member_ledger",
        mt == (ts["verified_archives"], ts["verified_members"], ts["archive_bytes"], ts["uncompressed_member_bytes"]),
        f"member ledger totals {mt}")
    chk("C05_new_terminals_summary_vs_zip_ledger", n["artifact_verification"] == z["summary"],
        "NEW_TERMINALS.artifact_verification equals ZIP ledger summary")
    overlap = sorted(set(zi) & set(mi))
    agree = all(zi[a]["archive_sha256"] == mi[a]["observed_sha256"] for a in overlap)
    chk("C06_cross_ledger_digest_agreement", agree, f"overlapping artifacts {overlap} digests agree={agree}")

    # every cited artifact, from any source: a ledger citation must resolve to a verified archive, and a
    # resolved archive must come from one of the runs the event cites; chat-only citations stay unverified
    st = archive_status(data)
    problems, chat_unverified = [], set()
    for e in events:
        for a in e["artifact_ids"]:
            rec = st.get(a)
            if rec is None:
                if e["source"] == "chat":
                    chat_unverified.add(a)
                else:
                    problems.append(f"{a}: cited by {e['pulse']} but in no ledger")
                continue
            if not rec["verified"]:
                problems.append(f"{a}: cited by {e['pulse']} but failed integrity")
            if e.get("run_ids") and rec["run"] not in e["run_ids"]:
                problems.append(f"{a}: ledger run {rec['run']} not among {e['pulse']} cited runs {e['run_ids']}")
    res.append({"id": "C07_event_artifact_citations",
                "result": "FAIL" if problems else "WARN" if chat_unverified else "PASS",
                "detail": f"citation problems: {problems}; chat-only citations with no ledger record: "
                          f"{sorted(chat_unverified)}"})
    cited_ledger = {a for e in events if e["source"] != "chat" for a in e["artifact_ids"]}
    atlas = n["method_atlas"]
    run_cited = {r for e in events for r in e.get("run_ids", [])} | {atlas["original_run"], atlas["qualified_run"]}
    orphans = sorted(a for a, rec in zi.items() if rec["run_id"] not in run_cited and a not in cited_ledger)
    orphans += sorted(a for a, rec in mi.items() if rec["run"] not in run_cited and a not in cited_ledger)
    chk("C08_verified_artifacts_bound_to_event", not orphans,
        f"verified archives whose run is cited by no event (integrity proven, provenance unbound): {orphans}", "WARN")

    pc3 = [a for a in z["archives"] if a["run_id"] == 39787756949 and a["members_count"] == 13]
    pc3_ev = next(e for e in n["events"] if e.get("fingerprint") == "PC3_COLLECTOR_CONCLUSION_CONFLICT")
    receipts = sum(sum(1 for x in a["members"] if "RUN_SUMMARY" not in x["name"]) for a in pc3)
    chk("C09_pc3_task_receipts", len(pc3) == pc3_ev["successful_platform_jobs"] and receipts == pc3_ev["accepted_task_receipts"],
        f"{len(pc3)} platform archives x task receipts = {receipts}; event claims "
        f"{pc3_ev['successful_platform_jobs']} jobs / {pc3_ev['accepted_task_receipts']} receipts")

    osv = [a for a in list(zi.values()) if a["repository"] == "GBOGEB/CODEX" and a["members_count"] == 1]
    osv_sha = {x["sha256"] for a in osv for x in a["members"]} | \
              {x["sha256"] for a in m if a["repo"] == "GBOGEB/CODEX" for x in a["members"]}
    res.append({"id": "C10_codex_osv_old_equals_new", "result": "WARN" if len(osv_sha) == 1 else "PASS",
                "detail": f"{len(osv_sha)} distinct OSV result digest(s) across both CODEX heads: old==new, so a "
                          "diff-only gate reports no new finding while PYSEC-2026-4320 persists (job GREEN != risk closed)"})

    orig = {x["name"]: x["sha256"] for x in zi[11961956624]["members"]}
    qual = {x["name"]: x["sha256"] for x in zi[11964700323]["members"]}
    lane = [k for k in qual if k.startswith("lane-process")]
    same = all(orig.get(k) == qual[k] for k in lane)
    res.append({"id": "C11_method_atlas_lane_members", "result": "PASS" if same else "FAIL",
                "detail": f"lane-process members identical by SHA256 across original/qualified artifacts: {same} "
                          f"(byte-only claim generated_members_match_original upgraded to digest match)"})

    icd = mi[12428658601]["members"]
    pdf_qa = {x["name"].split("/")[1]: x["bytes"] for x in icd if x["name"].endswith("QA_REPORT_pdf.json")}
    big = sorted(k for k, b in pdf_qa.items() if b > 300)
    res.append({"id": "C12_icd_pdf_qa_signature", "result": "PASS" if len(big) == 5 else "UNKNOWN",
                "detail": f"QA_REPORT_pdf.json size splits {len(big)}/{len(pdf_qa)} packs into the larger class {big}; "
                          "consistent with '5 of 8 overflow' but content not read -> corroboration only"})
    pptx = {x["sha256"] for x in icd if x["name"].endswith("QA_REPORT_pptx.md")}
    res.append({"id": "C13_icd_pptx_qa_identical", "result": "WARN" if len(pptx) == 1 else "PASS",
                "detail": f"QA_REPORT_pptx.md has {len(pptx)} distinct digest across 8 packs (89 B each): "
                          "likely a stub, pptx QA should not be credited as executed"})

    hub531 = zi[12433936196]["members"]
    empty = [x["name"] for x in hub531 if x["uncompressed_bytes"] == 0]
    res.append({"id": "C14_hub531_event_stream", "result": "WARN" if empty else "PASS",
                "detail": f"zero-byte members in HUB #531 artifact: {empty} -> OBSERVED_EMPTY (verified none), "
                          "and snapshot dated 2026-10-16 with 0 authenticated requests -> replay, not fresh"})

    res.append({"id": "C15_zip_ledger_head_binding", "result": "WARN",
                "detail": "ZIP ledger archives carry no head_sha and no separate expected digest; "
                          "checksum_verified is an assertion, binding to a head only via run_id join"})

    chat_unknown = {a for p in data["chat"]["pulses"] for e in p["events"]
                    for a in e.get("run_ids", []) if e.get("artifact_integrity") == "UNKNOWN"}
    upgraded = sorted(a["artifact_id"] for a in m if a["run"] in chat_unknown)
    res.append({"id": "C16_chat_unknown_superseded", "result": "PASS" if upgraded else "UNKNOWN",
                "detail": f"artifacts reported UNKNOWN in chat 1426Z later verified by ledger: {upgraded}"})

    mains = [(p["pulse_id"], p["anchors"].get("QPS_main")) for p in data["chat"]["pulses"] if p["anchors"].get("QPS_main")]
    res.append({"id": "C17_qps_main_drift", "result": "WARN" if len({s for _, s in mains}) > 1 else "PASS",
                "detail": f"QPS main observed {mains}; then #2047/#2048 merged at 14:24-14:26Z -> current main SHA "
                          "NOT_OBSERVED; anchor 763/852 is a PR-head (#2017) cohort, not main"})

    w76_chat = [e for e in events if e["pr"] == 2367]
    c18 = {"id": C18_ID, "result": "FAIL",
           "detail": f"chat 1156Z: #2367 head {w76_chat[0]['head_sha']}... 30/30 action_required; "
                     f"terminal pulse baseline: '{t['comparison_baseline']}'. No exact head in either -> "
                     "cannot tell supersession from contradiction"}
    res.append(resolve_c18(c18, (resolutions or {}).get(C18_ID), w76_chat[0]))

    trunc = sorted({f"{e['repo'].split('/')[1]}#{e['pr']}" for e in events if e["head_sha"] and not e["head_sha_exact"]})
    res.append({"id": "C19_truncated_heads", "result": "WARN" if trunc else "PASS",
                "detail": f"populations identified only by SHA prefix (ineligible for comparison): {trunc}"})
    return res


# --------------------------------------------------------------------------- reduction

def measurements(data):
    """Coverage / breadth measurements with freshness. fresh=False marks re-asserted anchors or replays."""
    n = {e["run_id"]: e for e in data["new_terminals"]["events"]}
    q = n[39795640940]
    a = n[39799140766]
    return [
        {"repo": "QPS", "cohort": "ten-module PR-head #2017 statements", "pulse": p, "num": 763, "den": 852, "fresh": False}
        for p in ("1156Z", "1426Z")
    ] + [
        {"repo": "QPS", "cohort": q["statement_coverage"]["scope"] + " statements", "pulse": "NEW_TERMINALS",
         "num": q["statement_coverage"]["covered"], "den": q["statement_coverage"]["eligible"], "fresh": True},
        {"repo": "ABACUS", "cohort": f"W70 focused statements @cohort {a['embedded_cohort_source_sha'][:12]}",
         "pulse": "NEW_TERMINALS", "num": 133, "den": 133, "fresh": a["embedded_cohort_source_sha"] == a["exact_sha"]},
        {"repo": "HUB", "cohort": "#531 authenticated six-repo breadth", "pulse": "TERMINAL",
         "num": data["terminal"]["census"]["historical_observed"],
         "den": data["terminal"]["census"]["historical_eligible"], "fresh": False},
        {"repo": "HUB", "cohort": "#531 authenticated six-repo breadth", "pulse": "NEW_TERMINALS",
         "num": 6, "den": 42, "fresh": n[39796486153]["authenticated_requests"] > 0},
    ]


def plateau(series, asserted):
    """Count trailing equal transitions between consecutive fresh, same-cohort measurements."""
    fresh = [s for s in series if s["fresh"]]
    by_cohort = defaultdict(list)
    for s in fresh:
        by_cohort[s["cohort"]].append((s["num"], s["den"]))
    best = 0
    for vals in by_cohort.values():
        run = 0
        for prev, cur in zip(vals, vals[1:]):
            run = run + 1 if prev == cur else 0
        best = max(best, run)
    if not any(len(v) > 1 for v in by_cohort.values()):
        state, why = "STARVED", "no cohort has two fresh comparable measurements"
    elif best >= STABLE_HOLD_TRANSITIONS:
        state, why = "STABLE_HOLD", f"{best} equal fresh transitions"
    else:
        state, why = "ACTIVE", f"{best} equal fresh transitions (< {STABLE_HOLD_TRANSITIONS})"
    if asserted == "STABLE_HOLD" and state != "STABLE_HOLD":
        why += "; asserted STABLE_HOLD is not derivable from fresh evidence"
    return {"comparable_equal_transitions": best, "fresh_measurements": len(fresh),
            "state": state, "asserted_state": asserted, "derivation": why}


def main_anchors(pulses):
    """Latest observed main SHA per repo. A later pulse that records a merge into a repo without
    re-observing its main invalidates the anchor: the old SHA is no longer main, the new one is unknown."""
    short_of = {full: short for short, full in REPOS.items()}
    mains = {}
    for p in pulses:
        for k, v in p["anchors"].items():
            if k.endswith("_main"):
                mains[k[:-5]] = {"sha": v, "pulse": p["pulse_id"], "invalidated_by": None}
        for e in p["events"]:
            short = short_of.get(e["repo"])
            if e.get("merged_utc") and short in mains and f"{short}_main" not in p["anchors"]:
                note = f"chat:{p['pulse_id']} merge of #{e['pr']} at {e['merged_utc']}"
                prior = mains[short]["invalidated_by"]
                mains[short] = {**mains[short], "invalidated_by": f"{prior}; {note}" if prior else note}
    return mains


def observed_main(main):
    if main is None:
        return evidence("NOT_OBSERVED")
    if main["invalidated_by"]:
        return evidence("NOT_OBSERVED", sources=[f"last seen {main['sha']} @chat:{main['pulse']}",
                                                 main["invalidated_by"]])
    return evidence("OBSERVED_NONEMPTY", main["sha"], [f"chat:{main['pulse']}"])


def integrity_summary(data, events):
    """Totals over archives that pass every integrity check; failures are counted, not assumed away."""
    st = archive_status(data)
    ok = {a: s for a, s in st.items() if s["verified"]}
    claims = [c for e in events for c in e.get("artifact_claims", [])]
    unknown = sorted({c["artifact_id"] for c in claims
                      if c["integrity"] != "VERIFIED_IN_CHAT" and c["artifact_id"] not in ok})
    verified_runs = {s["run"] for s in ok.values()}
    for e in events:
        if e.get("artifact_integrity") == "UNKNOWN" and not e["artifact_ids"]:
            unknown += [f"{e['repo'].split('/')[1]}#{e['pr']} run {r} (artifact ids not recorded)"
                        for r in e.get("run_ids", []) if r not in verified_runs]
    return {
        "verified_unique_archives": len(ok),
        "verified_unique_members": sum(s["members"] for s in ok.values()),
        "verified_zip_bytes": sum(s["zip_bytes"] for s in ok.values()),
        "verified_member_bytes": sum(s["member_bytes"] for s in ok.values()),
        "digest_failures": sum(1 for s in st.values() if not s["digest_ok"]),
        "crc_failures": sum(1 for s in st.values() if not s["crc_ok"]),
        "inconsistent_archives": sorted(a for a, s in st.items() if not s["consistent"]),
        "failed_archives": sorted(set(st) - set(ok)),
        "verified_in_chat_only": sorted({c["artifact_id"] for c in claims
                                         if c["integrity"] == "VERIFIED_IN_CHAT" and c["artifact_id"] not in ok}),
        "unknown": unknown,
    }


def reduce(data, manifest, checks, events):
    by_repo = defaultdict(list)
    for e in events:
        by_repo[e["repo"]].append(e)
    meas = measurements(data)
    chat_mains = main_anchors(data["chat"]["pulses"])
    finding_ids = {c["id"] for c in checks if c["result"] in ("FAIL", "WARN")}
    repo_findings = {"ABACUS": {"C18_abacus_2367_conflict", "C19_truncated_heads"},
                     "QPS": {"C08_verified_artifacts_bound_to_event", "C13_icd_pptx_qa_identical", "C17_qps_main_drift"},
                     "HUB": {"C14_hub531_event_stream", "C15_zip_ledger_head_binding"},
                     "CODEX": {"C08_verified_artifacts_bound_to_event", "C10_codex_osv_old_equals_new"}}

    repos = {}
    for short, full in REPOS.items():
        evs = by_repo.get(full, [])
        pops = defaultdict(list)
        for e in evs:
            pops[(e["pr"], e["head_sha"])].append(e)
        populations = []
        main = chat_mains.get(short)
        for (pr, head), pe in sorted(pops.items(), key=lambda kv: (kv[0][0] or 0, kv[0][1] or "")):
            exact = bool(head and SHA40.match(head))
            # an unrecorded PR number is UNKNOWN, not "this is main": eligibility needs a positive SHA match
            on_main = exact and main is not None and main["invalidated_by"] is None and head == main["sha"]
            reasons = []
            if not exact:
                reasons.append("head SHA not exact")
            elif not on_main:
                reasons.append("head is not the observed main SHA: not comparable with main cohort")
            populations.append({"pr": pr, "head_sha": head, "head_sha_exact": exact,
                                "eligible_for_comparison": on_main,
                                "ineligible_reasons": reasons, "events": pe})
        novel = sorted({e["fingerprint"] for e in evs if e["fingerprint"] and e["class"] in NOVEL_CLASSES})
        terminal = sum(1 for e in evs if e["class"] not in ("RECURRENCE",))
        approvals = [e.get("approvals") for e in evs if "approvals" in e]
        review = (evidence("OBSERVED_EMPTY", 0, ["chat:1426Z"]) if approvals and all(a == 0 for a in approvals)
                  else evidence("NOT_OBSERVED", sources=[]))
        asserted = "STABLE_HOLD" if short == "HUB" else "NONE"
        reasons = sorted(repo_findings.get(short, set()) & finding_ids)
        repos[short] = {
            "last_qualified_head": None,
            "observed_main": observed_main(main),
            "populations": populations,
            "progress": {
                "new_terminal_events": terminal,
                "new_fingerprints": novel,
                "qualified_root_closures": 0,
                "coverage_delta": evidence("NOT_OBSERVED", sources=["no fresh same-cohort pair"]),
                "worker_hours": evidence("NOT_OBSERVED"),
            },
            "governance": {"independent_review": review, "admission": "HOLD"},
            "plateau": plateau([x for x in meas if x["repo"] == short], asserted),
            "notify": bool(reasons),
            "notify_reasons": reasons,
        }

    fps = defaultdict(lambda: {"occurrences": 0, "counted": 0, "occurrences_unknown": 0,
                               "populations": set(), "classes": set()})
    for e in events:
        if not e["fingerprint"]:
            continue
        f = fps[e["fingerprint"]]
        if e["occurrences"] is None:
            f["occurrences_unknown"] += 1
        else:
            f["occurrences"] += e["occurrences"]
            f["counted"] += 1
        f["populations"].add(f"{e['repo'].split('/')[1]}#{e['pr'] or (e['head_sha'] or '?')[:12]}")
        f["classes"].add(e["class"])
    fingerprints = [{
        "fingerprint": k,
        # an event without a count makes the total a lower bound, never a zero;
        # a counted zero stays OBSERVED_EMPTY
        "occurrences": count_evidence(v["occurrences"] if v["counted"] else None, ["events"]),
        "occurrences_lower_bound": bool(v["occurrences_unknown"]),
        "populations": sorted(v["populations"]),
        "classes": sorted(v["classes"]),
        "accepted_root_id": None,
        "closed": False,
    } for k, v in sorted(fps.items())]
    for d in data["chat"]["method_defects"]:
        fingerprints.append({"fingerprint": d["fingerprint"], "occurrences": evidence("OBSERVED_NONEMPTY", 1, ["chat"]),
                             "occurrences_lower_bound": True, "populations": [d["path"]],
                             "classes": ["METHOD_DEFECT"], "accepted_root_id": None, "closed": False})

    integ = integrity_summary(data, events)

    novel_total = sum(len(r["progress"]["new_fingerprints"]) for r in repos.values())
    return {
        "schema_version": "1.1",
        "programme": "CODE_PURPLE",
        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "inputs": manifest,
        "repos": repos,
        "fingerprints": fingerprints,
        "artifact_integrity": integ,
        "crosschecks": checks,
        "federation": {
            "admission": "HOLD",
            "formal_credit_delta": 0,
            "security_waiver": False,
            "qualified_root_closures": 0,
            "accepted_root_ids": None,
            "fingerprint_families": len(fingerprints),
            "novel_fingerprints_today": novel_total,
            "last_qualified_heads_populated": sum(1 for r in repos.values() if r["last_qualified_head"]),
            "notify": any(r["notify"] for r in repos.values()),
        },
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--inputs", default=str(EVIDENCE_DIR))
    ap.add_argument("--schema", default=str(REPO_ROOT / "contracts" / "convergence-receipt.schema.json"))
    ap.add_argument("--out", default=str(EVIDENCE_DIR / "CODE_PURPLE_SCALED_CONVERGENCE_20261022.json"))
    ap.add_argument("--resolutions", default=None,
                    help="optional resolution addendum (codepurple/convergence-resolution/1) keyed by item id")
    args = ap.parse_args()
    data, manifest = load(args.inputs)
    resolutions, res_entry = load_resolutions(args.resolutions)
    if res_entry:
        manifest.append(res_entry)
    events = normalise_events(data)
    checks = crosschecks(data, events, resolutions)
    receipt = reduce(data, manifest, checks, events)

    try:
        import jsonschema
    except ImportError as exc:  # fail closed: an unvalidated receipt is never written
        raise SystemExit("jsonschema is required to validate the receipt; nothing written") from exc
    jsonschema.validate(receipt, json.loads(Path(args.schema).read_text(encoding="utf-8")))

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    body = json.dumps(receipt, indent=2, sort_keys=False) + "\n"
    out.write_text(body, encoding="utf-8", newline="\n")
    digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
    out.with_name(out.name + ".sha256").write_text(f"{digest}  {out.name}\n", encoding="utf-8", newline="\n")
    for c in checks:
        print(f"{c['result']:7} {c['id']}")
    print(f"receipt {out} sha256 {digest}")


if __name__ == "__main__":
    main()
