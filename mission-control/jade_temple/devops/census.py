#!/usr/bin/env python3
"""JADE N+9 DevOps fleet census: exact-head, object-addressed lifecycle evidence for the TOP21.

fetch : blobless bare clones (--filter=blob:none --depth=1) of every roster repository into a
        cache, the N11 baseline commit next to HEAD, landed history since the baseline, then ONE
        batched blob fetch per repository for exactly the classified paths. Nothing is checked
        out and nothing from a scanned repository is executed.
scan  : reads git objects at the exact HEAD (and baseline) commit, classifies DevOps assets into
        lifecycle stages S0..S9, parses workflows (job needs-DAG, environments, DP1..DP10),
        inventories tests (cases per file, zero-case files, Python modules with no referencing
        test), crosswalks red-trace first-red roots, scores maturity and writes
        data/DEVOPS_CENSUS_N9.json + data/DEVOPS_OBJECTS_N9.json.
check : offline invariants of the committed census (schema, digest, reconciliation, no PASS
        without evidence, no authority).

Identity: every object carries its git id (commit / tree / blob, 40-hex, exactly what
`git rev-parse <commit>:<path>` returns) and a descriptive OID URN (jade:<kind>:<repo>:<locator>).
UNKNOWN is never PASS. No merge, release or deploy authority is derived here.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
import warnings
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent  # mission-control/jade_temple
sys.path.insert(0, str(HERE))
import lifecycle as L  # noqa: E402
import workflows as W  # noqa: E402

_pb = importlib.util.spec_from_file_location("jade_private_boundary", ROOT / "tools" / "private_boundary.py")
PB = importlib.util.module_from_spec(_pb)
_pb.loader.exec_module(PB)

SCHEMA = "jade.devops.census.v1"
OBJ_SCHEMA = "jade.devops.objects.v1"
ROSTER = "data/TOP21_PORTFOLIO.json"
RED_TRACE = "data/RED_TRACE_FEDERATION_N8.json"
OUT = ROOT / "data" / "DEVOPS_CENSUS_N9.json"
OUT_OBJ = ROOT / "data" / "DEVOPS_OBJECTS_N9.json"
OUT_MD = HERE / "DEVOPS_CENSUS_N9_READING.md"
ROSTER_BASELINE_LABEL = "TOP21 N11 roster head 2026-10-18 (non-atomic)"


def paths(iteration: str) -> tuple[Path, Path, Path]:
    """Committed census, object table and reading for one pulse (N9, N10, ...). Earlier pulses stay immutable."""
    return (ROOT / "data" / f"DEVOPS_CENSUS_{iteration}.json", ROOT / "data" / f"DEVOPS_OBJECTS_{iteration}.json",
            HERE / f"DEVOPS_CENSUS_{iteration}_READING.md")


def census_baseline(prev: dict) -> dict:
    """Use a previous pulse's exact heads as the delta baseline (pulse-over-pulse instead of roster heads)."""
    return {"kind": "census", "iteration": prev["iteration"], "digest_sha256": prev["digest_sha256"],
            "label": f"census {prev['iteration']} heads ({prev['observed_at_utc']})",
            "heads": {r["repo"]: r["head_sha"] for r in prev["repos"] if r.get("head_sha")}}
HUB = "GBOGEB/pipeline-automation-hub"
HUB_PREFIX = "mission-control/jade_temple/"
SHA40 = re.compile(r"^[0-9a-f]{40}$")
EVIDENCE_CAP = 40
UNTESTED_CAP = 25
MAX_BLOB = 1_500_000

# Hub-held written contracts per stage (formalization input; existence and blob OID are read at HEAD).
CONTRACTS = {
    "S0_PLAN": ["mission-control/jade_temple/04_REPO_ROOT_SPINE_CONTRACT.md", "mission-control/jade_temple/05_MACH_TIERS.md"],
    "S1_CODE": [],
    "S2_BUILD": [],
    "S3_TEST": ["mission-control/federation-atlas/CODE_PURPLE_BEAMS_DAG_v1.json", "scripts/zero_test_gate_audit.py"],
    "S4_SECURE": [],
    "S5_RELEASE": ["mission-control/jade_temple/02_CHARTER.md"],
    "S6_DEPLOY": ["mission-control/jade_temple/devops/DEPLOY_PRODUCTION_ARCHITECTURE_N9.md",
                  "mission-control/jade_temple/notes/NAVIGATION_PAGES_STYLE_CONTRACT.md"],
    "S7_OPERATE": ["mission-control/jade_temple/tools/hosted_parity.py"],
    "S8_MONITOR": [],
    "S9_CONTROL": ["mission-control/federation-atlas/CODE_PURPLE_BD_QUEUE_v1.json",
                   "mission-control/jade_temple/notes/JADE_STOP_RULES_CONTRACT.md",
                   "mission-control/gogreen/red_trace/README.md"],
}

_r = lambda p: re.compile(p, re.I)
# (path regex, stage, kind). First match per kind; a path may carry several kinds.
RULES = [
    (_r(r"^readme(\.[a-z]+)?$"), "S0_PLAN", "readme_root"),
    (_r(r"^\.github/issue_template(/|\.md$)|^issue_template\.md$"), "S0_PLAN", "issue_template"),
    (_r(r"(^|/)pull_request_template(\.md)?$|^\.github/pull_request_template/"), "S0_PLAN", "pr_template"),
    (_r(r"^(\.github/|docs/)?codeowners$"), "S0_PLAN", "codeowners"),
    (_r(r"(^|/)(adr|adrs|decisions)/[^/]+\.md$|(^|/)roadmap[^/]*\.(md|json|ya?ml)$|(^|/)[^/]*bd_queue[^/]*$|"
        r"(^|/)decision[_-]?log[^/]*$|^contributing(\.md)?$|^\.github/contributing(\.md)?$|^governance(\.md)?$"),
     "S0_PLAN", "register"),
    (_r(r"(^|/)(\.flake8|\.pylintrc|pylintrc|ruff\.toml|\.ruff\.toml|\.eslintrc[^/]*|eslint\.config\.[cm]?[jt]s|"
        r"\.prettierrc[^/]*|prettier\.config\.[cm]?js|\.editorconfig|\.markdownlint[^/]*|\.yamllint[^/]*|"
        r"\.golangci\.ya?ml|rustfmt\.toml|\.clang-format|psscriptanalyzersettings\.psd1|mypy\.ini|\.mypy\.ini|"
        r"pyrightconfig\.json|\.stylelintrc[^/]*|biome\.jsonc?)$"), "S1_CODE", "lint_config"),
    (_r(r"(^|/)\.pre-commit-config\.ya?ml$"), "S1_CODE", "precommit"),
    (_r(r"(^|/)(pyproject\.toml|setup\.py|setup\.cfg|package\.json|go\.mod|cargo\.toml|makefile|gnumakefile|"
        r"cmakelists\.txt|build\.gradle(\.kts)?|pom\.xml|[^/]+\.csproj|[^/]+\.sln|dockerfile[^/]*|[^/]*\.dockerfile|"
        r"requirements[^/]*\.txt|environment\.ya?ml|tox\.ini|noxfile\.py)$"), "S2_BUILD", "build_manifest"),
    (_r(r"(^|/)(package-lock\.json|npm-shrinkwrap\.json|yarn\.lock|pnpm-lock\.yaml|poetry\.lock|uv\.lock|"
        r"pipfile\.lock|pdm\.lock|go\.sum|cargo\.lock|composer\.lock|gemfile\.lock|packages\.lock\.json|"
        r"requirements[^/]*\.lock|constraints[^/]*\.txt)$"), "S2_BUILD", "lockfile"),
    (_r(r"(^|/)(pytest\.ini|conftest\.py|\.coveragerc|codecov\.ya?ml|\.codecov\.ya?ml|jest\.config\.[cm]?[jt]s|"
        r"vitest\.config\.[cm]?[jt]s|karma\.conf\.js|\.mocharc[^/]*|phpunit\.xml[^/]*|playwright\.config\.[cm]?[jt]s)$"),
     "S3_TEST", "test_config"),
    (_r(r"^(\.github/|docs/)?security(\.md)?$"), "S4_SECURE", "security_policy"),
    (_r(r"^\.github/dependabot\.ya?ml$|(^|/)renovate\.json5?$|^\.renovaterc[^/]*$"), "S4_SECURE", "dependency_bot"),
    (_r(r"(^|/)[^/]*(sbom|cyclonedx|\.spdx)[^/]*\.(json|xml|spdx)$"), "S4_SECURE", "sbom"),
    (_r(r"^(changelog|changes|history|release[_-]?notes|releases)(\.[a-z]+)?$|(^|/)changelog\.md$"),
     "S5_RELEASE", "changelog"),
    (_r(r"(^|/)(\.goreleaser\.ya?ml|\.releaserc[^/]*|release\.config\.[cm]?js|release-please-config\.json|"
        r"\.release-please-manifest\.json|\.changeset/config\.json|_version\.py|\.bumpversion\.cfg)$|^version(\.txt)?$"),
     "S5_RELEASE", "release_config"),
    (_r(r"(^|/)(docker-compose[^/]*\.ya?ml|compose\.ya?ml|procfile|fly\.toml|vercel\.json|netlify\.toml|render\.ya?ml|"
        r"railway\.(json|toml)|chart\.yaml|kustomization\.ya?ml|skaffold\.ya?ml|[^/]+\.tf|[^/]+\.bicep|"
        r"serverless\.ya?ml|samconfig\.toml|mkdocs\.ya?ml|\.nojekyll)$|^cname$|^_config\.yml$|"
        r"(^|/)(k8s|kubernetes|helm|charts|terraform)/[^/]+"), "S6_DEPLOY", "deploy_descriptor"),
    (_r(r"(^|/)(docker-compose[^/]*\.ya?ml|compose\.ya?ml|procfile|[^/]+\.service|supervisord\.conf|\.env\.example|"
        r"\.env\.sample|nginx[^/]*\.conf|gunicorn[^/]*\.py|uwsgi\.ini|ecosystem\.config\.js)$|(^|/)(k8s|kubernetes|helm)/[^/]+"),
     "S7_OPERATE", "runtime_descriptor"),
    (_r(r"(^|/)[^/]*(runbook|operations|oncall|on-call|rollback|incident|disaster[_-]recovery)[^/]*\.(md|rst|txt|adoc)$|"
        r"(^|/)(runbooks|ops)/[^/]+\.(md|rst)$"), "S7_OPERATE", "runbook"),
    (_r(r"(^|/)[^/]*(healthcheck|health_check|healthz|hosted_parity|hosted_pages_verify|hosted_readback|"
        r"smoke[_-]?test)[^/]*$"), "S7_OPERATE", "healthcheck"),
    (_r(r"(^|/)(prometheus[^/]*\.ya?ml|alertmanager[^/]*\.ya?ml|otel[^/]*\.ya?ml|opentelemetry[^/]*\.ya?ml|"
        r"datadog[^/]*\.ya?ml)$|(^|/)grafana/[^/]+|(^|/)[^/]*red_trace[^/]*$"), "S8_MONITOR", "observability"),
    (_r(r"(^|/)[^/]*(receipt|bd_queue|red_trace|dmaic|everred|control_register|stop_model|first[_-]?red|"
        r"root[_-]?red)[^/]*\.(json|csv|ya?ml|md)$"), "S9_CONTROL", "control_ledger"),
]
KIND_STAGE = {kind: stage for _, stage, kind in RULES}
KIND_STAGE.update({"workflow": "S9_CONTROL", "test_file": "S3_TEST"})
VENDORED = _r(r"(^|/)(node_modules|vendor|third_party|third-party|\.venv|venv|site-packages|dist|build|\.git|"
              r"__pycache__|\.tox|\.mypy_cache)/")
