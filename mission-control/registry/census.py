#!/usr/bin/env python3
"""GBOGEB canonical registry census (#529 G01): one SSOT, readable/retrievable YAML tiers.

Owner decision G01: pick ONE canonical registry (the most developed) and derive every list
(top/bottom 3, 7, 14, 21, 50, 100) from it as readable YAML, for repositories AND binaries.

  repos     All account repositories (seed listing, optionally refreshed in CI) enriched with
            the richest existing per-repo schema (JADE REPO_READINESS_NPLUS1: priority, lane,
            owner role, technical need, MACH tier) and every mission list membership, ranked
            by a documented, recomputable score -> REPO_REGISTRY.yaml (canonical) +
            REPO_TIERS.yaml (views) + drift crosswalk of the legacy lists.
  binaries  Every binary blob in the core repositories: path, git object id (O-ID), bytes,
            type, hierarchy, references from text files, duplicate content groups with one
            canonical path -> BINARY_REGISTRY.yaml + BINARY_TIERS.yaml + BINARY_INDEX.json.
  get       Read one tier back:  census.py get REPO_TIERS.yaml all.top_7
Read-only: local files + git object metadata. No authority, no merge.
"""
from __future__ import annotations

import argparse
import ast
import json
import math
import re
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import yaml

HUB = Path(__file__).resolve().parents[2]
TIERS = (3, 7, 14, 21, 50, 100)
SCHEMA_REPO = "gbogeb.registry.repos.v1"
SCHEMA_BIN = "gbogeb.registry.binaries.v1"
JADE_FIELDS = ("priority", "lane", "owner_role", "mach_proposal", "technical_need", "next_point_release_todo")


class Dumper(yaml.SafeDumper):
    pass


Dumper.add_representer(str, lambda d, s: d.represent_scalar("tag:yaml.org,2002:str", s, style="|" if "\n" in s else None))


def dump(obj, path: Path, header: str):
    text = yaml.dump(obj, Dumper=Dumper, sort_keys=False, allow_unicode=True, width=110)
    path.write_text("".join("# " + h + "\n" for h in header.strip().splitlines()) + text, encoding="utf-8")


# ------------------------------------------------------------------ repositories
def read_seed(tsv: Path):
    rows = []
    for line in tsv.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        name, pushed, vis, fork = line.split("\t")
        rows.append({"name": name, "pushed_at": pushed, "visibility": vis, "fork": fork == "true"})
    return rows


def mission_lists(hub: Path):
    """Every existing repo list in the hub = legacy views to reconcile."""
    out = {}
    out["TOP21_COHORT_ROSTER"] = [x.split("/")[-1] for x in json.loads(
        (hub / "mission-control/federation-atlas/central/top21/TOP21_COHORT_ROSTER.json").read_text())]
    top7 = json.loads((hub / "mission-control/federation-atlas/TOP7_CENSUS_PULSES_v1.json").read_text())
    out["TOP7_CENSUS"] = [r["repo"].split("/")[-1] for r in top7["pulses"][-1]["rows"]]
    src = (hub / "mission-control/federation-atlas/live-census/source/live_census.py").read_text()
    out["LIVE_CENSUS_REPOS"] = list(ast.literal_eval(re.search(r"REPOS = (\{.*?\})", src, re.S).group(1)))
    fed = hub / "mission-control/jade_temple/data/RED_TRACE_FEDERATION_N8.json"
    if fed.exists():
        out["RED_TRACE_CORE"] = [r["short"] for r in json.loads(fed.read_text())["repositories"]]
    return out


def jade_rows(hub: Path):
    d = json.loads((hub / "mission-control/jade_temple/data/REPO_READINESS_NPLUS1.json").read_text())
    return {r["repo"].split("/")[-1]: r for r in d["rows"]}


def recency_points(days):
    for lim, pts in ((2, 25), (7, 20), (30, 12), (90, 6), (365, 2)):
        if days <= lim:
            return pts
    return 0


def score_repo(r, lists, jade, now):
    core = r["name"] in set(lists.get("LIVE_CENSUS_REPOS", [])) | set(lists.get("RED_TRACE_CORE", []))
    days = (now - datetime.fromisoformat(r["pushed_at"].replace("Z", "+00:00"))).total_seconds() / 86400
    pr = (jade.get(r["name"], {}).get("priority") or "")
    parts = {
        "core_federation": 30 if core else 0,
        "top7": 12 if r["name"] in lists.get("TOP7_CENSUS", []) else 0,
        "top21": 8 if r["name"] in lists.get("TOP21_COHORT_ROSTER", []) else 0,
        "jade_priority": {"P0": 5, "P1": 3, "P2": 1}.get(pr, 0),
        "recency": recency_points(days),
        "fork": -20 if r["fork"] else 0,
        "archived": -30 if r.get("archived") else 0,
    }
    return sum(parts.values()), parts, round(days, 1)


