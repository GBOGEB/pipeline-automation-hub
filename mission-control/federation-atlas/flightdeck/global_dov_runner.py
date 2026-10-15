#!/usr/bin/env python3
"""Read-only global DoV projection from the governed MissionControl contract."""
from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
from pathlib import Path

SCHEMA = "missioncontrol.global_dov.owner_control.v1"
VALID = {
    "READY_OWNER", "READY_READONLY", "BLOCKED_EXTERNAL",
    "BLOCKED_DEPENDENCY", "HELD_GOVERNANCE",
}


def validate(data: dict) -> None:
    if data.get("schema") != SCHEMA:
        raise ValueError("unsupported DoV source")
    hard = data.get("hard_gates", {})
    if hard != {
        "qps_engineering_acceptance": "DEFER",
        "native_cross_repo_federation": "UNKNOWN",
        "merge_admission": "HOLD",
        "authority_transfer": False,
        "formal_credit_delta": 0,
    }:
        raise ValueError("owner/engineering authority would be promoted")
    expected = {
        "PRODUCT": (70, 90),
        "BREADTH": (36, 45),
        "DEPTH": (34, 45),
        "OBSERVABILITY": (6, 42),
        "FEDERATION": (None, 4),
        "PUBLICATION": (None, 1),
    }
    outcomes = data.get("global_outcomes", [])
    if len(outcomes) != 6:
        raise ValueError("missing or additional global outcome family")
    actual = {x["id"]: (x["numerator"], x["denominator"]) for x in outcomes}
    if actual != expected:
        raise ValueError("scope or denominator mismatch")
    sources = data.get("source_conflicts", [])
    if len(sources) != 2 or any(x.get("disposition") != "HOLD" for x in sources):
        raise ValueError("source conflict concealed")
    actions = data.get("decisions", [])
    if len(actions) != 8 or len({x["id"] for x in actions}) != 8:
        raise ValueError("uncontrolled decision count or duplicate IDs")
    for action in actions:
        if action["state"] not in VALID or not action["source"].startswith(
            "https://github.com/GBOGEB/"
        ):
            raise ValueError("invalid work state or source provenance")
        for field in ("owner", "outcome", "action", "proof"):
            if not action.get(field):
                raise ValueError("action lacking ownership or DoV verification")


def produce(source: Path, output: Path) -> dict:
    raw = source.read_bytes()
    data = json.loads(raw)
    validate(data)
    source_hash = hashlib.sha256(raw).hexdigest()
    actions = sorted(data["decisions"], key=lambda x: (x["priority"], x["id"]))
    output.mkdir(parents=True, exist_ok=True)
    summary = {
        "schema": "missioncontrol.global_dov.projection.v1",
        "source_sha256": source_hash,
        "as_of": data["snapshot_date"],
        "metrics": data["global_outcomes"],
        "actions": actions,
        "source_conflicts": data["source_conflicts"],
        "hard_gates": data["hard_gates"],
        "evidence_class": "SOURCE_CONTROLLED_HISTORICAL_AND_READONLY",
        "engineering_credit_delta": 0,
        "owner_acceptance": "DEFER",
    }
    (output / "scorecard.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    columns = ["priority", "id", "state", "owner", "outcome", "action", "proof", "source"]
    with (output / "owner_actions.csv").open("w", newline="", encoding="utf-8") as fp:
        writer = csv.DictWriter(fp, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(actions)
    e = html.escape
    tiles = "".join(
        f'<article><small>{e(m["description"])}</small><b>'
        f'{m["numerator"] if m["numerator"] is not None else "UNKNOWN"}'
        f'/{m["denominator"]}</b><small>{e(m["evidence_class"])}</small></article>'
        for m in data["global_outcomes"]
    )
    rows = "".join(
        f'<tr><td>{e(x["priority"])}</td><td><b>{e(x["outcome"])}</b>'
        f'<p>{e(x["action"])}</p></td><td>{e(x["state"])}</td>'
        f'<td>{e(x["proof"])}</td>'
        f'<td><a href="{e(x["source"])}">Source</a></td></tr>'
        for x in actions
    )
    page = (
        '<!doctype html><html lang="en"><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<title>MissionControl Global Definition of Value</title>'
        '<style>body{margin:0;background:#f3f5fa;color:#111e35;'
        'font:15px system-ui}header{background:#101b30;color:white;padding:24px}'
        'main{max-width:1350px;margin:auto;padding:16px}'
        '.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));'
        'gap:12px}article,section{background:white;border:1px solid #d3dbeb;'
        'border-radius:13px;padding:15px;margin-bottom:10px}'
        'article b{display:block;font-size:30px}small{color:#71819a}'
        'section{overflow-x:auto}table{width:100%;min-width:770px;border-collapse:collapse}'
        'td,th{padding:12px;border-bottom:1px solid #e0e6f0;text-align:left}'
        'th{background:#edf0fa}td p{max-width:460px}'
        '.hold{background:#fff3df;padding:12px;border-radius:8px}'
        '@media(max-width:500px){header{padding:14px}main{padding:10px}}'
        '</style><header><h1>Global Definition of Value</h1>'
        '<p>Useful owner output → verified proof → governed decision</p></header>'
        '<main><div class="tiles">' + tiles + '</div><section>'
        '<h2>Actionable work order</h2>'
        '<p class="hold">The 20 vs 19 QPS obligation disagreement is unresolved.'
        ' No engineering admission follows from this report.</p>'
        '<table><thead><tr><th>Priority</th><th>Outcome / action</th>'
        '<th>Readiness</th><th>Proof of value</th><th>Source</th></tr>'
        '</thead><tbody>' + rows + '</tbody></table></section>'
        '<section><p>Snapshot: ' + e(data["snapshot_date"])
        + ' · source SHA-256: ' + source_hash
        + '</p><p>HARD GATES: QPS DEFER · merge HOLD · native federation UNKNOWN.'
        ' No financial ROI or statistical BT priority is claimed.</p></section></main></html>'
    )
    (output / "index.html").write_text(page, encoding="utf-8")
    manifest = {
        "source_sha256": source_hash,
        "files": {
            name: hashlib.sha256((output / name).read_bytes()).hexdigest()
            for name in ("scorecard.json", "owner_actions.csv", "index.html")
        },
    }
    (output / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return {"status": "LOCAL_PROJECTION_PASS", "actions": len(actions),
            "source_sha256": source_hash, "engineering_credit": 0}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    try:
        print(json.dumps(produce(args.source, args.out), sort_keys=True))
        return 0
    except (ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
        print(json.dumps({"status": "HOLD", "reason": str(error)}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