# Archived copies (recovered snapshots, unpacked .zip.d / .tar.gz.d payloads, archive incubators) are still read
# and counted, but never feed the live-code test probes: an archived test file is not a test the repo runs.
ARCHIVED = _r(r"(^|/)(archive|archives|archived|archive_incubator|recovered|attic)/|\.(zip|tar|tgz|tar\.gz)\.d/")
# A3: a copied snapshot of another repository's files (e.g. tender_library/abacus_snapshot/) is archived too, but
# only when a PROVENANCE.csv beside it or inside it records where the copy came from; the name alone is not enough.
SNAPSHOT_DIR = _r(r"(^|/)([^/]+_snapshot)/")
FIXTURE = _r(r"(^|/)(tests?|__tests__|spec|fixtures?|testdata|test-data|examples?|samples?|__snapshots__|"
             r"benchmarks?|docs/examples)/")
SRC_EXT = {".py": "python", ".js": "js", ".mjs": "js", ".cjs": "js", ".ts": "ts", ".tsx": "ts", ".jsx": "js",
           ".go": "go", ".rs": "rust", ".ps1": "powershell", ".psm1": "powershell", ".cs": "csharp",
           ".java": "java", ".sh": "shell", ".rb": "ruby", ".php": "php", ".c": "c", ".cpp": "cpp", ".h": "c"}
TEST_PATH = {
    "python": _r(r"(^|/)test_[^/]*\.py$|_test\.py$|(^|/)tests\.py$"),
    "js": _r(r"(\.(test|spec)\.[cm]?[jt]sx?$|(^|/)__tests__/.*\.[cm]?[jt]sx?$)"),
    "go": _r(r"_test\.go$"),
    "powershell": _r(r"\.tests\.ps1$"),
    "rust": _r(r"(^|/)tests/[^/]+\.rs$"),
    "csharp": _r(r"(^|/)[^/]*tests?[^/]*/.*\.cs$"),
}
CASE_RX = {
    "js": re.compile(r"(?m)^\s*(?:it|test)(?:\.(?:each\([^)]*\)|only|concurrent|skip))?\s*\(|"
                     r"\b(?:runFormatTest|run_spec|runTest)\s*\("),
    "go": re.compile(r"(?m)^func\s+(?:Test|Benchmark|Fuzz|Example)\w*\("),
    "powershell": re.compile(r"(?mi)^\s*It\s+['\"]"),
    "rust": re.compile(r"#\[(?:tokio::)?test\]"),
    "csharp": re.compile(r"\[(?:Fact|Theory|Test|TestMethod|TestCase)\b"),
}
PY_SKIP_MODULE = _r(r"(^|/)(__init__|setup|conftest|__main__|manage)\.py$|(^|/)docs?/conf\.py$|(^|/)migrations/")
DOTTED = re.compile(r"^[A-Za-z_]\w*(\.[A-Za-z_]\w*)+$")
IDENT = re.compile(r"^[A-Za-z_]\w{2,63}$")
DYNAMIC_IMPORT = re.compile(r"spec_from_file_location|import_module|__import__|SourceFileLoader|run_path")
COMMIT_TYPE = {"fix": "fix", "bugfix": "fix", "hotfix": "fix", "repair": "fix", "feat": "feat", "feature": "feat",
               "test": "test", "tests": "test", "ci": "ci", "build": "ci", "docs": "docs", "doc": "docs",
               "refactor": "maintenance", "perf": "maintenance", "style": "maintenance", "chore": "maintenance",
               "cleanup": "maintenance", "revert": "revert", "qps": "feat", "triage": "fix", "jade": "feat",
               "tools": "maintenance", "review": "docs", "metrics": "automation", "missioncontrol": "control",
               "codepurple": "control", "code-purple": "control", "gogreen": "control", "dependabot": "deps",
               "renovate": "deps", "deps": "deps"}
# Branch or subject words that mark JADE control work (code_purple waves, first-red / root-red, gates).
CONTROL_WORDS = re.compile(r"\b(first ?red|root ?red|everred|fail ?closed|zero ?test|gate|guard|receipt|"
                           r"admission|stop ?rule|dmaic|control)\b")


# --------------------------------------------------------------------------- git layer
class Git:
    def __init__(self, gitdir: Path):
        self.dir = Path(gitdir)

    def run(self, *args, input_bytes: bytes | None = None, check=True) -> bytes:
        cmd = ["git", "--git-dir", str(self.dir), "-c", "core.quotepath=off", *args]
        p = subprocess.run(cmd, input=input_bytes, capture_output=True, timeout=900)
        if check and p.returncode != 0:
            raise RuntimeError(f"git {' '.join(args[:3])}: {p.stderr.decode(errors='replace').strip()[:300]}")
        return p.stdout

    def rev(self, ref: str) -> str | None:
        out = self.run("rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}", check=False).decode().strip()
        return out if SHA40.match(out) else None

    def commit_meta(self, sha: str) -> dict:
        h, t, d = self.run("show", "-s", "--format=%H%x00%T%x00%cI", sha).decode().strip().split("\x00")
        return {"sha": h, "tree": t, "date": d}

    def ls_tree(self, sha: str) -> list[tuple[str, str, str, str]]:
        out = self.run("ls-tree", "-r", "-z", "--full-tree", sha)
        rows = []
        for rec in out.split(b"\x00"):
            if not rec:
                continue
            meta, path = rec.split(b"\t", 1)
            mode, typ, oid = meta.decode().split(" ")
            rows.append((mode, typ, oid, path.decode("utf-8", errors="replace")))
        return rows

    def missing(self, sha: str) -> set[str]:
        out = self.run("rev-list", "--objects", "--missing=print", sha, check=False).decode()
        return {ln[1:].split()[0] for ln in out.splitlines() if ln.startswith("?")}

    def fetch_blobs(self, oids: list[str]) -> None:
        for i in range(0, len(oids), 2000):
            chunk = "\n".join(oids[i:i + 2000]) + "\n"
            self.run("-c", "fetch.negotiationAlgorithm=noop", "fetch", "-q", "--no-tags", "--no-write-fetch-head",
                     "--recurse-submodules=no", "--filter=blob:none", "--stdin", "origin",
                     input_bytes=chunk.encode(), check=False)

    def cat(self, oids: list[str]) -> dict[str, bytes]:
        if not oids:
            return {}
        out = self.run("cat-file", "--batch", input_bytes=("\n".join(oids) + "\n").encode())
        res, i = {}, 0
        while i < len(out):
            nl = out.index(b"\n", i)
            head = out[i:nl].decode().split(" ")
            if len(head) < 3 or head[1] == "missing":
                i = nl + 1
                continue
            size = int(head[2])
            res[head[0]] = out[nl + 1:nl + 1 + size]
            i = nl + 1 + size + 1
        return res

    def first_parent(self, base: str, head: str) -> list[tuple[str, str]] | None:
        p = subprocess.run(["git", "--git-dir", str(self.dir), "merge-base", "--is-ancestor", base, head],
                           capture_output=True, timeout=120)
        if p.returncode != 0:
            return None
        out = self.run("log", "--first-parent", "--format=%H%x09%s", f"{base}..{head}").decode()
        return [tuple(ln.split("\t", 1)) for ln in out.splitlines() if "\t" in ln]

    def diff_tree(self, base: str, head: str) -> Counter:
        out = self.run("diff-tree", "-r", "-z", "--no-renames", "--name-status", base, head).decode(errors="replace")
        parts = [p for p in out.split("\x00") if p]
        return Counter(parts[i][0] for i in range(0, len(parts) - 1, 2))


def cache_dir(cache: Path, repo: str) -> Path:
    return Path(cache) / (repo.replace("/", "__") + ".git")


