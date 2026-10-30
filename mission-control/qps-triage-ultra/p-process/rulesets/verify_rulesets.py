#!/usr/bin/env python3
"""Control-plane probe: compare each repo's EFFECTIVE default-branch rules with its expected ruleset.

Reads manifest.json + <repo>.basic.json, queries GET /repos/{r}/rules/branches/{branch} (effective
rules from every active ruleset that targets the branch) and reports, per repo, which expected rules
or required checks are missing. A ruleset that targets no branch contributes nothing and is reported.
Output: drift.json (consumed by EVERRED as CONTROL_PLANE_DRIFT probes).
"""
import json
import re
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

D = Path(__file__).parent


TRANSIENT = re.compile(r"timeout|timed out|TLS handshake|connection (reset|refused|attempt failed)|connectex|error connecting to|unexpected EOF|HTTP 5\d\d", re.I)


def gh(p):
    for attempt in range(5):  # a blip must not be recorded as ruleset drift
        r = subprocess.run(["gh", "api", p], capture_output=True, text=True, encoding="utf-8", errors="replace")
        if r.returncode == 0 or not TRANSIENT.search(r.stderr):
            break
        time.sleep(3 * (attempt + 1))
    return json.loads(r.stdout) if r.returncode == 0 and r.stdout.strip() else {"_error": r.stderr.strip()[:200]}


def gaps(effective: list, expected: dict) -> list[str]:
    have = {}
    for r in effective:
        have.setdefault(r["type"], []).append(r.get("parameters") or {})
    out = []
    for e in expected["rules"]:
        t = e["type"]
        if t not in have:
            out.append(f"{t} missing")
            continue
        if t == "required_status_checks":
            # compare (context, integration_id): a same-named check from another app must not read green
            got = {(c["context"], c.get("integration_id")) for p in have[t] for c in p.get("required_status_checks", [])}
            # HARD requires branch currency: matching names alone is not enough.
            if e["parameters"].get("strict_required_status_checks_policy") and not any(
                p.get("strict_required_status_checks_policy") for p in have[t]
            ):
                out.append("strict required-status-check policy off")
            names = {g[0] for g in got}
            for c in e["parameters"]["required_status_checks"]:
                if (c["context"], c.get("integration_id")) in got:
                    continue
                out.append(f"required check '{c['context']}' missing" if c["context"] not in names
                           else f"required check '{c['context']}' pinned to another app (expected integration {c.get('integration_id')})")
        if t == "pull_request":
            required = int(e["parameters"].get("required_approving_review_count") or 0)
            if required and not any(int(p.get("required_approving_review_count") or 0) >= required for p in have[t]):
                out.append(f"required approvals below {required}")
            if e["parameters"].get("require_last_push_approval") and not any(
                p.get("require_last_push_approval") for p in have[t]
            ):
                out.append("last-push approval off")
        if t == "pull_request" and e["parameters"].get("required_review_thread_resolution") and not any(p.get("required_review_thread_resolution") for p in have[t]):
            out.append("review-thread resolution off")
    return out


def probe_status(effective, rulesets, branch, expected, untargeted=()):
    """Classify observed missing rules separately from inaccessible GitHub data.

    Unknown API reads MUST hold the control gate, but are not evidence that a
    rule is missing. Keep a visible distinction from confirmed control drift.
    """
    unknown = []
    if not isinstance(effective, list):
        unknown.append("effective branch rules API unavailable")
    if not isinstance(rulesets, list):
        unknown.append("rulesets inventory API unavailable")
    if not isinstance(branch, dict) or type(branch.get("protected")) is not bool:
        unknown.append("default branch protection readback unavailable")
    missing = gaps(effective, expected) if isinstance(effective, list) else []
    if unknown:
        state = "UNKNOWN_API_READBACK"
    elif missing or untargeted:
        state = "CONFIRMED_DRIFT"
    else:
        state = "VERIFIED_EFFECTIVE"
    return {
        "probe_status": state, "red": state != "VERIFIED_EFFECTIVE",
        "gaps": missing, "unknown_readbacks": unknown,
        "observation_coverage": {
            "observed": 3-len(unknown), "required": 3,
            "qualification": "COMPLETE" if not unknown else "INCOMPLETE"
        }
    }


def main():
    man = json.loads((D / "manifest.json").read_text())
    res = {"generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "repos": {}}
    for repo, m in man.items():
        exp = json.loads((D / m["file"]).read_text())
        eff = gh(f"repos/{repo}/rules/branches/{m['branch']}")
        sets = gh(f"repos/{repo}/rulesets")
        untargeted = []
        if isinstance(sets, list):
            for s in sets:
                full = gh(f"repos/{repo}/rulesets/{s['id']}")
                inc = (((full.get("conditions") or {}).get("ref_name") or {}).get("include")) or []
                if full.get("enforcement") == "active" and not inc:
                    untargeted.append(f"ruleset {s['id']} '{s['name']}' is active but targets no branch")
        branch = gh(f"repos/{repo}/branches/{m['branch']}")
        measured = probe_status(eff, sets, branch, exp, untargeted)
        # Unknown is a separate evidence state, not fabricated absent rules.
        res["repos"][repo] = {"branch": m["branch"],
                              "protected": branch.get("protected") if isinstance(branch, dict) else None,
                              "effective_rules": [r["type"] for r in eff] if isinstance(eff, list) else None,
                              "untargeted_rulesets": untargeted, **measured}
        # BASIC and HARD are distinct profiles. A BASIC restoration never
        # grants HARD admission credit, and unknown reads remain blocked.
        if m.get("hard_file"):
            hard_expected = json.loads((D / m["hard_file"]).read_text())
            res["repos"][repo]["hard_gate"] = probe_status(
                eff, sets, branch, hard_expected, untargeted
            )
    (D / "drift.json").write_text(json.dumps(res, indent=2) + "\n", encoding="utf-8", newline="\n")
    for r, v in res["repos"].items():
        print(f"{v['probe_status']:21s} {r:34s} observed={v['observation_coverage']['observed']}/3  gaps={len(v['gaps'])}  unknown={len(v['unknown_readbacks'])}")


if __name__ == "__main__":
    main()