SCORE_RULE = ("score = core_federation 30 (live census / red-trace core) + TOP7 12 + TOP21 8 + JADE priority "
              "(P0 5, P1 3, P2 1) + recency (<=2 d 25, <=7 d 20, <=30 d 12, <=90 d 6, <=365 d 2) - fork 20 - archived 30; "
              "ties: newer push first, then name")


def repo_census(seed: Path, hub: Path, out: Path, now=None):
    now = now or datetime.now(timezone.utc)
    lists, jade = mission_lists(hub), jade_rows(hub)
    rows = []
    for r in read_seed(seed):
        s, parts, days = score_repo(r, lists, jade, now)
        j = jade.get(r["name"], {})
        rows.append({
            "name": r["name"], "full_name": "GBOGEB/" + r["name"], "score": s, "score_parts": parts,
            "visibility": r["visibility"], "fork": r["fork"], "pushed_at": r["pushed_at"], "days_since_push": days,
            "memberships": sorted(k for k, v in lists.items() if r["name"] in v),
            **({"jade": {k: j[k] for k in JADE_FIELDS if k in j}} if j else {}),
            "class": ("CORE" if parts["core_federation"] else "SATELLITE" if parts["top7"] else
                      "UPSTREAM_FORK" if r["fork"] else "OWNED"),
        })
    rows.sort(key=lambda x: (-x["score"], -datetime.fromisoformat(x["pushed_at"].replace("Z", "+00:00")).timestamp(), x["name"]))
    for i, x in enumerate(rows, 1):
        x["rank"] = i
    rows = [{"rank": x.pop("rank"), **x} for x in rows]
    owned = [x for x in rows if not x["fork"]]

    def tiers(pop):
        t = {"population": len(pop)}
        for n in TIERS:
            t[f"top_{n}"] = [x["name"] for x in pop[:n]]
        for n in TIERS:
            if n < len(pop):
                t[f"bottom_{n}"] = [x["name"] for x in pop[-n:][::-1]]
        return t
    tier = {"schema": "gbogeb.registry.repo_tiers.v1", "canonical_source": "mission-control/registry/REPO_REGISTRY.yaml",
            "score_rule": SCORE_RULE, "observed_at_utc": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "all": tiers(rows), "owned": tiers(owned)}
    drift = {}
    for name, lst in lists.items():
        n = len(lst)
        ref = tier["all"].get(f"top_{n}") or [x["name"] for x in rows[:n]]
        drift[name] = {"size": n, "compared_with": f"top_{n}" if n in TIERS else f"first {n}",
                       "overlap": sorted(set(lst) & set(ref)), "only_in_legacy": sorted(set(lst) - set(ref)),
                       "only_in_registry": sorted(set(ref) - set(lst))}
    tier["legacy_list_drift"] = drift
    reg = {"schema": SCHEMA_REPO, "canonical": True,
           "decision": "#529 G01 (owner): ONE canonical registry; every other list is a derived view or legacy input",
           "schema_base": "JADE REPO_READINESS_NPLUS1 (most developed: 21 rows x 24 fields) extended to the whole account",
           "observed_at_utc": tier["observed_at_utc"], "seed": seed.relative_to(hub).as_posix(),
           "legacy_inputs": {k: len(v) for k, v in lists.items()}, "score_rule": SCORE_RULE,
           "population": len(rows), "classes": dict(Counter(x["class"] for x in rows)),
           "repositories": rows, "merge_authorized": False}
    out.mkdir(parents=True, exist_ok=True)
    dump(reg, out / "REPO_REGISTRY.yaml", "CANONICAL GBOGEB repository registry (SSOT). Generated: python mission-control/registry/census.py repos\nRead a tier: python mission-control/registry/census.py get mission-control/registry/REPO_TIERS.yaml all.top_7")
    dump(tier, out / "REPO_TIERS.yaml", "Derived views of REPO_REGISTRY.yaml (do not edit). all = 90 repos, owned = non-fork.")
    return reg, tier