def refresh_tags(gitdir: Path) -> bool:
    """Record the remote's tags. A failed read removes the record, so tags stay UNKNOWN instead of reading as zero."""
    out = Path(gitdir) / "jade-tags.txt"
    p = subprocess.run(["git", "--git-dir", str(gitdir), "ls-remote", "--tags", "origin"], capture_output=True,
                       timeout=300)
    if p.returncode != 0:
        out.unlink(missing_ok=True)
        return False
    out.write_text(p.stdout.decode("utf-8", errors="replace"), encoding="utf-8", newline="\n")
    return True


def fetch_repo(cache: Path, repo: str, branch: str, baseline: str | None, url: str | None = None) -> dict:
    """Clone or refresh one bare blobless cache, fetch the baseline commit and landed history."""
    url = url or f"https://github.com/{repo}.git"
    d = cache_dir(cache, repo)
    g = Git(d)
    if not d.exists():
        p = subprocess.run(["git", "clone", "-q", "--bare", "--filter=blob:none", "--depth=1", "--single-branch",
                            "-b", branch, url, str(d)], capture_output=True, timeout=900)
        if p.returncode != 0:
            return {"repo": repo, "ok": False, "error": p.stderr.decode(errors="replace").strip()[:200]}
    else:
        g.run("fetch", "-q", "--filter=blob:none", "--depth=1", "origin", f"+refs/heads/{branch}:refs/heads/{branch}")
    head = g.rev(f"refs/heads/{branch}")
    base_ok = False
    if baseline and SHA40.match(baseline):
        if baseline != head and not g.rev(baseline):
            g.run("fetch", "-q", "--filter=blob:none", "--depth=1", "origin", baseline, check=False)
        base_ok = g.rev(baseline) is not None
        if base_ok and baseline != head:
            since = datetime.fromisoformat(g.commit_meta(baseline)["date"]) - timedelta(days=1)
            g.run("fetch", "-q", "--filter=blob:none", f"--shallow-since={since.date().isoformat()}", "origin",
                  f"+refs/heads/{branch}:refs/heads/{branch}", check=False)
    refresh_tags(d)
    shas =[head] + ([baseline] if base_ok and baseline != head else [])
    want = sorted({oid for s in shas for (_m, t, oid, path) in g.ls_tree(s) if t == "blob" and wanted(path)}
                  & set().union(*(g.missing(s) for s in shas)))
    g.fetch_blobs(want)
    return {"repo": repo, "ok": True, "head": head, "baseline_fetched": base_ok, "blobs_fetched": len(want)}


# --------------------------------------------------------------------------- classification
def lang_of(path: str) -> str | None:
    return SRC_EXT.get(os.path.splitext(path)[1].lower())


def test_lang(path: str) -> str | None:
    lang = lang_of(path)
    if lang in ("ts",):
        lang = "js"
    rx = TEST_PATH.get(lang or "")
    if not rx or not rx.search(path):
        return None
    if lang == "python" and re.search(r"(^|/)(conftest|__init__)\.py$", path):
        return None
    return lang


def classify(path: str) -> list[str]:
    if VENDORED.search(path):
        return []
    if path.lower().startswith(".github/workflows/") and path.count("/") == 2 and path.lower().endswith((".yml", ".yaml")):
        return ["workflow"]
    in_fixture = bool(FIXTURE.search(path))
    kinds = []
    for rx, stage, kind in RULES:
        if rx.search(path) and kind not in kinds and (not in_fixture or stage in ("S3_TEST", "S9_CONTROL")):
            kinds.append(kind)
    return kinds


def wanted(path: str) -> bool:
    """Blobs read by the scan: classified assets, Python sources and all test files."""
    if VENDORED.search(path):
        return False
    return bool(classify(path)) or test_lang(path) is not None or (
        lang_of(path) == "python" and not FIXTURE.search(path))


