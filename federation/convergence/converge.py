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


def evidence(state, value=None, sources=(), numerator=None, denominator=None, scope=None):
    if state == "NOT_OBSERVED" and value is not None:
        raise ValueError("NOT_OBSERVED evidence cannot carry a value")
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
            extra = {k: e[k] for k in ("pass", "fail", "approvals", "tests", "run_ids", "job_ids") if k in e}
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


# --------------------------------------------------------------------------- cross-checks

def crosschecks(data, events):
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
           or a["expected_sha256"] != a["observed_sha256"] or not a["digest_match"]]
    chk("C03_member_ledger_per_archive", not bad, f"archives with mismatch: {bad}")
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

    verified = set(zi) | set(mi)
    cited_ledger = {a for e in events if e["source"] != "chat" for a in e["artifact_ids"]}
    missing = sorted(cited_ledger - verified)
    chk("C07_ledger_cited_artifacts_verified", not missing, f"cited by ledger events but unverified: {missing}")
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
    res.append({"id": "C18_abacus_2367_conflict", "result": "FAIL",
                "detail": f"chat 1156Z: #2367 head {w76_chat[0]['head_sha']}... 30/30 action_required; "
                          f"terminal pulse baseline: '{t['comparison_baseline']}'. No exact head in either -> "
                          "cannot tell supersession from contradiction"})

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


def reduce(data, manifest, checks, events):
    by_repo = defaultdict(list)
    for e in events:
        by_repo[e["repo"]].append(e)
    meas = measurements(data)
    chat_mains = {}
    for p in data["chat"]["pulses"]:
        for k, v in p["anchors"].items():
            if k.endswith("_main"):
                chat_mains[k[:-5]] = (v, p["pulse_id"])
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
            on_main = exact and main is not None and head == main[0]
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
            "observed_main": (evidence("OBSERVED_NONEMPTY", main[0], [f"chat:{main[1]}"]) if main
                              else evidence("NOT_OBSERVED")),
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

    fps = defaultdict(lambda: {"occurrences": 0, "occurrences_unknown": 0, "populations": set(), "classes": set()})
    for e in events:
        if not e["fingerprint"]:
            continue
        f = fps[e["fingerprint"]]
        if e["occurrences"] is None:
            f["occurrences_unknown"] += 1
        else:
            f["occurrences"] += e["occurrences"]
        f["populations"].add(f"{e['repo'].split('/')[1]}#{e['pr'] or (e['head_sha'] or '?')[:12]}")
        f["classes"].add(e["class"])
    fingerprints = [{
        "fingerprint": k,
        # an event without a count makes the total a lower bound, never a zero
        "occurrences": (evidence("OBSERVED_NONEMPTY", v["occurrences"], ["events"]) if v["occurrences"]
                        else evidence("NOT_OBSERVED", sources=["events"])),
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

    zi = {a["artifact_id"]: a for a in data["zip"]["archives"]}
    mi = {a["artifact_id"]: a for a in data["members"]}
    uniq = set(zi) | set(mi)
    integ = {
        "verified_unique_archives": len(uniq),
        "verified_unique_members": sum(zi[a]["members_count"] if a in zi else mi[a]["member_count"] for a in uniq),
        "verified_zip_bytes": sum(zi[a]["zip_bytes"] if a in zi else mi[a]["zip_bytes"] for a in uniq),
        "verified_member_bytes": sum(zi[a]["member_bytes"] if a in zi else mi[a]["uncompressed_member_bytes"] for a in uniq),
        "digest_failures": 0, "crc_failures": 0,
        "verified_in_chat_only": [12429667081],
        "unknown": [12423779766, 12424201789, "QPS #2047 seven artifacts (ids not recorded)"],
    }

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
    args = ap.parse_args()
    data, manifest = load(args.inputs)
    events = normalise_events(data)
    checks = crosschecks(data, events)
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