# ------------------------------------------------------------------ binaries
BIN_EXT = {"pptx", "ppt", "docx", "doc", "xlsx", "xlsm", "xls", "pdf", "zip", "gz", "tgz", "7z", "png", "jpg", "jpeg",
           "gif", "ico", "bmp", "tif", "tiff", "webp", "svgz", "woff", "woff2", "ttf", "otf", "eot", "whl", "pkl",
           "npy", "npz", "parquet", "db", "sqlite", "h5", "mp4", "mp3", "wav", "exe", "dll", "so", "dylib", "jar",
           "class", "pyc", "vsdx", "dwg", "dxf", "msg", "eml", "onnx", "pt", "bin"}
REF_RX = re.compile(r"[\w\-.()%+@ ]{1,160}?\.(?:" + "|".join(sorted(BIN_EXT, key=len, reverse=True)) + r")\b", re.I)


def git_files(repo: Path):
    raw = subprocess.run(["git", "-C", str(repo), "ls-files", "-s", "-z"], capture_output=True, check=True).stdout
    for rec in raw.split(b"\0"):
        if not rec:
            continue
        meta, path = rec.split(b"\t", 1)
        mode, oid, _ = meta.decode().split()
        yield mode, oid, path.decode("utf-8", "surrogateescape")


def is_binary(p: Path, ext: str):
    if ext in BIN_EXT:
        return True
    try:
        with p.open("rb") as f:
            return b"\0" in f.read(8000)
    except OSError:
        return False


def binary_census(repos: dict, out: Path, now=None):
    now = now or datetime.now(timezone.utc)
    index, per_repo = [], {}
    for rname, root in repos.items():
        root = Path(root)
        head = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
        bins, texts = [], []
        for mode, oid, path in git_files(root):
            if mode == "120000" or mode == "160000":
                continue
            p = root / path
            if not p.is_file():
                continue
            ext = path.rsplit(".", 1)[-1].lower() if "." in Path(path).name else ""
            if is_binary(p, ext):
                bins.append({"repo": rname, "path": path, "name": Path(path).name, "ext": ext or "(none)",
                             "oid": oid, "bytes": p.stat().st_size, "top_dir": path.split("/")[0] if "/" in path else ".",
                             "depth": path.count("/")})
            elif p.stat().st_size <= 2_000_000:
                texts.append(p)
        names = sorted({b["name"].lower() for b in bins}, key=len, reverse=True)
        refs = Counter()
        for t in texts:
            try:
                s = t.read_text(encoding="utf-8", errors="ignore").lower().replace("%20", " ")
            except OSError:
                continue
            if not REF_RX.search(s):
                continue
            for n in names:  # exact basename occurrences (names may contain spaces)
                k = s.count(n)
                if k:
                    refs[n] += k
        groups = defaultdict(list)
        for b in bins:
            b["refs"] = refs.get(b["name"].lower(), 0)
            b["priority"] = round(10 * min(b["refs"], 10) + math.log2(b["bytes"] + 1), 2)
            groups[b["oid"]].append(b)
        dup_groups = 0
        for oid, g in groups.items():
            g.sort(key=lambda b: (-b["refs"], len(b["path"]), b["path"]))
            for i, b in enumerate(g):
                b["copies"] = len(g)
                b["canonical"] = i == 0
                b["canonical_path"] = g[0]["path"]
            dup_groups += len(g) > 1
        index += bins
        by_ext = defaultdict(lambda: [0, 0])
        by_dir = defaultdict(lambda: [0, 0])
        for b in bins:
            by_ext[b["ext"]][0] += 1
            by_ext[b["ext"]][1] += b["bytes"]
            by_dir[b["top_dir"]][0] += 1
            by_dir[b["top_dir"]][1] += b["bytes"]
        tot = sum(b["bytes"] for b in bins)
        per_repo[rname] = {
            "head_sha": head, "binaries": len(bins), "bytes": tot, "unique_contents": len(groups),
            "duplicate_groups": dup_groups, "duplicate_bytes": tot - sum(g[0]["bytes"] for g in groups.values()),
            "referenced": sum(1 for b in bins if b["refs"]), "unreferenced": sum(1 for b in bins if not b["refs"]),
            "by_type": {k: {"files": v[0], "bytes": v[1]} for k, v in sorted(by_ext.items(), key=lambda kv: -kv[1][1])[:15]},
            "hierarchy_top_dirs": {k: {"files": v[0], "bytes": v[1]} for k, v in sorted(by_dir.items(), key=lambda kv: -kv[1][1])[:15]},
            "depth_spread": dict(sorted(Counter(b["depth"] for b in bins).items())),
        }

    def row(b):
        return {"repo": b["repo"], "path": b["path"], "oid": b["oid"][:12], "bytes": b["bytes"], "refs": b["refs"],
                "copies": b["copies"], "canonical": b["canonical"]}
    canon = [b for b in index if b["canonical"]]
    by_pri = sorted(canon, key=lambda b: (-b["priority"], b["repo"], b["path"]))
    by_size = sorted(canon, key=lambda b: (-b["bytes"], b["repo"], b["path"]))
    tiers = {"schema": "gbogeb.registry.binary_tiers.v1", "canonical_source": "mission-control/registry/BINARY_INDEX.json",
             "priority_rule": "priority = 10 x min(text references, 10) + log2(bytes + 1); canonical copy per content (git O-ID) only",
             "population_unique_contents": len(canon)}
    for key, seq in (("priority", by_pri), ("size", by_size)):
        for n in TIERS:
            tiers[f"{key}.top_{n}"] = [row(b) for b in seq[:n]]
        for n in (3, 7, 14, 21, 50):
            if n < len(seq):
                tiers[f"{key}.bottom_{n}"] = [row(b) for b in seq[-n:][::-1]]
    reg = {"schema": SCHEMA_BIN, "canonical": True, "observed_at_utc": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
           "identity": "git blob object id (O-ID) per path; identical O-ID = identical bytes; canonical = most referenced, then shortest path",
           "totals": {"binaries": len(index), "bytes": sum(b["bytes"] for b in index), "unique_contents": len(canon),
                      "duplicate_copies": len(index) - len(canon),
                      "duplicate_bytes": sum(b["bytes"] for b in index if not b["canonical"])},
           "repositories": per_repo, "merge_authorized": False}
    out.mkdir(parents=True, exist_ok=True)
    dump(reg, out / "BINARY_REGISTRY.yaml", "CANONICAL binary registry summary (SSOT). Generated: python mission-control/registry/census.py binaries")
    dump(tiers, out / "BINARY_TIERS.yaml", "Derived binary tiers (do not edit). Full index: BINARY_INDEX.json")
    (out / "BINARY_INDEX.json").write_text(json.dumps(sorted(index, key=lambda b: (b["repo"], b["path"])),
                                                      separators=(",", ":"), sort_keys=True) + "\n", encoding="utf-8")
    return reg, tiers