# --------------------------------------------------------------------------- content analysis
def py_info(text: str) -> dict:
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")  # scanned code's own invalid escapes are not our signal
            tree = ast.parse(text)
    except (SyntaxError, ValueError):
        return {"parse_error": True, "symbols": [], "methods": 0, "tests": len(re.findall(r"(?m)^\s*(?:async\s+)?def\s+test", text)),
                "imports": set(), "strings": set(), "idents": set()}
    symbols, methods, tests = [], 0, 0
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            symbols.append(node.name)
            tests += node.name.startswith("test")
        elif isinstance(node, ast.ClassDef):
            symbols.append(node.name)
            for sub in node.body:
                if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    methods += 1
                    tests += sub.name.startswith("test")
    imports, strings, idents = set(), set(), set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
            imports.add(node.module)
            imports.update(f"{node.module}.{a.name}" for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level:
            imports.update(a.name for a in node.names)
            if node.module:
                imports.add(node.module)
        elif isinstance(node, ast.Constant) and isinstance(node.value, str) and len(node.value) < 300:
            v = node.value.strip()
            if v.endswith(".py"):
                strings.add(v.replace("\\", "/").lstrip("./"))
            elif DOTTED.match(v):
                imports.add(v)
            elif IDENT.match(v):
                idents.add(v)
    if not DYNAMIC_IMPORT.search(text):
        idents = set()
    return {"parse_error": False, "symbols": symbols, "methods": methods, "tests": tests,
            "imports": imports, "strings": strings, "idents": idents}


def count_cases(lang: str, text: str) -> int:
    if lang == "python":
        return py_info(text)["tests"]
    return len(CASE_RX[lang].findall(text)) if lang in CASE_RX else 0


def module_parts(path: str) -> tuple[str, ...]:
    parts = path[:-3].split("/")
    while parts and parts[0] in ("src", "lib", "python"):
        parts = parts[1:]
    return tuple(parts)


def map_tests(modules: dict, test_refs: dict) -> dict:
    """modules: path -> parts; test_refs: test path -> (imports, strings). Returns path -> (via, n_refs)."""
    by_suffix: dict[tuple, set] = {}
    for path, parts in modules.items():
        # The stripped parts (src/x.py -> x) and the full path (src.x), so `import src.x` maps too.
        for name in {parts, tuple(path[:-3].split("/"))}:
            for k in range(1, len(name) + 1):
                by_suffix.setdefault(name[-k:], set()).add(path)
    hits: dict[str, dict] = {p: {} for p in modules}
    for tpath, (imports, strings) in sorted(test_refs.items()):
        for name in imports:
            for p in by_suffix.get(tuple(name.split(".")), ()):
                hits[p].setdefault(tpath, "import")
        for s in strings:
            for p in by_suffix.get(module_parts(s if s.endswith(".py") else s + ".py")[-3:], ()):
                hits[p].setdefault(tpath, "path")
            stem = s.rsplit("/", 1)[-1][:-3] if s.endswith(".py") else None
            for p in by_suffix.get((stem,), ()) if stem else ():
                hits[p].setdefault(tpath, "path")
    out = {}
    for p, h in hits.items():
        vias = set(h.values())
        out[p] = ("import" if "import" in vias else "path" if vias else "none", len(h))
    return out


def toml_floor(text: str) -> float | None:
    m = re.findall(r"(?m)^\s*fail_under\s*=\s*(\d+(?:\.\d+)?)", text)
    return max(float(x) for x in m) if m else None


def healthcheck_in(text: str) -> bool:
    return bool(re.search(r"(?mi)^\s*HEALTHCHECK\s|^\s*healthcheck\s*:|livenessProbe|readinessProbe", text))


def snapshot_prefixes(paths) -> list[str]:
    """`<dir>_snapshot/` prefixes that have a PROVENANCE.csv beside the directory or inside it."""
    paths = set(paths)
    out = set()
    for path in paths:
        for m in SNAPSHOT_DIR.finditer(path):
            prefix = path[:m.end()]
            parent = prefix[:-1].rpartition("/")[0]
            if (parent + "/PROVENANCE.csv" if parent else "PROVENANCE.csv") in paths or prefix + "PROVENANCE.csv" in paths:
                out.add(prefix)
    return sorted(out)


def is_archived(sc: dict, path: str) -> bool:
    return bool(ARCHIVED.search(path)) or any(path.startswith(p) for p in sc.get("snapshot_prefixes", ()))


def scan_commit(g: Git, repo: str, sha: str, blobs: dict | None = None) -> dict:
    """Structural facts at one commit. Missing blobs are counted as unread, never guessed."""
    rows = g.ls_tree(sha)
    missing = g.missing(sha)
    need = sorted({oid for _m, t, oid, p in rows if t == "blob" and wanted(p) and oid not in missing}
                  - set(blobs or {}))
    blobs = dict(blobs or {})
    blobs.update(g.cat(need))
    name = repo.split("/")[-1]
    evidence: dict[str, list] = {k: [] for k in L.STAGE_KEYS}
    kinds = Counter()
    src = Counter()
    test_files, py_modules, test_refs, wf_recs = [], {}, {}, []
    unread = 0
    cov_cfg = []
    health = False
    pinned_req = False
    declared_version = False
    for mode, typ, oid, path in rows:
        if typ != "blob":
            if typ == "commit":
                kinds["submodule"] += 1
            continue
        low = path.lower()
        lang = lang_of(path)
        tl = test_lang(path) if not VENDORED.search(path) else None
        if lang and not tl and not VENDORED.search(path) and not FIXTURE.search(path):
            src[lang] += 1
        data = blobs.get(oid)
        if wanted(path) and data is None:
            unread += 1
        text = data.decode("utf-8", errors="replace") if data is not None and len(data) <= MAX_BLOB else None
        if tl:
            cases = count_cases(tl, text) if text is not None else None
            test_files.append([path, oid, tl, cases])
            if tl == "python" and text is not None:
                info = py_info(text)
                test_refs[path] = (info["imports"], info["strings"] | {i + ".py" for i in info["idents"]})
        elif lang == "python" and not VENDORED.search(path) and not FIXTURE.search(path) and not PY_SKIP_MODULE.search(path):
            info = py_info(text) if text is not None else None
            py_modules[path] = (oid, info)
        for kind in classify(path):
            kinds[kind] += 1
            if kind == "workflow":
                if text is not None:
                    wf_recs.append(W.analyse(W.parse(text, path=path, blob_oid=oid, repo=name)))
                continue
            stage = KIND_STAGE[kind]
            evidence[stage].append({"path": path, "blob_oid": oid, "kind": kind, "oid": f"jade:file:{name}:{path}"})
            if text is not None:
                if kind in ("build_manifest", "test_config") and low.endswith(("pyproject.toml", "setup.cfg", "tox.ini", ".coveragerc")):
                    f = toml_floor(text)
                    if f is not None:
                        cov_cfg.append(f)
                if kind in ("build_manifest", "runtime_descriptor", "deploy_descriptor") and healthcheck_in(text):
                    health = True
                if kind == "build_manifest" and re.search(r"requirements[^/]*\.txt$", low):
                    lines = [ln.strip() for ln in text.splitlines() if ln.strip() and not ln.strip().startswith(("#", "-"))]
                    pinned_req = pinned_req or (bool(lines) and all("==" in ln for ln in lines))
                if kind == "build_manifest" and re.search(r"(^|\n)\s*\"?version\"?\s*[=:]\s*[\"']\d", text) and \
                        low.endswith(("pyproject.toml", "package.json", "setup.cfg", "cargo.toml")):
                    declared_version = True
    for k in evidence:
        evidence[k].sort(key=lambda e: (e["path"].count("/"), e["path"], e["kind"]))
    mapping = map_tests({p: module_parts(p) for p in py_modules}, test_refs)
    modules = []
    for path, (oid, info) in sorted(py_modules.items()):
        via, n = mapping[path]
        modules.append([path, oid, ".".join(module_parts(path)), len(info["symbols"]) if info else None,
                        info["methods"] if info else None, via != "none", via, n,
                        info["symbols"][:30] if info else None])
    test_files.sort()
    return {"sha": sha, "rows": len(rows), "unread": unread, "evidence": evidence, "kinds": kinds, "src": src,
            "snapshot_prefixes": snapshot_prefixes(p for _m, t, _o, p in rows if t == "blob"),
            "test_files": test_files, "modules": modules, "workflows": sorted(wf_recs, key=lambda w: w["path"]),
            "coverage_config_floor": max(cov_cfg) if cov_cfg else None, "healthcheck": health,
            "pinned_requirements": pinned_req, "declared_version": declared_version, "blobs": blobs}


# --------------------------------------------------------------------------- aggregation
def wf_facts(wfs: list, cov_cfg: float | None) -> dict:
    c = Counter()
    floors = []
    for w in wfs:
        if w["parse_error"]:
            c["parse_errors"] += 1
            continue
        c["workflows"] += 1
        jobs = [j for j in w["jobs"] if "def_sha256" in j]
        c["permissions_declared"] += w["permissions"] != "default" or (
            bool(jobs) and all(j["permissions"] != "default" for j in jobs))
        c["write_all"] += w["permissions"] == "write-all" or any(j["permissions"] == "write-all" for j in jobs)
        trig = set(w["triggers"])
        ci_trig = bool(trig & {"pull_request", "push", "merge_group", "pull_request_target"})
        sched = "schedule" in trig
        c["scheduled"] += sched
        gate = bool(W.GATE_NAME_RX.search(w["name"] + " " + w["path"]))
        c["gates"] += gate
        has_deploy = False
        for j in w["jobs"]:
            s = w["sig"].get(j["id"])
            if s is None:
                continue
            c["actions_total"] += s["actions_total"]
            c["actions_pinned"] += s["actions_pinned"]
            for k in ("lint", "typecheck", "precommit", "build", "security", "provenance", "verify", "alerting"):
                c[k] += s[k]
            c["tests_ci"] += s["tests"] and (ci_trig or "workflow_call" in trig)
            c["zero_test_guard"] += s["zero_test_guard"]
            c["zero_test_guard_implicit"] += s["implicit_zero_guard"]
            c["artifact_digest"] += s["artifact_upload"] and s["digest"]
            s["scheduled_verify"] = sched and (s["verify"] or s["tests"])
            c["scheduled_verify"] += s["scheduled_verify"]
            if s["coverage"] and s["coverage_floor"] is not None:
                floors.append(s["coverage_floor"])
            if s["coverage"] and cov_cfg is not None:
                floors.append(cov_cfg)
            rel = s["release"] or "release" in trig or w["push_tags"]
            s["release_job"] = bool(rel and (s["release"] or s["build"] or s["deploy"]))
            if s["release_job"]:
                c["release"] += 1
                by_id = {x["id"]: x for x in w["jobs"] if "needs" in x}
                up = W._closure(by_id, j["id"]) if j["id"] in by_id else set()
                s["release_gated"] = any(w["sig"][u]["tests"] for u in up if u in w["sig"])
                s["release_provenance"] = s["provenance"] or s["digest"]
                c["release_gated"] += s["release_gated"]
                c["release_provenance"] += s["release_provenance"]
            if "dp" in j:
                has_deploy = True
                c["deploy"] += 1
                c["deploy_env"] += bool(j["environment"])
                s["deploy_core"] = all(j["dp"][g] == "PASS" for g in W.DP_CORE)
                s["deploy_verified"] = all(j["dp"][g] == "PASS" for g in W.DP_VERIFIED)
                s["deploy_env"] = bool(j["environment"])
                c["deploy_contract_core"] += s["deploy_core"]
                c["deploy_verified"] += s["deploy_verified"]
            if s["soft_fail_tests"] or (s["tests"] and not (s["zero_test_guard"] or s["implicit_zero_guard"])):
                c["unguarded_test_jobs"] += 1
        if has_deploy and any(W.ROLLBACK_INPUT_RX.match(i) for i in w["dispatch_inputs"]):
            c["rollback"] += 1
            for j in w["jobs"]:
                if "dp" in j:
                    w["sig"][j["id"]]["rollback"] = True
    out = {k: c.get(k, 0) for k in (
        "workflows", "parse_errors", "permissions_declared", "write_all", "scheduled", "gates", "actions_total",
        "actions_pinned", "lint", "typecheck", "precommit", "build", "security", "provenance", "verify", "alerting",
        "tests_ci", "zero_test_guard", "zero_test_guard_implicit", "artifact_digest", "scheduled_verify", "release",
        "release_gated", "release_provenance", "deploy", "deploy_env", "deploy_contract_core", "deploy_verified",
        "rollback", "unguarded_test_jobs")}
    out["coverage_floor_max"] = max(floors) if floors else None
    return out


def tests_summary(sc: dict) -> dict:
    tf = sc["test_files"]
    mods = sc["modules"]
    known = [t for t in tf if t[3] is not None]
    by_lang = Counter(t[2] for t in tf)
    return {"files": len(tf), "cases": sum(t[3] for t in known), "unread_files": len(tf) - len(known),
            "zero_case_files": sum(1 for t in known if t[3] == 0), "by_lang": dict(sorted(by_lang.items())),
            "py_modules": len(mods), "py_tested": sum(1 for m in mods if m[5]),
            "py_untested": sum(1 for m in mods if not m[5]),
            "py_tested_via": dict(sorted(Counter(m[6] for m in mods).items())),
            # Live code only: the inputs of test.fail_closed and test.controlled.
            "live_zero_case_files": sum(1 for t in known if t[3] == 0 and not is_archived(sc, t[0])),
            "live_py_modules": sum(1 for m in mods if not is_archived(sc, m[0])),
            "live_py_untested": sum(1 for m in mods if not m[5] and not is_archived(sc, m[0])),
            "archived_test_files": sum(1 for t in tf if is_archived(sc, t[0])),
            "archived_py_modules": sum(1 for m in mods if is_archived(sc, m[0])),
            "snapshot_prefixes": sc.get("snapshot_prefixes", [])}


def tag_info(cache: Path, repo: str) -> dict:
    p = cache_dir(cache, repo) / "jade-tags.txt"
    if not p.exists():
        return {"count": None, "semver": None, "latest_semver": None, "latest_semver_sha": None}
    tags = {}
    for ln in p.read_text(encoding="utf-8").splitlines():
        sha, _, ref = ln.partition("\t")
        name = ref.removeprefix("refs/tags/")
        if name.endswith("^{}"):
            tags[name[:-3]] = sha
        else:
            tags.setdefault(name, sha)
    sem = sorted((n for n in tags if re.match(r"^v?\d+\.\d+\.\d+", n)),
                 key=lambda n: [int(x) for x in re.findall(r"\d+", n)[:3]])
    return {"count": len(tags), "semver": len(sem), "latest_semver": sem[-1] if sem else None,
            "latest_semver_sha": tags[sem[-1]] if sem else None}


def http_get(url: str, timeout: float = 15.0, opener=None, token: str | None = None) -> tuple[int | None, bytes]:
    headers = {"User-Agent": "jade-devops-census/1", "Accept": "*/*"}
    if token and url.startswith("https://api.github.com/"):
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, headers=headers)
    try:
        with (opener or urllib.request.urlopen)(req, timeout=timeout) as r:
            return r.status, r.read(2_000_000)
    except urllib.error.HTTPError as e:
        return e.code, b""
    except (urllib.error.URLError, TimeoutError, OSError):
        return None, b""


