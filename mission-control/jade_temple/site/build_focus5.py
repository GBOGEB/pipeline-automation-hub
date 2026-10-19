#!/usr/bin/env python3
"""JADE focus-five read-only native-evidence dashboard generator.

Data originates in owner-controlled GitHub receipt readback. This generator
never queries GitHub, launches jobs, marks roots closed or makes releases.
"""
from __future__ import annotations
import argparse
import csv
import io
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "FOCUS5_POINT_RELEASE_NPLUS7.json"
TEMPLATE = ROOT / "site" / "focus5_template.html"
OUTPUT = ROOT / "site" / "focus5.html"
CSV = ROOT / "site" / "focus5_burndown.csv"
TOKEN = "<!-- FOCUS5_CANONICAL_JSON -->"


def validate(data: dict) -> None:
    assert data["schema"] == "jade.temple.focus5.readonly/1.0"
    assert data["workflow"]["merge_admission"] == "HOLD"
    assert data["workflow"]["dispatch_performed"] is False
    assert data["source"]["release_authority_transfer"] is False
    assert len(data["rows"]) == 5
    assert data["metrics"]["required_gate_total"] == 60
    assert data["metrics"]["required_gate_count_per_repo"] == 12
    assert data["metrics"]["globally_admitted_point_release"] is None
    assert data["metrics"]["canonical_root_open"] is None
    assert data["metrics"]["canonical_root_closed"] is None
    keys = {x["id"] for x in data["requisites"]}
    assert len(keys) == 12
    passes = failures = unknowns = 0
    unique = set()
    for row in data["rows"]:
        assert row["repo"] not in unique
        unique.add(row["repo"])
        assert len(row["source_sha"]) == 40
        assert row["release"] == "HOLD"
        assert len(row["gates"]) == 12
        assert {g["id"] for g in row["gates"]} == keys
        assert row["gate_denominator"] == 12
        assert row["authenticated_crew"] is None
        assert row["accepted_root_count"] is None
        counts = {k: sum(g["status"] == k for g in row["gates"])
                  for k in ("PASS", "FAIL", "UNKNOWN")}
        assert sum(counts.values()) == 12
        assert row["verified_complete"] == counts["PASS"]
        assert row["verified_failed"] == counts["FAIL"]
        assert row["unqualified"] == counts["UNKNOWN"]
        assert row["percent"] == round(100 * counts["PASS"] / 12, 2)
        passes += counts["PASS"]
        failures += counts["FAIL"]
        unknowns += counts["UNKNOWN"]
    assert (passes, failures, unknowns) == (
        data["metrics"]["passed"], data["metrics"]["failed"],
        data["metrics"]["unknown"])
    assert passes + failures + unknowns == 60
    assert data["metrics"]["verified_completion_pct"] == round(100 * passes / 60, 2)
    for edge in data["edges"]:
        assert edge["causal_root_proof"] is False
        assert edge["weight"] is None
        assert edge["state"] != "RELEASE_APPROVED"


def render(source_text: str, template: str) -> str:
    data = json.loads(source_text)
    validate(data)
    if source_text.lower().find("</script") >= 0:
        raise ValueError("script-close token prohibited in embedded source")
    if template.count(TOKEN) != 1:
        raise ValueError("template requires one data placeholder")
    return template.replace(TOKEN, source_text.strip())



def make_csv(source_text: str) -> str:
    data = json.loads(source_text)
    validate(data)
    buf = io.StringIO(newline="")
    writer = csv.writer(buf, lineterminator="\\n")
    writer.writerow(["rank", "repo", "source_sha", "gate_id", "gate_label",
                     "status", "verified_complete", "denominator",
                     "evidence_url", "next_owner_action"])
    for row in data["rows"]:
        for gate in row["gates"]:
            writer.writerow([
                row["rank"], row["repo"], row["source_sha"], gate["id"],
                gate["label"], gate["status"],
                "1" if gate["status"] == "PASS" else "0",
                row["gate_denominator"], gate["evidence"] or "",
                row["owner_action"],
            ])
    return buf.getvalue()


def main() -> None:
    parser = argparse.ArgumentParser()
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--check", action="store_true")
    modes.add_argument("--build", action="store_true")
    args = parser.parse_args()
    source = DATA.read_text(encoding="utf-8")
    result = render(source, TEMPLATE.read_text(encoding="utf-8"))
    tabular = make_csv(source)
    digest = hashlib.sha256(result.encode("utf-8")).hexdigest()
    if args.check:
        if not OUTPUT.is_file() or OUTPUT.read_text(encoding="utf-8") != result:
            raise SystemExit("FAIL: generated focus-five page out of sync")
        if not CSV.is_file() or CSV.read_text(encoding="utf-8") != tabular:
            raise SystemExit("FAIL: generated focus-five CSV out of sync")
        print("PASS focus-five HTML + CSV source parity SHA256=" + digest)
    else:
        OUTPUT.write_text(result, encoding="utf-8")
        CSV.write_text(tabular, encoding="utf-8")
        print("BUILD focus-five HTML + CSV SHA256=" + digest)


if __name__ == "__main__":
    main()
