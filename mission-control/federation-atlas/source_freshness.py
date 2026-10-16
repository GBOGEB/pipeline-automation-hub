"""Fail-closed source freshness contract; advisory only, no time inference.

Builds are deterministic unless an explicit observation day is injected by a caller.
An ordinal series or mission-id suffix is not silently treated as a timestamp.
"""
from __future__ import annotations
from datetime import date

ALLOWED_BASES = {"observed_on", "captured_at", "snapshot_at"}
SCHEMA = "missioncontrol.code_purple.source_freshness.v1"

def _date(value):
    if not isinstance(value, str) or len(value) < 10:
        return None
    try:
        d = date.fromisoformat(value[:10])
    except ValueError:
        return None
    if value[10:] and value[10] not in ("T", " "):
        return None
    return d

def annotate(sources, observed_on=None, ttl_days=14):
    if type(ttl_days) is not int or not 0 <= ttl_days <= 366:
        raise ValueError("invalid ttl_days")
    if observed_on is not None and (_date(observed_on) is None or len(observed_on) != 10):
        raise ValueError("invalid observed_on")
    now = _date(observed_on)
    rows = []
    for item in sources:
        name = item.get("name")
        basis = item.get("as_of_basis")
        stamp = item.get("as_of")
        candidate = _date(stamp) if basis in ALLOWED_BASES else None
        age = (now - candidate).days if now and candidate else None
        if age is None:
            state = "UNKNOWN"
        elif age < 0:
            state = "FUTURE_INVALID"
        elif age > ttl_days:
            state = "STALE"
        else:
            state = "FRESH"
        rows.append({"name": name, "as_of": stamp, "basis": basis,
                     "age_days": age, "ttl_days": ttl_days,
                     "state": state, "eligible_fresh": state == "FRESH"})
    return {"schema": SCHEMA, "observed_on": observed_on, "ttl_days": ttl_days,
            "authority_transfer": False, "formal_credit_delta": 0, "sources": rows}