def probe_pages(repo: str, head: str | None, get=http_get) -> dict:
    owner, name = repo.split("/")
    url = f"https://{owner.lower()}.github.io/{name}/"
    status, _ = get(url)
    out = {"url": url, "status": status, "served_sha": None, "source_sha_match": None, "manifest": None}
    if status == 200:
        mst, body = get(url + "site-manifest.json")
        if mst == 200:
            try:
                served = json.loads(body.decode("utf-8")).get("source_git_sha")
            except (ValueError, AttributeError):
                served = None
            if isinstance(served, str) and SHA40.match(served):
                out.update(manifest="site-manifest.json", served_sha=served, source_sha_match=served == head)
    return out


def probe_api(repo: str, branch: str, budget: list, get=http_get) -> dict:
    """Public REST reads (unauthenticated 60/h unless a token is opted in). budget = [calls left, calls made,
    refused]. A 401/403/429 stops further calls; every unanswered fact stays None (UNKNOWN)."""
    out = {"protected": None, "environments": None, "protected_production": None, "deployments": None,
           "latest_deployment_sha": None}

    def call(path):
        if budget[0] <= 0:
            return None
        budget[0] -= 1
        budget[1] += 1
        st, body = get(f"https://api.github.com/repos/{repo}{path}")
        if st == 200:
            try:
                return json.loads(body.decode("utf-8"))
            except ValueError:
                return None
        if st in (401, 403, 429):
            budget[0] = 0
            budget[2] = st
        return None

    b = call(f"/branches/{branch}")
    if isinstance(b, dict) and "protected" in b:
        out["protected"] = bool(b["protected"])
    e = call("/environments")
    if isinstance(e, dict) and "environments" in e:
        envs = e["environments"] or []
        out["environments"] = sorted(x.get("name", "") for x in envs)
        prod = [x for x in envs if re.search(r"prod|github-pages|live", x.get("name", ""), re.I)]
        out["protected_production"] = (any(x.get("protection_rules") for x in prod) if prod else False)
        if envs:
            d = call("/deployments?per_page=100")
            if isinstance(d, list):
                out["deployments"] = len(d)
                out["latest_deployment_sha"] = d[0].get("sha") if d else None
    return out


def classify_subject(subject: str) -> str:
    s = subject.strip()
    m = re.match(r"merge pull request #\d+ from [^/\s]+/(\S+)", s, re.I)
    if m:
        branch = m.group(1).lower()
        head = branch.split("/", 1)[0]
        for key in (head, re.split(r"[/_-]", branch, maxsplit=1)[0]):
            if key in COMMIT_TYPE:
                return COMMIT_TYPE[key]
        s = re.sub(r"[/_.-]+", " ", branch)  # agent-prefixed branches (claude/, codex/): classify by their words
    m = re.match(r"^([A-Za-z]+)(\([^)]*\))?!?:", s)
    if m:
        return COMMIT_TYPE.get(m.group(1).lower(), "other")
    low = s.lower()
    for rx, t in ((r"\b(fix|repair|resolve|correct|restore)", "fix"), (r"\btests?\b|coverage", "test"),
                  (r"\b(add|implement|introduce|feat|new)\b", "feat"), (r"\b(ci|workflow)\b", "ci")):
        if re.search(rx, low):
            return t
    if CONTROL_WORDS.search(low):
        return "control"
    return "other"


def red_trace_index(fed: dict | None) -> dict:
    out = {}
    for r in (fed or {}).get("repositories", []):
        hours = sorted(w["window"]["red_hours"] for w in r["non_green"]
                       if w["class"] == "RED_TO_GREEN" and (w.get("window") or {}).get("red_hours") is not None)
        mttr = None
        if hours:
            mid = len(hours) // 2
            mttr = hours[mid] if len(hours) % 2 else round((hours[mid - 1] + hours[mid]) / 2, 2)
        roots = [{"path": w["path"], "class": w["class"], "first_red_sha": (w.get("window") or {}).get("first_red_sha"),
                  "last_green_sha": (w.get("window") or {}).get("last_green_sha"), "stale": w["stale"],
                  "pinned": w["pinned"]}
                 for w in r["non_green"] if w["current"] == "RED"]
        out[r["repository"]] = {"counts": r["counts"], "currently_red": r["currently_red"],
                                "currently_red_stale": r["currently_red_stale"], "ci_mttr_hours_median": mttr,
                                "first_red_roots": roots[:12], "shared_break_roots": r.get("shared_break_roots", [])[:5],
                                "observed_at_utc": r["observed_at_utc"]}
    return out


def facts(sc: dict, wf: dict, tests: dict, tags: dict, pages: dict | None, api: dict | None, rt: dict | None) -> dict:
    kinds = sc["kinds"]
    return {"has": lambda k: kinds.get(k, 0) > 0 or (k == "healthcheck" and sc["healthcheck"]),
            "wf": wf, "tests": tests, "tags": tags, "pages": pages, "api": api, "red_trace": rt,
            "source_files": sum(sc["src"].values()), "pinned_requirements": sc["pinned_requirements"],
            "declared_version": sc["declared_version"]}


PROBE_KINDS = {
    "plan.readme_root": ("readme_root",), "plan.templates": ("issue_template", "pr_template"),
    "plan.codeowners": ("codeowners",), "plan.register": ("register",), "code.lint_config": ("lint_config",),
    "code.precommit_ci": ("precommit",), "build.manifest": ("build_manifest",), "build.lock": ("lockfile",),
    "secure.policy": ("security_policy", "dependency_bot"), "secure.depbot": ("dependency_bot",),
    "secure.provenance": ("sbom",), "release.notes": ("changelog", "release_config"),
    "deploy.descriptor": ("deploy_descriptor",), "operate.runtime": ("runtime_descriptor",),
    "operate.runbook": ("runbook",), "operate.health": ("healthcheck",), "monitor.observability": ("observability",),
    "control.ledger": ("control_ledger",),
}
PROBE_SIGNAL = {
    "code.lint_ci": "lint", "code.typecheck_ci": "typecheck", "code.precommit_ci": "precommit", "build.ci": "build",
    "build.artifact_digest": "artifact_upload", "test.ci": "tests", "test.fail_closed": "guard",
    "secure.scan_ci": "security", "secure.provenance": "provenance", "release.automation": "release_job",
    "release.gated": "release_gated", "release.provenance": "release_provenance", "deploy.workflow": "deploy",
    "deploy.environment": "deploy_env", "deploy.contract": "deploy_core", "deploy.verified": "deploy_verified",
    "operate.health": "verify", "operate.rollback": "rollback", "monitor.canary": "scheduled_verify",
    "monitor.alerting": "alerting", "control.zero_test_guard": "zero_test_guard",
}


def evidence_for(probe: str, sc: dict) -> list[str]:
    """Up to 4 descriptive OIDs (files of the probe's kinds, then jobs or workflows) behind a PASS."""
    out = []
    kinds = PROBE_KINDS.get(probe, ())
    stage = next(st for pid, st, _l, _d in L.PROBES if pid == probe)
    out += [e["oid"] for e in sc["evidence"][stage] if e["kind"] in kinds][:3]
    if probe == "test.files":
        out += [f"jade:file:{sc['name']}:{t[0]}" for t in sc["test_files"][:3]]
    sig = PROBE_SIGNAL.get(probe)
    wfs = [w for w in sc["workflows"] if not w["parse_error"]]
    if sig:
        for w in wfs:
            for j in w["jobs"]:
                s = w["sig"].get(j["id"]) or {}
                hit = (s.get("zero_test_guard") or s.get("implicit_zero_guard") or s.get("coverage_floor") is not None)                     if sig == "guard" else s.get(sig)
                if hit:
                    out.append(j["oid"])
    if probe == "control.gates":
        out += [w["oid"] for w in wfs if W.GATE_NAME_RX.search(w["name"] + " " + w["path"])]
    if probe == "monitor.schedule":
        out += [w["oid"] for w in wfs if "schedule" in w["triggers"]]
    if probe in ("secure.least_privilege", "build.pinned_actions"):
        out += [w["oid"] for w in wfs][:2]
    return list(dict.fromkeys(out))[:4]


