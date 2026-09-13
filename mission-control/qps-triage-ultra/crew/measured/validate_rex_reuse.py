#!/usr/bin/env python3
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CREW = ROOT.parent

ledger = json.loads((CREW / "REX_LEARNING_LEDGER_v1.json").read_text(encoding="utf-8"))
check = json.loads((ROOT / "REX_REUSE_CHECKLIST_v1.json").read_text(encoding="utf-8"))

ledger_ids = {e["rex_id"] for e in ledger["entries"]}
check_ids = {e["rex_id"] for e in check["checklist"]}
expected = {f"REX-{i:03d}" for i in range(1, 7)}

assert ledger_ids == expected, ("ledger_ids", sorted(ledger_ids))
assert check_ids == expected, ("check_ids", sorted(check_ids))
assert check["preflight_required"] is True
assert check["postflight_required"] is True
assert check["authority_transfer"] is False
assert set(check["recurrence_levels"]) == {"NEW", "RECURRING", "PERSISTENT", "REGRESSION"}

for row in check["checklist"]:
    assert row["before_task"], row["rex_id"]
    assert row["if_triggered"], row["rex_id"]
    assert row["proof_of_prevention"], row["rex_id"]

print(json.dumps({
    "status": "PASS_REX_REUSE_CHECKLIST",
    "rex_count": len(expected),
    "preflight_required": True,
    "postflight_required": True,
    "recurrence_levels": ["NEW", "RECURRING", "PERSISTENT", "REGRESSION"],
    "authority_transfer": False
}, sort_keys=True))
