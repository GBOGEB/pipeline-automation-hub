"""Shared helpers for the thread tools: the gh wrapper and the parked-intent parser owner.

The parked-intent marker parser belongs to the triway burndown (AGENTS.md L4); it is
loaded here by path, never copied.
"""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import time
from pathlib import Path

OWNER = "GBOGEB"
LABEL = "parked-intent"
MARK = "<!-- parked-intent:v1 "
ROOT = Path(__file__).resolve().parents[2]
TRIWAY_PATH = ROOT / "mission-control" / "qps-triage-ultra" / "issue-expedition" / "triway_burndown.py"
TRANSPORT = ("dial tcp", "connection attempt failed", "timeout", "EOF", "connection reset")


def _load_triway():
    spec = importlib.util.spec_from_file_location("triway_burndown", TRIWAY_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


triway = _load_triway()


def gh_env() -> dict:
    """The environment without GITHUB_TOKEN / GH_TOKEN, so gh uses its keyring sign-in.

    Shells started before a token was revoked still carry the dead value.
    """
    return {k: v for k, v in os.environ.items() if k not in ("GITHUB_TOKEN", "GH_TOKEN")}


def gh(*args: str, stdin: str | None = None, tries: int = 4) -> str:
    """Run gh; transport errors are retried, API errors raise RuntimeError."""
    for n in range(tries):
        r = subprocess.run(["gh", *args], input=stdin, capture_output=True, text=True,
                           encoding="utf-8", env=gh_env())
        if r.returncode == 0:
            return r.stdout
        if n + 1 < tries and any(t in r.stderr for t in TRANSPORT):
            time.sleep(5 * (n + 1))
            continue
        raise RuntimeError("gh " + " ".join(args[:4]) + ": " + r.stderr.strip()[:300])
    raise AssertionError("unreachable")


def gh_json(*args: str):
    out = gh(*args)
    return json.loads(out) if out.strip() else []