def repo_record(row: dict, g: Git | None, cache: Path, rt_idx: dict, pages: dict | None, api: dict | None,
                fetch_info: dict | None) -> tuple[dict, dict]:
    repo, name = row["repo"], row["repo"].split("/")[-1]
    base = {"rank": row["rank"], "repo": repo, "branch": row["branch"], "lane": row["cohort_lane"], "role": row["role"],
            "oid": f"jade:repo:{repo}"}
    head = g.rev(f"refs/heads/{row['branch']}") if g else None
    if not head:
        err = (fetch_info or {}).get("error") or "UNREACHABLE"
        states = {p: L.UNKNOWN for p in L.PROBE_IDS}
        return dict(base, reachable=False, error=err, head_sha=None, tree_oid=None, stages=L.score(states),
                    probes={p: {"state": v, "evidence": []} for p, v in states.items()}),             {"head_sha": None, "py_modules": [], "test_files": []}
    meta = g.commit_meta(head)
    sc = scan_commit(g, repo, head)
    sc["name"] = name
    wf = wf_facts(sc["workflows"], sc["coverage_config_floor"])
    tests = tests_summary(sc)
    tags = tag_info(cache, repo)
    rt = rt_idx.get(repo)
    states = L.probe_states(facts(sc, wf, tests, tags, pages, api, rt))
    stages = L.score(states)
    probes = {p: {"state": s, "evidence": evidence_for(p, sc) if s == L.PASS else []}
              for p, s in states.items()}
    # Crosswalk: red-trace workflow paths -> blob OIDs at HEAD.
    wf_oid = {w["path"]: w["blob_oid"] for w in sc["workflows"]}
    rt_out = None
    if rt:
        rt_out = dict(rt, first_red_roots=[dict(x, blob_oid=wf_oid.get(x["path"])) for x in rt["first_red_roots"]])
    untested = sorted((m for m in sc["modules"] if not m[5] and not is_archived(sc, m[0])), key=lambda m: (-(m[3] or 0), m[0]))[:UNTESTED_CAP]
    known_tests = [t for t in sc["test_files"] if t[3] is not None]
    rec = dict(base, reachable=True, error=None, head_sha=head, tree_oid=meta["tree"], commit_date=meta["date"],
               blobs_unread=sc["unread"], tree_entries=sc["rows"],
               source_files=dict(sorted(sc["src"].items())),
               stages=stages, probes=probes,
               evidence={k: v[:EVIDENCE_CAP] for k, v in sc["evidence"].items()},
               evidence_counts=dict(sorted((k, v) for k, v in sc["kinds"].items())),
               workflow_facts=wf,
               workflows=[{k: v for k, v in w.items() if k != "sig"} for w in sc["workflows"]],
               tests=tests,
               zero_test={"zero_case_files": [{"path": t[0], "blob_oid": t[1], "lang": t[2]} for t in known_tests
                                              if t[3] == 0 and not is_archived(sc, t[0])][:UNTESTED_CAP],
                          "untested_modules_top": [{"path": m[0], "blob_oid": m[1], "oid": f"jade:py:{name}:{m[2]}",
                                                    "symbols": m[3], "methods": m[4], "names": (m[8] or [])[:12]}
                                                   for m in untested],
                          "unguarded_test_jobs": [j["oid"] for w in sc["workflows"] if not w["parse_error"]
                                                  for j in w["jobs"] if w["sig"].get(j["id"]) and
                                                  w["sig"][j["id"]]["tests"] and
                                                  (w["sig"][j["id"]]["soft_fail_tests"] or not (
                                                      w["sig"][j["id"]]["zero_test_guard"] or
                                                      w["sig"][j["id"]]["implicit_zero_guard"]))][:UNTESTED_CAP]},
               tags=tags, pages=pages, api=api, red_trace=rt_out)
    rec["delta"] = delta(g, repo, row.get("commit_sha_observed"), head, sc, stages, tags, pages, api, rt,
                         label=row.get("baseline_label", ROSTER_BASELINE_LABEL))
    objs = {"head_sha": head, "py_modules": [m[:8] for m in sc["modules"]], "test_files": sc["test_files"]}
    return rec, objs


def delta(g: Git, repo: str, base: str | None, head: str, sc: dict, stages: dict, tags, pages, api, rt,
          label: str = "TOP21 N11 roster head 2026-10-18 (non-atomic)") -> dict:
    out = {"baseline_sha": base, "baseline_label": label,
           "same_as_head": base == head, "reachable": False}
    if not base or not g.rev(base):
        return out
    out["reachable"] = True
    if base == head:
        out.update(commits=0, by_type={}, files={}, workflows={"A": 0, "M": 0, "D": 0},
                   tests={"files": 0, "cases": 0, "zero_case_files": 0, "py_modules": 0, "py_untested": 0},
                   stage_levels={k: 0 for k in L.STAGE_KEYS}, outcomes=_outcomes({}, {}, {}))
        return out
    landed = g.first_parent(base, head)
    by_type = Counter(classify_subject(s) for _h, s in landed) if landed is not None else None
    out["commits"] = len(landed) if landed is not None else None
    out["by_type"] = dict(sorted(by_type.items())) if by_type is not None else None
    out["files"] = dict(sorted(g.diff_tree(base, head).items()))
    bsc = scan_commit(g, repo, base, sc["blobs"])
    bw = {w["path"]: w["blob_oid"] for w in bsc["workflows"]}
    hw = {w["path"]: w["blob_oid"] for w in sc["workflows"]}
    out["workflows"] = {"A": len(hw.keys() - bw.keys()), "D": len(bw.keys() - hw.keys()),
                        "M": sum(1 for p in hw.keys() & bw.keys() if hw[p] != bw[p])}
    ht, bt = tests_summary(sc), tests_summary(bsc)
    out["tests"] = {k: ht[k] - bt[k] for k in ("files", "cases", "zero_case_files", "py_modules", "py_untested")}
    out["baseline_unread"] = bsc["unread"]
    bstates = L.probe_states(facts(bsc, wf_facts(bsc["workflows"], bsc["coverage_config_floor"]), bt, tags, pages, api, rt))
    bstages = L.score(bstates)
    out["stage_levels"] = {k: stages[k]["level"] - bstages[k]["level"] for k in L.STAGE_KEYS}
    out["outcomes"] = _outcomes(out["by_type"] or {}, out["tests"], out["workflows"])
    return out


def _outcomes(by_type: dict, tests: dict, wfs: dict) -> dict:
    """The fixed / expanded / tested / test-expansion / coverage-expansion view of one delta."""
    return {"fixed": by_type.get("fix", 0), "expanded": by_type.get("feat", 0), "tested": by_type.get("test", 0),
            "controlled": by_type.get("control", 0), "dependency_updates": by_type.get("deps", 0),
            "automation": by_type.get("automation", 0),
            "ci_changes": by_type.get("ci", 0) + wfs.get("A", 0) + wfs.get("M", 0),
            "test_files_added_net": tests.get("files", 0), "test_cases_added_net": tests.get("cases", 0),
            "untested_modules_net": tests.get("py_untested", 0), "zero_case_files_net": tests.get("zero_case_files", 0)}