# ------------------------------------------------------------------ reader
def get(path: Path, dotted: str):
    d = yaml.safe_load(path.read_text(encoding="utf-8"))
    if dotted in d:
        return d[dotted]
    cur = d
    for part in dotted.split("."):
        if not isinstance(cur, dict) or part not in cur:
            raise KeyError(f"{dotted} not in {path.name}; available: {', '.join(k for k in d if not k.startswith('schema'))}")
        cur = cur[part]
    return cur


def main(argv=None):
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("repos")
    r.add_argument("--seed", type=Path, default=HUB / "mission-control/registry/seed/ORG_LISTING_20261020.tsv")
    r.add_argument("--out", type=Path, default=HUB / "mission-control/registry")
    r.add_argument("--now", help="ISO time for reproducible scoring")
    b = sub.add_parser("binaries")
    b.add_argument("--repo", action="append", required=True, help="NAME=PATH (git checkout)")
    b.add_argument("--out", type=Path, default=HUB / "mission-control/registry")
    g = sub.add_parser("get")
    g.add_argument("file", type=Path)
    g.add_argument("tier")
    a = ap.parse_args(argv)
    if a.cmd == "repos":
        now = datetime.fromisoformat(a.now.replace("Z", "+00:00")) if a.now else None
        reg, tier = repo_census(a.seed, HUB, a.out, now)
        print(json.dumps({"population": reg["population"], "classes": reg["classes"], "top_7": tier["all"]["top_7"]}))
    elif a.cmd == "binaries":
        reg, _ = binary_census(dict(x.split("=", 1) for x in a.repo), a.out)
        print(json.dumps(reg["totals"]))
    else:
        v = get(a.file, a.tier)
        print(yaml.safe_dump(v, sort_keys=False, allow_unicode=True).rstrip() if not isinstance(v, list) or (v and isinstance(v[0], dict))
              else "\n".join(map(str, v)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
