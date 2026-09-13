#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

EXPECTED_MUST_NOT = {
    "promote notebook execution to engineering authority",
    "promote runtime PASS to domain validation",
    "override child authority",
}


def fail(message):
    print(f"F03 authority validation failed: {message}")
    raise SystemExit(1)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("ssot")
    args = parser.parse_args()
    data = json.loads(Path(args.ssot).read_text(encoding="utf-8"))

    if data.get("schema") != "gbogeb-level1-ssot/v1":
        fail("schema must be gbogeb-level1-ssot/v1")
    if data.get("repo") != "GBOGEB/codespaces-jupyter":
        fail("repo must be GBOGEB/codespaces-jupyter")
    if data.get("role") != "REPRODUCIBLE_NOTEBOOK_RUNTIME_PRODUCER":
        fail("role must be REPRODUCIBLE_NOTEBOOK_RUNTIME_PRODUCER")
    if data.get("authority_transfer") is not False:
        fail("authority_transfer must be false")

    must_not = set(data.get("authority", {}).get("must_not", []))
    missing = sorted(EXPECTED_MUST_NOT - must_not)
    if missing:
        fail("missing must_not boundary: " + ", ".join(missing))

    promotion = data.get("promotion_requires", "")
    if "executes >0 cells twice" not in promotion:
        fail("promotion_requires must require >0 cells twice")

    print("validated F03 Level-1 SSOT identity")
    print("validated F03 runtime producer role")
    print("validated F03 authority_transfer=false")
    print("validated F03 must_not authority boundary")
    print("F03 authority validation passed")


if __name__ == "__main__":
    main()