# --------------------------------------------------------------------------- assembly
def canonical(d) -> bytes:
    return json.dumps(d, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def stage_contracts(hub_g: Git | None, hub_head: str | None) -> dict:
    index = {}
    if hub_g and hub_head:
        index = {p: oid for _m, t, oid, p in hub_g.ls_tree(hub_head) if t == "blob"}
    return {k: [{"path": p, "blob_oid": index.get(p), "present": p in index} for p in v] for k, v in CONTRACTS.items()}


def fleet_summary(repos: list, contracts: dict) -> dict:
    live = [r for r in repos if r["reachable"]]
    stages = {}
    for k in L.STAGE_KEYS:
        levels = [r["stages"][k]["level"] for r in live]
        hist = Counter(levels)
        present = any(c["present"] for c in contracts[k])
        stages[k] = {"levels": {str(i): hist.get(i, 0) for i in range(6)},
                     "median_level": sorted(levels)[len(levels) // 2] if levels else None,
                     "mean_completion": round(sum(r["stages"][k]["completion"] for r in live) / len(live), 4) if live else None,
                     "repos_ge_L3": sum(1 for x in levels if x >= 3), "repos_ge_L4": sum(1 for x in levels if x >= 4),
                     "contract_present": present, "formalization": L.formalization(levels, present)}
    tot = Counter()
    for r in live:
        t, w = r["tests"], r["workflow_facts"]
        for k in ("files", "cases", "zero_case_files", "py_modules", "py_tested", "py_untested", "unread_files"):
            tot["tests_" + k] += t[k]
        for k in ("workflows", "parse_errors", "deploy", "deploy_env", "deploy_contract_core", "deploy_verified",
                  "release", "scheduled", "tests_ci", "unguarded_test_jobs", "actions_total", "actions_pinned"):
            tot["wf_" + k] += w[k]
        tot["jobs"] += sum(len(x["jobs"]) for x in r["workflows"])
    outcomes = Counter()
    for r in live:
        for k, v in (r["delta"].get("outcomes") or {}).items():
            outcomes[k] += v or 0
    return {"repos": len(repos), "reachable": len(live), "stages": stages, "totals": dict(sorted(tot.items())),
            "outcomes_since_baseline": dict(sorted(outcomes.items())),
            "lanes": dict(sorted(Counter(r["lane"] for r in repos).items()))}


def scan(cache: Path, roster_path: Path, observed_at: str, probe_pages_on=True, probe_api_on=True,
         get=http_get, only: set | None = None, fetch_log: dict | None = None, api_mode="unauthenticated",
         api_budget=55, iteration: str = "N9", baseline: dict | None = None) -> tuple[dict, dict]:
    roster = json.loads(roster_path.read_text(encoding="utf-8"))
    fed_path = ROOT / RED_TRACE
    fed = json.loads(fed_path.read_text(encoding="utf-8")) if fed_path.exists() else None
    rt_idx = red_trace_index(fed)
    budget = [api_budget, 0, None]
    repos, objects = [], {}
    hub_g, hub_head = None, None
    for row in sorted(roster["repositories"], key=lambda r: r["rank"]):
        if only and row["repo"] not in only:
            continue
        if baseline:
            row = dict(row, commit_sha_observed=baseline["heads"].get(row["repo"]), baseline_label=baseline["label"])
        d = cache_dir(cache, row["repo"])
        g = Git(d) if d.exists() else None
        head = g.rev(f"refs/heads/{row['branch']}") if g else None
        pages = probe_pages(row["repo"], head, get) if (probe_pages_on and head) else None
        api = probe_api(row["repo"], row["branch"], budget, get) if (probe_api_on and head) else None
        rec, objs = repo_record(row, g, cache, rt_idx, pages, api, (fetch_log or {}).get(row["repo"]))
        repos.append(rec)
        objects[row["repo"]] = objs
        if row["repo"] == HUB and head:
            hub_g, hub_head = g, head
    contracts = stage_contracts(hub_g, hub_head)
    census = {
        "schema": SCHEMA, "iteration": iteration, "method": "JADE_CASTE / DevOps lifecycle S0..S9",
        "authority": {"merge_admission": "HOLD", "merge_authorized": False, "release_authorized": False,
                      "deploy_authorized": False, "authority_transfer": False, "security_waiver": False},
        "observed_at_utc": observed_at,
        "rules": ["UNKNOWN is never PASS; an unobservable probe caps the stage level.",
                  "Level L requires every probe of tiers 1..L to PASS (cumulative ladder).",
                  "Completion = PASS probes / probes of the stage.",
                  "blob_oid / tree_oid / head_sha are git object ids at the exact HEAD commit.",
                  "Signals are static, text- and action-based heuristics; nothing is executed.",
                  "Python module -> test mapping: AST imports, dotted strings and .py path literals in test files.",
                  "Baseline delta holds the live probes (Pages, API, red-trace) constant; only structure differs.",
                  "No merge, release or deploy authority is derived from this census."],
        "sources": {"roster": ROSTER, "red_trace": RED_TRACE if fed else None,
                    **({"baseline": {k: v for k, v in baseline.items() if k != "heads"}} if baseline else {}),
                    "api": {"mode": api_mode if probe_api_on else "off", "calls": budget[1],
                            "refused_status": budget[2]},
                    "red_trace_digest_sha256": (fed or {}).get("digest_sha256"),
                    "red_trace_observed_at_utc": (fed or {}).get("observed_at_utc")},
        "lifecycle": {"stages": [{"key": k, "title": t, "question": q, "gates": gt, "sipoc": L.SIPOC[k],
                                  "probes": [{"id": p, "level": lv, "description": ds}
                                             for p, st, lv, ds in L.PROBES if st == k],
                                  "contract": contracts[k], "oid": f"jade:stage:{k}"}
                                 for k, t, q, gt in L.STAGES],
                      "edges": [list(e) for e in L.EDGES], "layers": L.topo_layers(L.STAGE_KEYS, L.EDGES),
                      "levels": {str(k): v for k, v in L.LEVELS.items()},
                      "deploy_gates": W.DP_GATES},
        "fleet": fleet_summary(repos, contracts),
        "repos": repos,
    }
    obj = {"schema": OBJ_SCHEMA, "observed_at_utc": observed_at,
           "columns": {"py_modules": ["path", "blob_oid", "dotted", "symbols", "methods", "tested", "via", "test_refs"],
                       "test_files": ["path", "blob_oid", "lang", "cases"]},
           "repos": objects}
    census, obj = PB.project_many(census, obj)  # private repos: counts only, sealed after projection
    census["digest_sha256"] = hashlib.sha256(canonical(census)).hexdigest()
    obj = {"schema": obj.pop("schema"), "census_digest_sha256": census["digest_sha256"], **obj}
    return census, obj


# --------------------------------------------------------------------------- check
def check(census: dict, objects: dict | None = None) -> list[str]:
    errs = []
    body = {k: v for k, v in census.items() if k != "digest_sha256"}
    if hashlib.sha256(canonical(body)).hexdigest() != census.get("digest_sha256"):
        errs.append("DIGEST_DRIFT")
    if census.get("schema") != SCHEMA:
        errs.append("SCHEMA")
    a = census.get("authority", {})
    if a.get("merge_admission") != "HOLD" or any(a.get(k) is not False for k in
                                                  ("merge_authorized", "release_authorized", "deploy_authorized",
                                                   "authority_transfer")):
        errs.append("AUTHORITY_BEARING")
    if [s["key"] for s in census["lifecycle"]["stages"]] != L.STAGE_KEYS:
        errs.append("STAGE_KEYS")
    for r in census["repos"]:
        tag = r["repo"]
        if set(r["stages"]) != set(L.STAGE_KEYS):
            errs.append(f"{tag}: stages")
        if not r["reachable"]:
            if any(v["state"] != L.UNKNOWN for v in r["probes"].values()):
                errs.append(f"{tag}: unreachable repo claims a probe")
            continue
        private = PB.boundary().names_private(tag)  # private ids are PB.MARK (counts only)

        def oid(v, private=private):
            return bool(SHA40.match(v or "")) or (private and v == PB.MARK)
        for k in ("head_sha", "tree_oid"):
            if not oid(r.get(k)):
                errs.append(f"{tag}: {k}")
        for pid, p in r["probes"].items():
            if p["state"] not in L.STATES:
                errs.append(f"{tag}: {pid} state")
            if p["state"] == L.PASS and not p["evidence"] and pid not in PASS_WITHOUT_FILE:
                errs.append(f"{tag}: {pid} PASS without evidence")
        recomputed = L.score({p: v["state"] for p, v in r["probes"].items()})
        if recomputed != r["stages"]:
            errs.append(f"{tag}: stage scores do not follow from probes")
        for st, items in r["evidence"].items():
            for e in items:
                if not oid(e["blob_oid"]):
                    errs.append(f"{tag}: evidence blob_oid {e['path']}")
        for w in r["workflows"]:
            if w["blob_oid"] and not oid(w["blob_oid"]):
                errs.append(f"{tag}: workflow blob_oid {w['path']}")
        t = r["tests"]
        if t["py_tested"] + t["py_untested"] != t["py_modules"]:
            errs.append(f"{tag}: python module reconciliation")
        if objects is not None:
            o = objects["repos"].get(tag) or {}
            if o.get("head_sha") != r["head_sha"] or len(o.get("py_modules", [])) != t["py_modules"] or \
                    len(o.get("test_files", [])) != t["files"]:
                errs.append(f"{tag}: objects file drift")
    if objects is not None and objects.get("census_digest_sha256") != census.get("digest_sha256"):
        errs.append("OBJECTS_DIGEST_DRIFT")
    f = census["fleet"]
    if f["reachable"] != sum(1 for r in census["repos"] if r["reachable"]):
        errs.append("FLEET_REACHABLE")
    return errs


# Probes whose PASS is a measured value (counts, tags, HTTP, API, red-trace) rather than a file.
PASS_WITHOUT_FILE = {"code.source", "release.tags", "deploy.descriptor", "operate.runtime", "plan.protection",
                     "operate.protected_env", "monitor.live_parity", "monitor.observability", "control.red_trace",
                     "control.no_red", "test.cases", "test.controlled", "build.lock", "release.notes",
                     "secure.least_privilege", "build.pinned_actions", "operate.health"}


# --------------------------------------------------------------------------- report
def _dp_histogram(census: dict) -> tuple[int, Counter, list]:
    fails, jobs = Counter(), []
    for r in census["repos"]:
        for w in r.get("workflows", []):
            for j in w["jobs"]:
                if "dp" in j:
                    bad = sorted((g for g, v in j["dp"].items() if v != "PASS"), key=lambda g: int(g[2:]))
                    fails.update(bad)
                    jobs.append((len(bad), j["oid"], bad))
    return len(jobs), fails, sorted(jobs)


def report(census: dict, previous: dict | None = None) -> str:
    """Deterministic Markdown reading of a census (tables only; prose lives in the architecture note).

    With `previous`, a pulse-over-pulse section lists stage-level changes and probe-state flips per repository.
    """
    f, keys = census["fleet"], L.STAGE_KEYS
    api = census["sources"]["api"]
    it = census["iteration"]
    base = census["sources"].get("baseline")
    since = f"the {base['label']}" if base else "the TOP21 baseline (2026-10-18 heads)"
    out = [f"# JADE N+{it[1:]} DevOps census reading", "",
           f"Generated by `census.py report` from `data/DEVOPS_CENSUS_{it}.json`; do not hand edit.",
           f"Observed `{census['observed_at_utc']}` · digest `{census['digest_sha256'][:16]}` · "
           f"{f['reachable']}/{f['repos']} repositories reachable · API `{api['mode']}` "
           f"(refused: {api['refused_status']}) · merge admission {census['authority']['merge_admission']}.", "",
           "## Stage maturity across the fleet", "",
           "| Stage | L0 | L1 | L2 | L3 | L4 | L5 | Median | Mean completion | Hub contract | Formalization |",
           "|---|---|---|---|---|---|---|---|---|---|---|"]
    for k in keys:
        v = f["stages"][k]
        out.append(f"| {k} | " + " | ".join(str(v["levels"][str(i)]) for i in range(6)) +
                   f" | L{v['median_level']} | {round(100 * (v['mean_completion'] or 0))}% | "
                   f"{'yes' if v['contract_present'] else 'no'} | {v['formalization']} |")
    out += ["", "## Repository × stage level (L0–L5)", "",
            "| # | Repository | Lane | " + " | ".join(k.split("_")[0] for k in keys) + " | HEAD |",
            "|---|---|---|" + "---|" * len(keys) + "---|"]
    for r in census["repos"]:
        cells = " | ".join(str(r["stages"][k]["level"]) for k in keys)
        head = f"`{r['head_sha'][:10]}`" if r["head_sha"] else "UNREACHABLE"
        out.append(f"| {r['rank']} | {r['repo']} | {r['lane']} | {cells} | {head} |")
    n_dep, fails, jobs = _dp_histogram(census)
    out += ["", "## Deploy contract DP1–DP10 across every deploy job", "",
            f"{n_dep} deploy jobs. A job passes the core contract only with DP1–DP6, DP9 and DP10 all PASS.", "",
            "| Gate | Meaning | Jobs failing |", "|---|---|---|"]
    for g, text in sorted(W.DP_GATES.items(), key=lambda x: int(x[0][2:])):
        out.append(f"| {g} | {text.split(':')[0]} | {fails.get(g, 0)} |")
    out += ["", "Closest deploy jobs to the contract:", ""]
    out += [f"- `{oid}`: fails {', '.join(bad) or 'none'}" for _n, oid, bad in jobs[:6]]
    t, o = f["totals"], f["outcomes_since_baseline"]
    out += ["", "## Zero-test artefacts", "",
            "| Measure | Value |", "|---|---|",
            f"| Test files / declared cases | {t['tests_files']} / {t['tests_cases']} |",
            f"| Zero-case test files | {t['tests_zero_case_files']} |",
            f"| Python modules / with a referencing test / with none | {t['tests_py_modules']} / "
            f"{t['tests_py_tested']} / {t['tests_py_untested']} |",
            f"| CI test jobs / without a zero-test guard | {t['wf_tests_ci']} / {t['wf_unguarded_test_jobs']} |",
            f"| Third-party actions pinned to a SHA | {t['wf_actions_pinned']} / {t['wf_actions_total']} |",
            "", f"## Change since {since}", "",
            "| Outcome | Fleet total |", "|---|---|"]
    out += [f"| {k} | {v} |" for k, v in sorted(o.items())]
    out += ["", "| Repository | Landed commits | fix | feat | test | Test cases Δ | Untested modules Δ |",
            "|---|---|---|---|---|---|---|"]
    for r in census["repos"]:
        d = r.get("delta") or {}
        bt = d.get("by_type") or {}
        oc = d.get("outcomes") or {}
        out.append(f"| {r['repo'].split('/')[1]} | {d.get('commits', 'UNKNOWN')} | {bt.get('fix', 0)} | "
                   f"{bt.get('feat', 0)} | {bt.get('test', 0)} | {oc.get('test_cases_added_net', 0)} | "
                   f"{oc.get('untested_modules_net', 0)} |")
    out += ["", "## Red-trace crosswalk (first red / root red, EVERRED)", "",
            "| Repository | EVERRED | GREEN→RED | RED→GREEN | FLAKY | Red now | CI MTTR median (h) | "
            "Red roots with HEAD blob OID |", "|---|---|---|---|---|---|---|---|"]
    for r in census["repos"]:
        rt = r.get("red_trace")
        if rt:
            c = rt["counts"]
            roots = rt["first_red_roots"]
            out.append(f"| {r['repo'].split('/')[1]} | {c.get('EVERRED', 0)} | {c.get('GREEN_TO_RED', 0)} | "
                       f"{c.get('RED_TO_GREEN', 0)} | {c.get('FLAKY', 0)} | {rt['currently_red']} | "
                       f"{rt['ci_mttr_hours_median']} | {sum(1 for x in roots if x.get('blob_oid'))}/{len(roots)} |")
    out += ["", "## Probe states across reachable repositories", "", "| Probe | Level | PASS | FAIL | UNKNOWN |",
            "|---|---|---|---|---|"]
    live = [r for r in census["repos"] if r["reachable"]]
    for pid, _st, lvl, _d in L.PROBES:
        c = Counter(r["probes"][pid]["state"] for r in live)
        out.append(f"| `{pid}` | L{lvl} | {c[L.PASS]} | {c[L.FAIL]} | {c[L.UNKNOWN]} |")
    if previous is not None:
        out += pulse_section(previous, census)
    return "\n".join(out) + "\n"


def pulse_section(prev: dict, cur: dict) -> list[str]:
    """Stage-level changes and probe flips between two pulses, matched by repository."""
    keys = L.STAGE_KEYS
    pr = {r["repo"]: r for r in prev["repos"]}
    flips = Counter()
    rows = []
    for r in cur["repos"]:
        o = pr.get(r["repo"])
        if not o:
            continue
        for pid in L.PROBE_IDS:
            a, b = o["probes"][pid]["state"], r["probes"][pid]["state"]
            if a != b:
                flips[(pid, a, b)] += 1
        moves = [f"{k.split('_')[0]} {o['stages'][k]['level']}→{r['stages'][k]['level']}" for k in keys
                 if o["stages"][k]["level"] != r["stages"][k]["level"]]
        head = "same" if o.get("head_sha") == r.get("head_sha") else "moved"
        rows.append(f"| {r['repo'].split('/')[1]} | {head} | {', '.join(moves) or 'none'} |")
    po, pc = prev["fleet"]["totals"], cur["fleet"]["totals"]
    out = ["", f"## Pulse over pulse: {prev['iteration']} → {cur['iteration']}", "",
           f"Previous `{prev['observed_at_utc']}` digest `{prev['digest_sha256'][:16]}` → current "
           f"`{cur['observed_at_utc']}` digest `{cur['digest_sha256'][:16]}`.", "",
           "| Fleet measure | " + prev["iteration"] + " | " + cur["iteration"] + " |", "|---|---|---|"]
    for k in ("wf_deploy", "wf_deploy_contract_core", "wf_deploy_verified", "wf_actions_pinned", "wf_actions_total",
              "wf_unguarded_test_jobs", "tests_cases", "tests_py_untested", "tests_zero_case_files"):
        out.append(f"| {k} | {po.get(k)} | {pc.get(k)} |")
    out += ["", "| Stage | Median " + prev["iteration"] + " | Median " + cur["iteration"] + " |", "|---|---|---|"]
    out += [f"| {k} | L{prev['fleet']['stages'][k]['median_level']} | L{cur['fleet']['stages'][k]['median_level']} |"
            for k in keys]
    out += ["", "| Repository | HEAD | Stage level changes |", "|---|---|---|"] + rows
    out += ["", "| Probe | From | To | Repositories |", "|---|---|---|---|"]
    out += [f"| `{pid}` | {a} | {b} | {n} |" for (pid, a, b), n in sorted(flips.items())] or ["| none | | | |"]
    return out


# --------------------------------------------------------------------------- CLI
def write_json(path: Path, data) -> None:
    # LF on every OS: the CICD DAG pins these bytes.
    path.write_text(json.dumps(data, indent=1, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8",
                    newline="\n")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("fetch", "scan"):
        p = sub.add_parser(name)
        p.add_argument("--cache", required=True, type=Path)
        p.add_argument("--roster", type=Path, default=ROOT / ROSTER)
        p.add_argument("--only", default="", help="comma-separated owner/name subset")
    sub.choices["scan"].add_argument("--out", type=Path, default=OUT)
    sub.choices["scan"].add_argument("--objects", type=Path, default=OUT_OBJ)
    sub.choices["scan"].add_argument("--no-pages", action="store_true")
    sub.choices["scan"].add_argument("--no-api", action="store_true")
    sub.choices["scan"].add_argument("--observed-at", default=None)
    sub.choices["scan"].add_argument("--api-token-env", default=None,
                                     help="environment variable holding a read token for api.github.com (opt-in)")
    sub.choices["scan"].add_argument("--iteration", default="N9", help="pulse name written into the census")
    for name in ("fetch", "scan"):
        sub.choices[name].add_argument("--baseline-census", type=Path, default=None,
                                       help="previous pulse whose heads become the delta baseline")
    c = sub.add_parser("check")
    c.add_argument("--census", type=Path, default=OUT)
    c.add_argument("--objects", type=Path, default=OUT_OBJ)
    rp = sub.add_parser("report")
    rp.add_argument("--census", type=Path, default=OUT)
    rp.add_argument("--out", type=Path, default=OUT_MD)
    rp.add_argument("--check", action="store_true", help="fail when --out differs from the census")
    rp.add_argument("--previous", type=Path, default=None, help="previous pulse for the pulse-over-pulse section")
    a = ap.parse_args(argv)
    if a.cmd == "report":
        prev = json.loads(a.previous.read_text(encoding="utf-8")) if a.previous else None
        text = report(json.loads(a.census.read_text(encoding="utf-8")), prev)
        if a.check:
            same = a.out.exists() and a.out.read_text(encoding="utf-8").replace("\r\n", "\n") == text
            print(json.dumps({"report": a.out.name, "parity": same}))
            return 0 if same else 1
        a.out.write_text(text, encoding="utf-8", newline="\n")
        return 0
    if a.cmd == "check":
        census = json.loads(a.census.read_text(encoding="utf-8"))
        objects = json.loads(a.objects.read_text(encoding="utf-8")) if a.objects.exists() else None
        errs = check(census, objects)
        print(json.dumps({"census": str(a.census.name), "digest_sha256": census.get("digest_sha256"),
                          "repos": len(census["repos"]), "errors": errs,
                          "verdict": "PASS" if not errs else "DEVOPS_CENSUS_FIRST_RED"}, sort_keys=True))
        return 1 if errs else 0
    only = {x.strip() for x in a.only.split(",") if x.strip()}
    roster = json.loads(a.roster.read_text(encoding="utf-8"))
    a.cache.mkdir(parents=True, exist_ok=True)
    log_path = a.cache / "fetch-log.json"
    baseline = census_baseline(json.loads(a.baseline_census.read_text(encoding="utf-8"))) if a.baseline_census else None
    if a.cmd == "fetch":
        log = json.loads(log_path.read_text(encoding="utf-8")) if log_path.exists() else {}
        for row in sorted(roster["repositories"], key=lambda r: r["rank"]):
            if only and row["repo"] not in only:
                continue
            try:
                base = baseline["heads"].get(row["repo"]) if baseline else row.get("commit_sha_observed")
                info = fetch_repo(a.cache, row["repo"], row["branch"], base)
            except (RuntimeError, subprocess.TimeoutExpired) as exc:
                info = {"repo": row["repo"], "ok": False, "error": str(exc)[:200]}
            log[row["repo"]] = info
            print(json.dumps(info, sort_keys=True), flush=True)
        write_json(log_path, log)
        return 0
    observed = a.observed_at or datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    log = json.loads(log_path.read_text(encoding="utf-8")) if log_path.exists() else {}
    token = os.environ.get(a.api_token_env) if a.api_token_env else None
    get = (lambda url: http_get(url, token=token)) if token else http_get
    census, obj = scan(a.cache, a.roster, observed, not a.no_pages, not a.no_api, get=get, only=only or None,
                       fetch_log=log, api_mode="token" if token else "unauthenticated",
                       api_budget=900 if token else 55, iteration=a.iteration, baseline=baseline)
    write_json(a.out, census)
    write_json(a.objects, obj)
    errs = check(census, obj)
    print(json.dumps({"out": str(a.out), "digest_sha256": census["digest_sha256"], "reachable": census["fleet"]["reachable"],
                      "errors": errs}, sort_keys=True))
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main())
