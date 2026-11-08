#!/usr/bin/env python3
"""Deterministic offline W19 view from the governed observations JSON.

No network access, ticket mutations, live recensus or engineering-credit claims.
Run: python docs/mission-control/w19/render.py --write
QA:  python docs/mission-control/w19/render.py --check
"""
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = HERE / "observations.json"
TEMPLATE = HERE / "burndown.template.html"
OUTPUT = HERE / "burndown.html"
ERROR_SENTINEL = "The requested file reference is not currently visible"


def render(source: bytes, template: str) -> str:
    d = json.loads(source)
    if not (
        d["schema"] == "code-purple.w19.integer-burndown.v1"
        and d["authority_transfer"] is False
        and d["merge_admission"] == "HOLD"
        and d["engineering_root_closure_credit"] == 0
        and d["formal_root_closure_credit"] == 0
        and d["search"]["incomplete_results"] is False
        and d["membership"]["current"] == d["search"]["total"] == 141
        and len(d["triage"]) == 20
        and len(d["counts"]) == 6
        and all(type(x) is int for x in d["counts"])
    ):
        raise ValueError("W19 source invariants changed; owner recensus required")
    if ERROR_SENTINEL in template:
        raise ValueError("Template contaminated by tool error")
    marker = "blob " + str(len(source)) + "\0"
    oid = hashlib.sha1(marker.encode("ascii") + source).hexdigest()
    payload = json.dumps(d, separators=(",", ":"), ensure_ascii=True)
    payload = payload.replace("<", r"\u003c")
    if template.count("__SOURCE_JSON__") != 1 or "__SOURCE_BLOB__" not in template:
        raise ValueError("Template placeholders missing or ambiguous")
    result = template.replace("__SOURCE_JSON__", payload).replace("__SOURCE_BLOB__", oid)
    if ERROR_SENTINEL in result or "__SOURCE_JSON__" in result:
        raise ValueError("Rendered output contaminated or incomplete")
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--check", action="store_true")
    group.add_argument("--write", action="store_true")
    args = parser.parse_args()
    output = render(SOURCE.read_bytes(), TEMPLATE.read_text(encoding="utf-8"))
    if args.check:
        if not OUTPUT.exists() or OUTPUT.read_text(encoding="utf-8") != output:
            print("W19_SOURCE_RENDER_MISMATCH; run render.py --write")
            return 1
        print("W19_SOURCE_RENDER_PASS")
        return 0
    OUTPUT.write_text(output, encoding="utf-8", newline="\n")
    print("W19_SOURCE_RENDER_WRITTEN")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
