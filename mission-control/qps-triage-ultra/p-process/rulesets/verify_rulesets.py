#!/usr/bin/env python3
"""Control-plane probe: compare each repo's EFFECTIVE default-branch rules with its expected ruleset.

Reads manifest.json + <repo>.basic.json, queries GET /repos/{r}/rules/branches/{branch} (effective
rules from every active ruleset that targets the branch) and reports, per repo, which expected rules
or required checks are missing. A ruleset that targets no branch contributes nothing and is reported.
Output: drift.json (consumed by EVERRED as CONTROL_PLANE_DRIFT probes).
"""
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

D = Path(__file__).parent


def gh(p):
    r = subprocess.run(["gh", "api", p], capture_output=True, text=True)
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
            names = {g[0] for g in got}
            for c in e["parameters"]["required_status_checks"]:
                if (c["context"], c.get("integration_id")) in got:
                    continue
                out.append(f"required check '{c['context']}' missing" if c["context"] not in names
                           else f"required check '{c['context']}' pinned to another app (expected integration {c.get('integration_id')})")
        if t == "pull_request" and e["parameters"].get("required_review_thread_resolution") and not any(p.get("required_review_thread_resolution") for p in have[t]):
            out.append("review-thread resolution off")
    return out


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
        prot = gh(f"repos/{repo}/branches/{m['branch']}").get("protected")
        g = gaps(eff if isinstance(eff, list) else [], exp)
        res["repos"][repo] = {"branch": m["branch"], "protected": prot, "effective_rules": [r["type"] for r in eff] if isinstance(eff, list) else eff,
                              "gaps": g, "untargeted_rulesets": untargeted, "red": bool(g)}
    (D / "drift.json").write_text(json.dumps(res, indent=2) + "\n")
    for r, v in res["repos"].items():
        print(f"{'RED ' if v['red'] else 'OK  '} {r:34s} effective={v['effective_rules']}  gaps={len(v['gaps'])}  {'; '.join(v['untargeted_rulesets'])}")


if __name__ == "__main__":
    main()
