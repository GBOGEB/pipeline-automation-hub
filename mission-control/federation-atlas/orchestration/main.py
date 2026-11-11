#!/usr/bin/env python3
"""Rebuild the existing Method Atlas with typed I/O and bounded local workers.

The canonical method/KPI/BD registries remain the inputs. Static source discovery
does not execute discovered code or qualify remote dispatch or engineering work.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import html
import importlib.util
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import tempfile
from collections import Counter

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
PROFILE = "mission-control/federation-atlas/orchestration/PIPELINE_CONTRACTS_v1.json"
SCHEMA = "missioncontrol.orchestration.atlas.v1"
MANIFEST_SCHEMA = "missioncontrol.orchestration.manifest.v1"
SHA = re.compile(r"^[0-9a-f]{40}$")
EDGE_COLORS = {"DEPENDENCY": "#4c9ad6", "ARTIFACT_HANDOFF": "#169c87",
               "FEEDBACK_NEXT_PULSE": "#d58924", "ROLE_ONLY": "#8568bf",
               "STATIC_CALL": "#64748b", "STEP_ORDER": "#4c9ad6",
               "SUPPLIES": "#4c9ad6", "CONSUMES_INPUT": "#169c87",
               "PRODUCES_OUTPUT": "#169c87", "DELIVERS_TO": "#8568bf"}
SNAPSHOT_POLICY = "MISSION_CONTROL_FILES_AND_REPOSITORY_MULTILANGUAGE_SOURCE_CONFIG_V2"
SOURCE_LANGUAGES = {".py": "python", ".js": "javascript", ".mjs": "javascript",
                    ".cjs": "javascript", ".jsx": "javascript-jsx", ".ts": "typescript",
                    ".tsx": "typescript-jsx", ".sh": "shell", ".bash": "shell",
                    ".ps1": "powershell", ".psm1": "powershell",
                    ".json": "json", ".toml": "toml", ".yaml": "yaml", ".yml": "yaml"}
CONFIG_SUFFIXES = {".json", ".toml", ".yaml", ".yml"}
REFERENCE_SCAN_BYTES = 1_048_576
REFERENCE_SCAN_LIMIT = 256
LITERAL_FILE_REFERENCE = re.compile(
    r"(?<![\w./:@-])(?:\.{1,2}/)?[A-Za-z0-9_@./-]+\."
    r"(?:py|js|mjs|cjs|jsx|ts|tsx|sh|bash|ps1|psm1|json|toml|yaml|yml)(?![\w.-])")


def canonical(value):
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode()


def digest(data):
    return hashlib.sha256(data).hexdigest()


def demand(condition, message):
    if not condition:
        raise ValueError(message)


def safe_path(root, name):
    """Only literal relative member paths; reject traversal and symlink escape."""
    demand(isinstance(name, str) and name and "\\" not in name, "invalid relative path")
    path = PurePosixPath(name)
    demand(not path.is_absolute() and ".." not in path.parts, "path escapes root")
    resolved = (Path(root) / name).resolve()
    demand(resolved.is_relative_to(Path(root).resolve()), "path escapes root")
    return resolved


def artifact_stem(identity):
    """Portable filename stem; canonical graph identity remains in the model."""
    demand(isinstance(identity, str) and bool(identity), "empty or invalid artifact identity")
    slug = re.sub(r"[^A-Za-z0-9_-]+", "-", identity).strip("-_")[:80] or "graph"
    return slug + "-" + digest(identity.encode("utf-8"))[:12]


def artifact_path(root, name):
    """Gate portable relative members before writing or accepting a bundle."""
    demand(isinstance(name, str) and bool(name), "invalid artifact member path")
    for part in name.split("/"):
        demand(part not in {"", ".", ".."}, "invalid artifact member segment")
        demand(not re.search(r'[<>:"\\|?*\x00-\x1f]', part), "nonportable artifact member")
        demand(not part.endswith((".", " ")), "nonportable artifact member suffix")
        demand(not re.match(r"(?i)^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\.|$)", part),
               "reserved artifact member basename")
    return safe_path(root, name)


def read_json(root, name):
    return json.loads(safe_path(root, name).read_text(encoding="utf-8"))


def git(root, *args):
    # Git emits UTF-8 blobs; the Windows locale codec would corrupt non-ASCII source.
    result = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True,
                            encoding="utf-8", check=False)
    return result.stdout.strip() if result.returncode == 0 else None


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    demand(spec is not None and spec.loader is not None, "module not loadable")
    result = importlib.util.module_from_spec(spec)
    sys.modules[name] = result
    spec.loader.exec_module(result)
    return result


def runtime_root(root):
    """Executing modules and recorded source identity must be the same checkout."""
    root = Path(root).resolve()
    demand(root == ROOT, "run this checkout's orchestration/main.py for the requested --root")
    return root


def layers(nodes, edges):
    """Deterministic Kahn layers for same-pulse dependencies only."""
    ids = [n["id"] for n in nodes]
    demand(len(ids) == len(set(ids)), "duplicate node identity")
    dependencies = {node: set() for node in ids}
    for edge in edges:
        demand(edge["from"] in dependencies and edge["to"] in dependencies, "dangling dependency")
        dependencies[edge["to"]].add(edge["from"])
    result, seen = [], set()
    while len(seen) < len(ids):
        ready = sorted(node for node in ids if node not in seen and dependencies[node] <= seen)
        demand(bool(ready), "same-pulse dependency cycle")
        result.append(ready)
        seen.update(ready)
    return result


def validate_artifact(root, port):
    """Validate bytes and the declared schema before downstream admission."""
    target = safe_path(root, port["path"])
    if not target.is_file():
        demand(not port.get("required", True), "missing required output: " + port["path"])
        return None
    raw = target.read_bytes()
    demand(len(raw) > 0, "empty artifact: " + port["path"])
    if port.get("sha256"):
        demand(digest(raw) == port["sha256"], "artifact digest mismatch")
    if port.get("kind") in {"json", "yaml"}:
        if port["kind"] == "yaml":
            import yaml
            try:
                value = yaml.safe_load(raw)
            except yaml.YAMLError as exc:
                raise ValueError("invalid YAML artifact: " + port["path"]) from exc
        else:
            value = json.loads(raw)
        if port.get("schema"):
            demand(isinstance(value, dict) and value.get("schema") == port["schema"],
                   "artifact schema mismatch: " + port["path"])
        for key in port.get("required_fields", []):
            demand(isinstance(value, dict) and key in value, "missing artifact field: " + key)
    elif port.get("kind") == "html":
        text = raw.decode("utf-8").lower()
        demand("<html" in text and "</html>" in text, "incomplete HTML: " + port["path"])
    else:
        raw.decode("utf-8")
    return {"path": port["path"], "bytes": len(raw), "sha256": digest(raw)}


def output_files(directory):
    """Seal every regular output member, including manifests and support files."""
    directory = Path(directory)
    demand(directory.is_dir() and not directory.is_symlink(), "output directory missing or symlinked")
    members = {}
    for path in sorted(directory.rglob("*")):
        demand(not path.is_symlink(), "symlinked output member")
        if path.is_dir():
            continue
        demand(path.is_file(), "nonregular output member")
        name = path.relative_to(directory).as_posix()
        artifact_path(directory, name)
        members[name] = digest(path.read_bytes())
    return members


def validate_profile(root, profile=None):
    profile = profile or read_json(root, PROFILE)
    demand(profile.get("schema") == "missioncontrol.orchestration.profile.v1", "profile schema")
    demand(profile.get("authority_transfer") is False and profile.get("remote_dispatch") is False,
           "profile authority violation")
    blocks = profile.get("blocks", [])
    by_id = {b["id"]: b for b in blocks}
    demand(len(by_id) == len(blocks) and blocks, "duplicate/empty block inventory")
    for filename in [*profile["inherits"].values(), *profile["sources"].values(), profile["publisher"]]:
        demand(safe_path(root, filename).is_file(), "missing canonical source: " + filename)
    for block in blocks:
        source = safe_path(root, block["source_path"])
        demand(source.is_file(), "missing functional source: " + block["id"])
        tree = ast.parse(source.read_text(encoding="utf-8"))
        functions = {n.name for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
        demand(block["entrypoint"] in functions, "unbound Python entrypoint: " + block["id"])
        for direction in ("inputs", "outputs"):
            ports = block[direction]
            demand(ports and len({p["id"] for p in ports}) == len(ports), "duplicate/empty ports")
            for port in ports:
                safe_path(root, port["path"])
                demand(port.get("kind") in {"json", "yaml", "html", "text"}, "unsupported port kind")
                demand(type(port.get("required")) is bool, "port cardinality missing")
                if direction == "inputs":
                    demand(port.get("source_scope") in {"REPOSITORY", "GENERATED", "EXTERNAL_OBSERVATION"},
                           "input source scope missing")
                    if port["source_scope"] == "REPOSITORY":
                        validate_artifact(root, port)
    graph_edges = [{"from": dep, "to": b["id"]} for b in blocks for dep in b.get("needs", [])]
    order = layers(blocks, graph_edges)
    for join in profile.get("joins", []):
        supplier, output = join["from"].split(":", 1)
        consumer, input_id = join["to"].split(":", 1)
        demand(supplier in by_id and consumer in by_id, "unknown handoff block")
        out = next((p for p in by_id[supplier]["outputs"] if p["id"] == output), None)
        inp = next((p for p in by_id[consumer]["inputs"] if p["id"] == input_id), None)
        demand(out is not None and inp is not None, "unknown handoff port")
        demand(out["kind"] == inp["kind"], "incompatible handoff type")
        demand(out.get("schema") == inp.get("schema"), "incompatible handoff schema")
        demand(not inp["required"] or out["required"], "optional producer cannot satisfy required input")
        demand(join.get("join") == "ALL", "ANY join needs a qualified alternative contract")
        demand(supplier in by_id[consumer].get("needs", []), "handoff absent from dependencies")
    return {"schema": "missioncontrol.orchestration.source_check.v1", "status": "PASS",
            "blocks": len(blocks), "joins": len(profile.get("joins", [])), "layers": order,
            "remote_dispatch": False}


def source_files(root):
    raw = git(root, "ls-files", "--cached", "--others", "--exclude-standard")
    if raw is not None:
        names = sorted(set(raw.splitlines()))
    else:
        names = sorted(p.relative_to(root).as_posix() for p in Path(root).rglob("*") if p.is_file())
    return [name for name in names if not any(p in {".git", "node_modules", "__pycache__", ".venv"}
                                            for p in PurePosixPath(name).parts)]


def source_snapshot_paths(root, profile):
    """A bounded source snapshot, not a claim of dynamically traced dependencies."""
    names = source_files(root)
    consumed = {name for name in names if name.startswith("mission-control/")
                or PurePosixPath(name).suffix.lower() in SOURCE_LANGUAGES
                or name.endswith(".mmd")}
    consumed.update(profile["inherits"].values())
    consumed.update(profile["sources"].values())
    consumed.update({PROFILE, profile["publisher"]})
    for block in profile["blocks"]:
        consumed.add(block["source_path"])
        consumed.update(port["path"] for port in block["inputs"]
                        if port.get("source_scope") == "REPOSITORY"
                        and (port.get("required", True) or safe_path(root, port["path"]).is_file()))
    return sorted(consumed)


def python_info(root, path):
    raw = safe_path(root, path).read_bytes()
    text = raw.decode("utf-8-sig")
    row = {"path": path, "sha256": digest(raw), "entrypoints": [], "functions": [],
           "static_calls": [], "parse_error": None, "evidence_class": "STATIC_SOURCE_ONLY"}
    try:
        tree = ast.parse(text)
    except SyntaxError as exc:
        row["parse_error"] = {"line": exc.lineno, "message": exc.msg}
        return row
    functions = [n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    local = {n.name for n in functions}
    row["docstring"] = (ast.get_docstring(tree) or "")[:800]
    for node in functions:
        calls = sorted({n.func.id for n in ast.walk(node) if isinstance(n, ast.Call)
                        and isinstance(n.func, ast.Name) and n.func.id in local})
        row["functions"].append({"name": node.name, "line": node.lineno,
            "end_line": node.end_lineno, "async": isinstance(node, ast.AsyncFunctionDef),
            "signature": ast.unparse(node.args), "docstring": (ast.get_docstring(node) or "")[:500],
            "calls": calls})
        row["static_calls"].extend({"from": node.name, "to": target} for target in calls)
    for node in tree.body:
        if isinstance(node, ast.If) and "__name__" in ast.unparse(node.test) and "__main__" in ast.unparse(node.test):
            row["entrypoints"] = sorted({n.func.id for n in ast.walk(node) if isinstance(n, ast.Call)
                                          and isinstance(n.func, ast.Name) and n.func.id in local})
    return row


def workflow_info(root, path):
    import yaml
    raw = safe_path(root, path).read_bytes()
    row = {"path": path, "sha256": digest(raw), "jobs": [], "errors": [], "evidence_class": "DECLARED_YAML"}
    try:
        # BaseLoader preserves `on`, boolean-looking labels and expressions as
        # strings. Discovery never evaluates YAML commands or imports source.
        data = yaml.load(raw, Loader=yaml.BaseLoader)
        demand(isinstance(data, dict) and isinstance(data.get("jobs"), dict), "workflow jobs missing")
        row.update(name=data.get("name", path), triggers=data.get("on", {}),
                   concurrency=data.get("concurrency"), permissions=data.get("permissions"))
        for job_id, spec in data["jobs"].items():
            demand(isinstance(spec, dict), "invalid job mapping")
            needs = spec.get("needs", [])
            needs = [needs] if isinstance(needs, str) else needs
            demand(isinstance(needs, list), "invalid needs")
            dynamic = [n for n in needs if "${{" in n]
            steps = []
            for index, step in enumerate(spec.get("steps", [])):
                demand(isinstance(step, dict), "invalid workflow step")
                command = step.get("run", "")
                steps.append({"id": step.get("id", "step-" + str(index + 1)), "ordinal": index + 1,
                              "name": step.get("name", step.get("uses", "Shell step " + str(index + 1))),
                              "uses": step.get("uses"), "if": step.get("if"),
                              "continue_on_error": step.get("continue-on-error"),
                              "run_sha256": digest(command.encode()) if command else None,
                              "python_targets": sorted(set(re.findall(r"[A-Za-z0-9_./-]+\.py\b", command)))})
            row["jobs"].append({"id": job_id, "label": spec.get("name", job_id), "needs": needs,
                                "unresolved_needs": dynamic, "runs_on": spec.get("runs-on"),
                                "strategy": spec.get("strategy"), "if": spec.get("if"),
                                "uses": spec.get("uses"), "concurrency": spec.get("concurrency"),
                                "steps": steps})
        edges = [{"from": dep, "to": j["id"]} for j in row["jobs"] for dep in j["needs"]
                 if dep not in j["unresolved_needs"]]
        row["layers"] = layers(row["jobs"], edges)
        row["dynamic_dependencies"] = sum(len(j["unresolved_needs"]) for j in row["jobs"])
    except (ValueError, TypeError, yaml.YAMLError) as exc:
        row["errors"].append(str(exc))
    return row


def source_assets(root, names):
    """Bounded literal-reference inspection, never a runtime/dead-code oracle.

    Comments and example strings can match; dynamic imports, aliases, extensionless
    targets and generated paths may not. Both limitations stay explicit per file.
    Every byte inspected here belongs to source_snapshot_paths' V2 population.
    """
    candidates = {name for name in names if PurePosixPath(name).suffix.lower() in SOURCE_LANGUAGES}
    registered = {}
    if PROFILE in names:
        for block in read_json(root, PROFILE).get("blocks", []):
            registered.setdefault(block["source_path"], []).append(
                {"block_id": block["id"], "entrypoint": block["entrypoint"]})
    rows = []
    base = Path(root).resolve()
    for name in sorted(candidates):
        path = PurePosixPath(name)
        raw = safe_path(root, name).read_bytes()
        role = "CONFIG_OR_DATA" if path.suffix.lower() in CONFIG_SUFFIXES else "EXECUTABLE_SOURCE_CANDIDATE"
        descriptor = None
        if name.startswith(".github/workflows/") and path.suffix.lower() in {".yml", ".yaml"}:
            role, descriptor = "WORKFLOW_DESCRIPTOR", "GITHUB_WORKFLOW"
        elif path.name in {"action.yml", "action.yaml"}:
            role, descriptor = "ACTION_DESCRIPTOR", "GITHUB_ACTION"
        elif path.name == "package.json":
            role, descriptor = "PACKAGE_DESCRIPTOR", "NPM_PACKAGE"
        elif path.name == "pyproject.toml":
            role, descriptor = "PACKAGE_DESCRIPTOR", "PYTHON_PROJECT"
        elif name.endswith(".d.ts"):
            role = "SUPPORT_DECLARATION"
        elif any(part in {"test", "tests", "__tests__"} for part in path.parts) or path.name.startswith("test_") or re.search(r"\.(test|spec)\.", path.name):
            role = "TEST_SUPPORT"
        row = {"path": name, "sha256": digest(raw), "bytes": len(raw),
               "language": SOURCE_LANGUAGES[path.suffix.lower()], "role": role,
               "descriptor": descriptor, "registered_entrypoints": registered.get(name, []),
               "references": [], "unresolved_dynamic_markers": 0,
               "runtime_reachability": "UNKNOWN", "evidence_class": "BOUNDED_STATIC_LITERAL_REFERENCES"}
        if len(raw) > REFERENCE_SCAN_BYTES:
            row["reference_scan"] = "SIZE_LIMIT_NOT_SCANNED"
        else:
            try:
                text = raw.decode("utf-8-sig")
            except UnicodeDecodeError:
                row["reference_scan"] = "NON_UTF8_NOT_SCANNED"
            else:
                if descriptor in {"GITHUB_ACTION", "NPM_PACKAGE"}:
                    import yaml
                    try:
                        if descriptor == "NPM_PACKAGE":
                            parsed = json.loads(text)
                            scripts = parsed.get("scripts", {}) if isinstance(parsed, dict) else None
                            demand(isinstance(scripts, dict), "package scripts must be a mapping")
                            row["declared_script_names"] = sorted(scripts)
                        else:
                            parsed = yaml.load(text, Loader=yaml.BaseLoader)
                            runtime = parsed.get("runs", {}).get("using") if isinstance(parsed, dict) else None
                            row["declared_action_runtime"] = runtime
                            if runtime == "composite":
                                row["descriptor"] = "GITHUB_COMPOSITE_ACTION"
                    except (ValueError, TypeError, AttributeError) as exc:
                        row["descriptor_error"] = str(exc)
                    except yaml.YAMLError as exc:
                        row["descriptor_error"] = str(exc)
                literals = sorted(set(LITERAL_FILE_REFERENCE.findall(text)))
                row["reference_scan"] = "REFERENCE_LIMIT_TRUNCATED" if len(literals) > REFERENCE_SCAN_LIMIT else "COMPLETE_WITHIN_DECLARED_METHOD"
                row["unresolved_dynamic_markers"] = len(re.findall(r"\$\{\{|\$\{|\brequire\(\s*(?![\s'\"])|\bimport\(\s*(?![\s'\"])", text))
                for literal in literals[:REFERENCE_SCAN_LIMIT]:
                    targets = set()
                    for parent in (base, (base / name).parent):
                        resolved = (parent / literal).resolve()
                        if resolved.is_relative_to(base):
                            relative = resolved.relative_to(base).as_posix()
                            if relative in candidates and relative != name:
                                targets.add(relative)
                    row["references"].append({"literal": literal, "targets": sorted(targets),
                        "resolution": "UNIQUE_LOCAL_LITERAL" if len(targets) == 1 else
                                      "AMBIGUOUS_LOCAL_LITERAL" if targets else "UNRESOLVED_OR_SELF_REFERENCE"})
        rows.append(row)
    referenced = {target for row in rows for ref in row["references"] for target in ref["targets"]}
    for row in rows:
        row["membership"] = "REGISTERED_PROCESS_SOURCE" if row["registered_entrypoints"] else (
            "STATIC_REFERENCE_CANDIDATE" if row["path"] in referenced else "UNCLASSIFIED_NO_LITERAL_REFERENCE")
    return rows


def inventory(root):
    names = source_files(root)
    python = [python_info(root, path) for path in names if path.endswith(".py")]
    workflows = [workflow_info(root, path) for path in names
                 if path.startswith(".github/workflows/") and path.endswith((".yml", ".yaml"))]
    diagrams = [{"path": path, "sha256": digest(safe_path(root, path).read_bytes()),
                 "kind": "MERMAID_SOURCE", "runtime_status": "UNKNOWN"}
                for path in names if path.endswith(".mmd")]
    assets = source_assets(root, names)
    return {"schema": "missioncontrol.orchestration.inventory.v1",
            "scope": "LOCAL_REPOSITORY_SOURCE_ONLY", "python_modules": python, "workflows": workflows,
            "diagrams": diagrams, "python_module_count": len(python), "workflow_count": len(workflows),
            "diagram_count": len(diagrams), "python_parse_errors": sum(bool(x["parse_error"]) for x in python),
            "workflow_parse_errors": sum(bool(x["errors"]) for x in workflows),
            "python_with_main": sum(bool(x["entrypoints"]) for x in python),
            "workflow_jobs": sum(len(x["jobs"]) for x in workflows),
            "workflow_steps": sum(len(j["steps"]) for x in workflows for j in x["jobs"]),
            "source_assets": assets, "source_asset_count": len(assets),
            "source_language_counts": dict(sorted(Counter(x["language"] for x in assets).items())),
            "reference_policy": {"snapshot_policy": SNAPSHOT_POLICY, "max_bytes_per_file": REFERENCE_SCAN_BYTES,
                "max_unique_literals_per_file": REFERENCE_SCAN_LIMIT,
                "interpretation": "Literal references can occur in comments or examples. Unreferenced files are unclassified, not confirmed dead. Dynamic, generated, aliased and extensionless dependencies require owner or runtime evidence."},
            "interpretation": "Static calls and YAML dependencies are source structure, not reachability, execution or remote dispatch proof."}


def graph_record(identity, label, kind, nodes, edges, source, **extra):
    ids = {n["id"] for n in nodes}
    demand(len(ids) == len(nodes), "duplicate graph node")
    demand(all(e["from"] in ids and e["to"] in ids for e in edges), "dangling graph edge")
    return {"id": identity, "label": label, "kind": kind, "nodes": nodes, "edges": edges,
            "source_path": source, "runtime_status": "UNKNOWN", **extra}


def coverage_graphs(coverage):
    nodes, edges = [], []
    def visit(node, parent=None):
        nodes.append({"id": node["id"], "label": node["label"], "kind": node["kind"],
                      "role": "viewer" if node["kind"] == "PORTFOLIO" else "source"})
        if parent is not None:
            edges.append({"from": parent, "to": node["id"], "kind": "ROLE_ONLY", "binding": "SOURCE_HIERARCHY"})
        for child in node.get("children", []):
            visit(child, node["id"])
    visit(coverage["hierarchy"])
    return [graph_record("coverage-hierarchy", "Portfolio coverage · repository, family, cohort and known modules", "COVERAGE_HIERARCHY",
                         nodes, edges, coverage["source_path"],
                         interpretation="Reported historical populations; unknown module, function, test and native identities are not invented.")]


def graphs(root, profile, inv):
    blocks = profile["blocks"]
    result = [graph_record("functional-spine", "Functional SPINE · source to output", "FUNCTIONAL_IO",
        [{"id": b["id"], "label": b["label"], "role": b["role"]} for b in blocks],
        [{"from": dep, "to": b["id"], "kind": "DEPENDENCY", "binding": "LOCAL_CONTRACT"}
         for b in blocks for dep in b["needs"]], PROFILE)]
    local_tasks = tasks(profile)
    result.append(graph_record("local-rebuild", "Local rebuild DAG · actual registered adapters", "EXECUTABLE_LOCAL",
        [{"id": t["id"], "label": t["label"]} for t in local_tasks],
        [{"from": dep, "to": t["id"], "kind": "DEPENDENCY", "binding": "LOCAL_CONTRACT"}
         for t in local_tasks for dep in t["needs"]], PROFILE))
    join_nodes = {}
    for join in profile.get("joins", []):
        for endpoint in (join["from"], join["to"]):
            block_id, port_id = endpoint.split(":", 1)
            join_nodes[endpoint] = {"id": endpoint, "label": block_id + " · " + port_id}
    result.append(graph_record("typed-artifact-handoffs", "Typed I/O joins · actual output-to-input contracts", "ARTIFACT_HANDOFFS",
        list(join_nodes.values()), [{"from": j["from"], "to": j["to"], "kind": "ARTIFACT_HANDOFF",
                                    "binding": "LOCAL_CONTRACT", "join": j["join"]} for j in profile.get("joins", [])], PROFILE))
    control_nodes = [{"id": identity, "label": label, "role": role} for identity, label, role in [
        ("trigger", "Explicit local launch", "source"), ("inputs", "Validate source and DAG", "source"),
        ("ready", "Bounded ready queue", "source"), ("defer", "Defer admission until slot", "neutral"),
        ("leases", "Check worker slot and path leases", "source"), ("execute", "Execute registered handler", "source"),
        ("verify", "Verify required output bytes", "source"), ("success", "Release successor dependencies", "source"),
        ("failed", "Record failure and block descendants", "blocked"), ("receipt", "Local receipt and metrics", "viewer")]]
    control_edges = [("trigger", "inputs"), ("inputs", "ready"), ("ready", "leases"),
                     ("ready", "defer"), ("leases", "execute"), ("execute", "verify"),
                     ("inputs", "failed"), ("execute", "failed"), ("verify", "failed"),
                     ("verify", "success"), ("success", "receipt"), ("failed", "receipt")]
    result.append(graph_record("broker-control", "Broker admission and dispatch · bounded local execution", "BROKER_CONTROL",
        control_nodes, [{"from": a, "to": b, "kind": "DEPENDENCY", "binding": "LOCAL_CONTRACT"} for a, b in control_edges],
        "mission-control/federation-atlas/orchestration/broker.py",
        interpretation="Deferred tasks are reconsidered on subsequent scheduler passes after slots release. This static DAG unrolls that control loop and does not imply remote dispatch."))
    import yaml
    fed = yaml.safe_load(safe_path(root, profile["sources"]["federation"]).read_text(encoding="utf-8"))
    result.append(graph_record("federation", "Canonical federation · owners and evidence", "FEDERATION",
        fed["nodes"], [{**e, "kind": e["type"].upper()} for e in fed["edges"]], profile["sources"]["federation"]))
    beams = read_json(root, profile["sources"]["beams"])
    nodes = [{"id": b["id"], "label": b["title"]} for b in beams["beams"]]
    edges = []
    for edge in beams["edges"]:
        e = {**edge, "kind": edge["type"], "binding": "DECLARED"}
        if e["kind"] == "FEEDBACK":
            next_id = e["to"] + "@NEXT_PULSE"
            if not any(n["id"] == next_id for n in nodes):
                nodes.append({"id": next_id, "label": e["to"] + " · next pulse"})
            e.update(to=next_id, kind="FEEDBACK_NEXT_PULSE")
        edges.append(e)
    result.append(graph_record("canonical-beams", "CODE PURPLE beams · feedback unrolled to N+1", "BEAMS", nodes, edges, profile["sources"]["beams"]))
    lane_source = read_json(root, profile["sources"]["lanes"])
    for lane in lane_source["lanes"]:
        nodes = [{"id": lane["id"] + ":" + s[0], "label": s[1], "inputs": s[2], "outputs": s[3]} for s in lane["stages"]]
        edges = [{"from": a["id"], "to": b["id"], "kind": "STEP_ORDER", "binding": "DECLARED"} for a, b in zip(nodes, nodes[1:])]
        result.append(graph_record("lane-" + lane["id"].lower(), lane["label"], "METHOD_LANE", nodes, edges,
                                   profile["sources"]["lanes"], parent_id="functional-spine"))
    for block in blocks:
        # A local SIPOC row is derived from the very same functional ports.
        nodes = [{"id": "S", "label": block.get("repo", profile["repository"])},
                 {"id": "I", "label": "Input ports: " + ", ".join(p["id"] for p in block["inputs"])},
                 {"id": "P", "label": block["label"]},
                 {"id": "O", "label": "Output ports: " + ", ".join(p["id"] for p in block["outputs"])},
                 {"id": "C", "label": "Consumers: " + (", ".join(b["id"] for b in blocks if block["id"] in b["needs"]) or "Owner / analyst")}]
        result.append(graph_record("sipoc-" + block["id"], "SIPOC · " + block["label"], "SIPOC", nodes,
             [{"from": a, "to": b, "kind": kind, "binding": "LOCAL_CONTRACT"}
              for a, b, kind in [("S", "I", "SUPPLIES"), ("I", "P", "CONSUMES_INPUT"),
                                 ("P", "O", "PRODUCES_OUTPUT"), ("O", "C", "DELIVERS_TO")]],
             block["source_path"], parent_id="functional-spine"))
    stitch = read_json(root, profile["sources"]["superstitch"])
    result.append(graph_record("superstitch", "Superstitch · complete source relationship graph", "RELATIONSHIP",
                              stitch["nodes"], stitch["edges"], profile["sources"]["superstitch"]))
    for group in read_json(root, profile["sources"]["groups"])["groups"]:
        ids = set(group["nodes"])
        result.append(graph_record("group-" + group["id"], group["label"], "BOUNDED_GROUP",
            [n for n in stitch["nodes"] if n["id"] in ids],
            [e for e in stitch["edges"] if e["from"] in ids and e["to"] in ids],
            profile["sources"]["groups"], parent_id="superstitch",
            boundary_edges=[e for e in stitch["edges"] if (e["from"] in ids) != (e["to"] in ids)]))
    queue = read_json(root, profile["sources"]["queue"])
    result.append(graph_record("cpq-dependencies", "CPQ work-item dependency graph", "WORK_QUEUE",
        [{"id": i["id"], "label": i["id"] + " · " + i["title"], "status": i["history"][-1]["state"]} for i in queue["items"]],
        [{"from": dep, "to": i["id"], "kind": "DEPENDENCY", "binding": "DECLARED"} for i in queue["items"] for dep in i["depends_on"]],
        profile["sources"]["queue"]))
    for workflow in inv["workflows"]:
        if workflow["errors"]:
            continue
        identity = "workflow-" + digest(workflow["path"].encode())[:12]
        result.append(graph_record(identity, workflow["name"], "WORKFLOW_JOBS", workflow["jobs"],
            [{"from": dep, "to": j["id"], "kind": "DEPENDENCY", "binding": "DECLARED_YAML"}
             for j in workflow["jobs"] for dep in j["needs"] if dep not in j["unresolved_needs"]], workflow["path"],
            dynamic_dependencies=workflow["dynamic_dependencies"]))
        if workflow["path"] == profile["publisher"]:
            for job in workflow["jobs"]:
                nodes = [{"id": job["id"] + ":" + str(s["ordinal"]), "label": s["name"], **s}
                         for s in job["steps"]]
                # Step IDs are scoped by job and ordinal, never a reused user label.
                for n in nodes:
                    n["id"] = job["id"] + ":" + str(n["ordinal"])
                result.append(graph_record(identity + "-" + job["id"], "Atlas workflow steps · " + job["id"], "WORKFLOW_STEPS", nodes,
                    [{"from": a["id"], "to": b["id"], "kind": "STEP_ORDER", "binding": "DECLARED_YAML"} for a, b in zip(nodes, nodes[1:])],
                    workflow["path"], parent_id=identity,
                    interpretation="Source step order; if/continue-on-error remain in inventory. A previous step is not necessarily a success prerequisite."))
    own = next((p for p in inv["python_modules"] if p["path"] == "mission-control/federation-atlas/orchestration/main.py"), None)
    if own:
        result.append(graph_record("python-main", "Python main.py · static call structure", "STATIC_CALLS",
            [{"id": f["name"], "label": f["name"]} for f in own["functions"]],
            [{**e, "kind": "STATIC_CALL", "binding": "STATIC_SOURCE"} for e in own["static_calls"]], own["path"]))
    return result


def graph_mermaid(graph):
    aliases = {n["id"]: "n" + str(i) for i, n in enumerate(graph["nodes"])}
    lines = ["flowchart TD", "%% " + graph["label"].replace("\n", " ")]
    for node in graph["nodes"]:
        label = str(node.get("label", node["id"])).replace('"', "'").replace("\n", " ").replace("<", "(").replace(">", ")")
        lines.append('  ' + aliases[node["id"]] + '["' + label + ' · ' + graph_role(node) + '"]')
    for edge in graph["edges"]:
        arrow = " --> " if edge.get("binding") in {"LOCAL_CONTRACT", "RECEIPT", "NATIVE_RECEIPT"} else " -.-> "
        lines.append("  " + aliases[edge["from"]] + arrow + aliases[edge["to"]])
    for role, colors in graph_palette("light")["roles"].items():
        lines.append(f"  classDef {role} fill:{colors[0]},stroke:{colors[1]},color:{colors[2]},stroke-width:2px")
        members = [aliases[n["id"]] for n in graph["nodes"] if graph_role(n) == role]
        if members:
            lines.append("  class " + ",".join(members) + " " + role)
    for index, edge in enumerate(graph["edges"]):
        lines.append(f"  linkStyle {index} stroke:{EDGE_COLORS.get(edge.get('kind'), '#8568bf')},stroke-width:2px")
    return "\n".join(lines) + "\n"


def graph_role(node):
    """Programme hue never supplies a success or qualification claim."""
    state = str(node.get("status", node.get("state", ""))).upper()
    role = str(node.get("role", node.get("class", ""))).lower()
    if state in {"BLOCKED", "FAILED", "HOLD", "RETURN_OWNER"} or role in {"blocked", "hold"}:
        return "blocked"
    if node.get("native_qualified") is True:
        return "qualified"
    if state in {"WAITING", "PENDING", "QUEUED", "DEFERRED", "UNKNOWN_NEEDS_READER"}:
        return "waiting"
    if role in {"viewer", "packager", "semantic", "control"}:
        return "viewer"
    if role in {"neutral", "actor"}:
        return "neutral"
    return "source"


def graph_palette(theme):
    demand(theme in {"light", "dark"}, "unknown graph theme")
    if theme == "dark":
        return {"background": "#101824", "text": "#e7eef8", "muted": "#b0bdd0",
                "roles": {"source": ("#172f48", "#73b5ee", "#d9ecff"),
                          "qualified": ("#153729", "#64d294", "#ddf5e6"),
                          "waiting": ("#3a2f13", "#efbd57", "#fff0c5"),
                          "blocked": ("#442029", "#f28b99", "#fbe1e4"),
                          "viewer": ("#30213f", "#c49af4", "#edddff"),
                          "neutral": ("#25303e", "#a7b3c4", "#e8edf4")}}
    return {"background": "#f6f8fc", "text": "#16324a", "muted": "#475569",
            "roles": {"source": ("#dbecff", "#3268a8", "#153d70"),
                      "qualified": ("#ddf5e6", "#247a49", "#17502f"),
                      "waiting": ("#fff0c5", "#a97718", "#694a08"),
                      "blocked": ("#fbe1e4", "#c23b49", "#802330"),
                      "viewer": ("#efe5fe", "#8150b4", "#532c80"),
                      "neutral": ("#e8edf4", "#6a7a90", "#344459")}}


def graph_svg(graph, theme="light"):
    palette = graph_palette(theme)
    nodes = graph["nodes"]
    try:
        rows = layers(nodes, graph["edges"])
    except ValueError:
        rows = [[n["id"] for n in nodes[i:i + 4]] for i in range(0, len(nodes), 4)]
    rows = [row[i:i + 4] for row in rows for i in range(0, len(row), 4)]
    positions = {node: (30 + index * 260, 120 + row_index * 110)
                 for row_index, row in enumerate(rows) for index, node in enumerate(row)}
    width, height = 1080, max(260, 200 + len(rows) * 110)
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" role="img">',
             '<title>' + html.escape(graph["label"]) + '</title>',
             '<metadata>canonical Mermaid SHA-256: ' + digest(graph_mermaid(graph).encode()) + '; theme: ' + theme + '</metadata>',
             f'<rect width="100%" height="100%" fill="{palette["background"]}"/>',
             '<defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="6" refY="4" orient="auto"><path d="M0 0L8 4L0 8Z" fill="#64748b"/></marker></defs>',
             f'<text x="30" y="33" font-family="system-ui" font-size="21" fill="{palette["text"]}">' + html.escape(graph["label"][:90]) + '</text>',
             f'<text x="30" y="59" font-family="system-ui" font-size="12" fill="{palette["muted"]}">Node roles: blue source · green qualified · amber waiting · red blocked · purple viewer · gray neutral</text>',
             f'<text x="30" y="78" font-family="system-ui" font-size="12" fill="{palette["muted"]}">Edges: blue dependency · teal I/O · amber next-pulse feedback · gray static · purple actor relationship</text>',
             f'<text x="30" y="97" font-family="system-ui" font-size="12" fill="{palette["muted"]}">Solid: local contract or receipt · dashed: declared/static · source structure does not prove runtime</text>']
    for edge in graph["edges"]:
        x, y = positions[edge["from"]]
        a, b = positions[edge["to"]]
        color = EDGE_COLORS.get(edge.get("kind"), "#8568bf")
        dash = '' if edge.get("binding") in {"LOCAL_CONTRACT", "RECEIPT", "NATIVE_RECEIPT"} else ' stroke-dasharray="6 4"'
        parts.append(f'<path d="M{x+115} {y+76} C{x+115} {y+91} {a+115} {b-25} {a+115} {b}" fill="none" stroke="{color}" stroke-width="1.8"{dash} marker-end="url(#arrow)"><title>' + html.escape(edge.get("kind", "relationship")) + '</title></path>')
    for node in nodes:
        x, y = positions[node["id"]]
        label = str(node.get("label", node["id"]))
        role = graph_role(node)
        fill, stroke, text = palette["roles"][role]
        parts.append(f'<g><title>{html.escape(label)} · {role}</title><rect x="{x}" y="{y}" width="230" height="76" rx="10" fill="{fill}" stroke="{stroke}" stroke-width="2"/>')
        for index, line in enumerate([label[:31], label[31:62], role.upper()]):
            if line:
                parts.append(f'<text x="{x+12}" y="{y+22+index*19}" font-family="system-ui" font-size="12" fill="{text}">{html.escape(line)}</text>')
        parts.append('</g>')
    return "\n".join(parts) + "\n</svg>\n"


def burndown(root, profile):
    q = read_json(root, profile["sources"]["queue"])
    series = read_json(root, profile["sources"]["series"])
    complete = {"DONE", "CONTROL", "SUPERSEDED", "INVALIDATED"}
    items = [{**i, **i["history"][-1], "canonical_id": q["schema"] + "::" + i["id"]} for i in q["items"]]
    count = Counter(i["state"] for i in items)
    cpq = {"id": "CPQ_CANONICAL", "label": "CODE PURPLE · canonical work ledger", "programmes": ["CODE_PURPLE", "EVERRED"],
           "source_path": profile["sources"]["queue"], "eligible": len(items),
           "done": sum(count[s] for s in complete), "open": sum(count[s] for s in q["open_states"]),
           "blocked": sum(i["flow"] in {"BLOCKED", "HOLD", "RETURN_OWNER"} for i in items),
           "unknown": count["UNKNOWN_NEEDS_READER"], "unit": "ledger items", "items": items,
           "evidence_class": "SOURCE_LEDGER_HISTORICAL_DISPOSITIONS", "states": dict(count),
           "note": "Terminal dispositions include superseded/invalidated records. They are not a count of accepted causal-root closures.",
           "series": []}
    previous = None
    for entry in series["entries"]:
        m = entry["metrics"]
        identity_fields = ("cohort_hash", "metric_config_hash", "unit", "metric")
        identity = (*tuple(entry.get(k) for k in identity_fields), m.get("bd_total"))
        numerator, denominator = m.get("bd_complete"), m.get("bd_total")
        qualified = (all(v is not None for v in identity)
                     and type(numerator) is int and type(denominator) is int
                     and 0 <= numerator <= denominator and denominator > 0)
        cpq["series"].append({"label": entry["key"], "x": len(cpq["series"]),
            "value": m.get("bd_complete") if m.get("bd_total") is not None else None,
            "eligible": m.get("bd_total"), "comparable": bool(qualified and previous == identity),
            "scope": "CPQ_CANONICAL", "evidence_class": entry.get("evidence_class", "SOURCE_LEDGER"),
            "source_sha": entry.get("tree"), "comparability_reason": "requires observed counts and equal cohort/config/unit/metric/denominator identities"})
        previous = identity if qualified else None
    jade = read_json(root, profile["sources"]["jade"])
    jm = jade["metrics"]
    j = {"id": "JADE_N11_OWNER_ACTIONS", "label": "JADE · N11 Top21 owner actions", "programmes": ["JADE_TEMPLE", "JADE_CASTE"],
         "source_path": profile["sources"]["jade"], "eligible": jm["owner_actions_open"] + jm["owner_actions_closed"],
         "done": jm["owner_actions_closed"], "open": jm["owner_actions_open"], "blocked": None, "unknown": None,
         "evidence_class": jade["evidence_level"], "unit": "owner actions", "items": [],
         "series": [{"label": p["id"], "x": i, "value": p["metrics"].get("accepted_owner_actions"),
                     "eligible": p["eligible_denominator"], "scope": p["scope"], "comparable": False,
                     "cohort_sha": p["cohort_sha"], "evidence_class": p["qualification"]}
                    for i, p in enumerate(jade["pulses"])],
         "note": "Frozen JADE cohort; native success is separate from owner-action acceptance. Cohort hashes and source changes remain explicit."}
    observed = read_json(root, profile["sources"]["superstitch"])["observations"]
    cohorts = [cpq, j]
    for identity, label, key in [("HISTORICAL_BREADTH", "Historical federation evidence breadth", "historical_six_repo_breadth"),
                                 ("AUTHENTICATED_PAIR", "CODEX to QPS authenticated pairs", "authenticated_codex_qps_pairs")]:
        item = observed[key]
        cohorts.append({"id": identity, "label": label, "source_path": profile["sources"]["superstitch"],
            "eligible": item["eligible"], "done": item["observed"], "open": None, "blocked": None,
            "unknown": None, "unit": "evidence cells" if identity == "HISTORICAL_BREADTH" else "pairs",
            "evidence_class": item["evidence_class"], "items": [], "series": [],
            "note": "Independent measurement population; never added to work items or current runtime."})
    return {"schema": "missioncontrol.orchestration.burndown.v1", "cohorts": cohorts,
            "global_completion_pct": None, "accepted_root_closure_delta": None,
            "rule": "No global percentage across distinct units, cohorts or histories. Unknown values remain null."}


def tasks(profile):
    """Only these local generator adapters are executable by this entrypoint."""
    specs = [("validate", "Source contract check", [], "source-contracts"),
             ("method", "Existing Method Atlas", ["validate"], "method-atlas"),
             ("control", "Existing burndown", ["validate"], "burndown"),
             ("superstitch", "Existing Superstitch", ["validate"], "superstitch"),
             ("convergence", "Existing convergence hub", ["validate"], "convergence"),
             ("orchestration", "Execution Atlas", ["validate"], "orchestration-view"),
             ("assemble", "Join verified output members", ["method", "control", "superstitch", "convergence", "orchestration"], None),
             ("portal", "Existing Pages packager", ["assemble"], "pages-portal")]
    blocks = {b["id"]: b for b in profile["blocks"]}
    result = []
    for identity, label, needs, block in specs:
        inputs = ([blocks[block]["source_path"], PROFILE]
                  + [p["path"] for p in blocks[block]["inputs"]
                     if p.get("source_scope") == "REPOSITORY" and p.get("required", True)]) if block else []
        reads = sorted(set(inputs + ["build/" + predecessor for predecessor in needs]))
        result.append({"id": identity, "label": label, "needs": needs, "repo": profile["repository"], "block_id": block,
                       "read_paths": reads, "write_paths": ["build/" + identity], "estimated_seconds": None,
                       "input_contract": {"required_paths": sorted(set(inputs))},
                       "output_contract": {"required_result_keys": ["status"]}})
    return result


def source_model(root, head, snapshot=None):
    root = runtime_root(root)
    profile_bytes = safe_path(root, PROFILE).read_bytes()
    profile = json.loads(profile_bytes)
    source_hashes = {p: digest(safe_path(root, p).read_bytes()) for p in source_snapshot_paths(root, profile)}
    demand(source_hashes[PROFILE] == digest(profile_bytes), "profile changed during source snapshot")
    checked = validate_profile(root, profile)
    actual = git(root, "rev-parse", "HEAD")
    demand(SHA.fullmatch(head or "") is not None, "exact head required")
    demand(actual is None or actual == head, "checkout/head mismatch")
    inv = inventory(root)
    tax = read_json(root, profile["inherits"]["programmes"])
    by_path = {m["path"]: m for m in inv["python_modules"]}
    blocks = []
    for block in profile["blocks"]:
        info = by_path[block["source_path"]]
        entry = next(f for f in info["functions"] if f["name"] == block["entrypoint"])
        blocks.append({**block, "repo": profile["repository"], "status": "SOURCE_BOUND_LOCAL_CONTRACT",
                       "source_url": f'https://github.com/{profile["repository"]}/blob/{head}/{block["source_path"]}',
                       "attributes": entry, "source_sha256": info["sha256"]})
    policy = read_json(root, "mission-control/federation-atlas/orchestration/BROKER_POLICY_v1.json")
    policy["cohort"] = {"repo": profile["repository"], "source_sha": head}
    broker = module("atlas_local_broker", HERE / "broker.py")
    planned = broker.plan(tasks(profile), snapshot, policy)
    if snapshot is None:
        planned["generated_at"] = None
        planned["time_basis"] = "DETERMINISTIC_SOURCE_PLAN_NO_RUNTIME_OBSERVATION"
    planned["source_path"] = "mission-control/federation-atlas/orchestration/BROKER_POLICY_v1.json"
    source = {"repository": profile["repository"], "head_sha": head, "checkout_sha": actual,
              "observed_at": None, "commit_at": git(root, "show", "-s", "--format=%cI", "HEAD"),
              "evidence_class": "LOCAL_SOURCE_INVENTORY_NOT_RUNTIME", "dirty": bool(git(root, "status", "--porcelain")),
              "inventory_policy": SNAPSHOT_POLICY,
              "inventory_interpretation": "Source snapshot includes all Mission Control inputs/assets, repository Python/JavaScript/TypeScript/shell/PowerShell, JSON/TOML/YAML descriptors and Mermaid files. Bounded literal references are not runtime dependency tracing.",
              "source_files_sha256": source_hashes, "source_digest": digest(canonical(source_hashes))}
    coverage_module = module("atlas_coverage_contract", HERE / "coverage_contract.py")
    coverage = coverage_module.build_model(root, profile)
    coverage_events = read_json(root, coverage["source_path"])["events"]
    baselines = []
    for revision in ("HEAD", "HEAD^"):
        previous = git(root, "show", revision + ":" + coverage["source_path"])
        if previous is not None:
            coverage_module.validate_append_only(json.loads(previous)["events"], coverage_events)
            baselines.append(revision)
    coverage["history_validation"] = {"checked_available_git_revisions": baselines,
        "status": "ORDERED_PREFIX_VERIFIED" if baselines else "NEW_SOURCE_NO_PRIOR_REGISTRY_AVAILABLE",
        "scope": "Available local Git history; not a cross-provider persistent database guarantee"}
    model = {"schema": SCHEMA, "title": profile["title"], "source": source,
             "taxonomy": {"programmes": tax.get("PROGRAMMES", {}).get("records", []), "hierarchy": profile["hierarchy"],
                          "glossary": read_json(root, profile["inherits"]["views"]), "inherited": profile["inherits"]},
             "blocks": blocks, "graphs": graphs(root, profile, inv) + coverage_graphs(coverage), "burndown": burndown(root, profile),
             "broker": planned, "coverage": coverage, "inventory": inv, "source_check": checked,
             "io_rules": profile["io_rules"], "joins": profile["joins"],
             "authority_transfer": False, "remote_dispatch": False, "merge_admission": "HOLD",
             "build": {"source_path": "mission-control/federation-atlas/orchestration/main.py", "commands": [
                 {"label": "Check source", "command": "python mission-control/federation-atlas/orchestration/main.py check --root ."},
                 {"label": "Build this view", "command": "python mission-control/federation-atlas/orchestration/main.py build --out ../atlas-review/orchestration --head <exact-checkout-sha>"},
                 {"label": "Rebuild registered views", "command": "python mission-control/federation-atlas/orchestration/main.py run-local --out ../atlas-review --head <exact-checkout-sha> --workers 2"}],
                 "outputs": [{"path": p, "purpose": purpose} for p, purpose in [
                     ("atlas.json", "Shared functional and graph model"), ("inventory.json", "Multi-language source/config locators and bounded static reference candidates"),
                     ("burndown.json", "Independent cohort ledger projections"), ("broker-plan.json", "Bounded scheduling projection"),
                     ("metric_observations.json", "Coverage identity, distributions and qualification"),
                     ("coverage_burndown.jsonl", "Immutable source-event ledger projection; independent populations"),
                     ("graphs/", "Rebuilt Mermaid and SVG for each normalized graph"), ("manifest.json", "Exact member hashes and source identity")]]}}
    for graph in model["graphs"]:
        for node in graph["nodes"]:
            node["visual_role"] = graph_role(node)
    return model


def observed_execution_peak(intervals):
    """Lower bound on simultaneous execution implied by (start, finish) pairs.

    End sorts before start at ties, so adjacent tasks do not overlap. Any
    executed task needed one slot. Coarse clocks (about 15.6 ms on Windows)
    record short tasks as zero-length: equal instants stay ambiguous, but a
    zero-length task strictly inside another task's open interval did overlap
    it. The broker's own counter can include short postterminal cleanup, so
    its reported peak may exceed this bound.
    """
    active, peak = 0, int(bool(intervals))
    for _, delta in sorted((point, delta) for start, finish in intervals if start < finish
                           for point, delta in ((start, 1), (finish, -1))):
        active += delta
        peak = max(peak, active)
    for instant, finish in intervals:
        if instant == finish:
            peak = max(peak, 1 + sum(start < instant < end for start, end in intervals))
    return peak


def validate_local_timeline(receipt, task_defs):
    """Reject a plausible-looking terminal summary without a causal local trace."""
    elapsed = receipt["metrics"]["elapsed_seconds"]
    rows = receipt["tasks"]
    timestamps = ("ready_at_seconds", "started_at_seconds", "execution_finished_at_seconds",
                  "verify_started_at_seconds", "finished_at_seconds")
    transitions = {None: {"ready", "deferred_ready", "blocked"}, "deferred_ready": {"ready"},
                   "ready": {"reserved"}, "reserved": {"running"},
                   "running": {"verifying", "failed"}, "verifying": {"succeeded", "failed"},
                   "succeeded": set(), "failed": set(), "blocked": set()}

    def close(left, right):
        return math.isclose(left, right, rel_tol=1e-9, abs_tol=1e-9)

    for row in rows.values():
        for field in timestamps:
            value = row.get(field)
            demand(value is None or (type(value) in {int, float} and math.isfinite(value)
                   and 0 <= value <= elapsed), "invalid local task timestamp: " + field)
        demand(row.get("finished_at_seconds") is not None, "terminal local task timestamp missing")
    for identity, row in rows.items():
        finished = row["finished_at_seconds"]
        events = row.get("events")
        demand(isinstance(events, list) and events, "local task events missing")
        previous_state, previous_time = None, 0.0
        event_times = {}
        for event in events:
            demand(isinstance(event, dict), "invalid local event")
            state, at = event.get("state"), event.get("at_seconds")
            demand(isinstance(state, str) and state in transitions.get(previous_state, set()), "invalid local event transition")
            demand(type(at) in {int, float} and math.isfinite(at)
                   and previous_time <= at <= elapsed, "nonmonotone local events")
            event_times[state] = at
            previous_state, previous_time = state, at
        demand(previous_state == row["state"] and close(previous_time, finished), "local terminal event mismatch")
        parents = [rows[parent] for parent in task_defs[identity]["needs"]]
        if row["state"] == "blocked":
            demand(len(events) == 1 and all(row.get(field) is None for field in timestamps[:-1])
                   and all(row.get(field) is None for field in
                           ("ready_wait_seconds", "execution_seconds", "verification_seconds"))
                   and row.get("result") is None, "blocked task claims execution")
            error = row.get("error")
            blockers = error.get("blocked_by") if isinstance(error, dict) else None
            demand(isinstance(error, dict) and error.get("phase") == "dependency"
                   and isinstance(blockers, list) and blockers
                   and all(isinstance(parent, str) for parent in blockers)
                   and len(blockers) == len(set(blockers)), "blocked task lacks failed dependency")
            demand(all(parent in task_defs[identity]["needs"] and rows[parent]["state"] in {"failed", "blocked"}
                       and rows[parent].get("finished_at_seconds") is not None
                       and rows[parent]["finished_at_seconds"] <= finished for parent in blockers),
                   "blocked task causal dependency mismatch")
            continue
        ready, started, execution = (row.get(field) for field in timestamps[:3])
        verifying = row.get("verify_started_at_seconds")
        demand(ready is not None and started is not None and execution is not None
               and ready <= started <= execution, "local execution timestamp ordering")
        demand(all(parent["state"] == "succeeded" and parent.get("finished_at_seconds") is not None
                   and parent["finished_at_seconds"] <= started for parent in parents),
               "local task started before verified predecessor")
        expected_ready = max((parent["finished_at_seconds"] for parent in parents), default=0.0)
        demand(close(ready, expected_ready), "local ready timestamp mismatch")
        demand(close(event_times.get("running", -1), started) and events[0]["at_seconds"] >= ready,
               "local running event mismatch")
        demand(close(row["ready_wait_seconds"], started - ready)
               and close(row["execution_seconds"], execution - started), "local duration arithmetic mismatch")
        if verifying is not None:
            demand(execution <= verifying <= finished and close(event_times.get("verifying", -1), verifying),
                   "local verification timestamp ordering")
            demand(row.get("verification_seconds") is not None
                   and close(row["verification_seconds"], finished - verifying), "local verification duration mismatch")
        else:
            # The broker records a pre-verification failure, then measures the
            # end of execution in finally; that final timestamp is slightly later.
            demand(row["state"] == "failed" and started <= finished <= execution
                   and row.get("verification_seconds") is None, "local failure timestamp ordering")
        if row["state"] == "succeeded":
            result = row.get("result")
            keys = task_defs[identity].get("output_contract", {}).get("required_result_keys", [])
            demand(row.get("error") is None and (not keys or
                   (isinstance(result, dict) and all(key in result for key in keys))), "local successful result contract mismatch")
            try:
                json.dumps(result, allow_nan=False)
            except (TypeError, ValueError) as exc:
                raise ValueError("invalid local successful result") from exc
        else:
            error = row.get("error")
            phases = {"output_contract"} if verifying is not None else {"input_contract", "handler"}
            demand(row.get("result") is None and isinstance(error, dict)
                   and error.get("phase") in phases, "local failure phase mismatch")


def validate_local_receipt(receipt, model):
    """Bind optional measured local timings to this exact source snapshot."""
    demand(receipt.get("schema") == "atlas.local-broker.receipt.v1", "local receipt schema")
    demand(receipt.get("source_sha") == model["source"]["head_sha"]
           and receipt.get("source_digest") == model["source"]["source_digest"], "local receipt source mismatch")
    demand(receipt.get("local_process_only") is True and receipt.get("dispatch_authorized") is False
           and receipt.get("merge_authorized") is False and receipt.get("authority_transfer") is False,
           "local receipt authority violation")
    demand(receipt.get("source_changed_during_run") is False, "local receipt source drift")
    demand(isinstance(receipt.get("tasks"), dict)
           and all(isinstance(row, dict) for row in receipt["tasks"].values()), "invalid local task records")
    demand(set(receipt.get("tasks", {})) == {t["id"] for t in model["broker"]["tasks"]}, "local receipt task population mismatch")
    bounds, metrics = receipt.get("bounds", {}), receipt.get("metrics", {})
    demand(bounds.get("task_count") == len(receipt["tasks"]), "local receipt denominator mismatch")
    count = len(receipt["tasks"])
    for field in ("elapsed_seconds", "max_running", "peak_ready", "ready_wait_sample_count"):
        value = metrics.get(field)
        demand(type(value) in {int, float} and math.isfinite(value) and value >= 0, "invalid local metric: " + field)
    states = Counter(row.get("state") for row in receipt["tasks"].values())
    demand(set(states) <= {"succeeded", "failed", "blocked"}, "nonterminal local task receipt")
    succeeded = states["succeeded"] == count
    demand(type(receipt.get("success")) is bool and receipt["success"] == succeeded, "local receipt success mismatch")
    demand(receipt.get("outcome") == ("LOCAL_GENERATORS_PASS" if succeeded else "LOCAL_GENERATORS_FAIL"), "local receipt outcome mismatch")
    for field in ("max_running", "peak_ready", "deferred_ready_count", "peak_deferred_ready",
                  "ready_wait_sample_count", "succeeded", "failed", "blocked"):
        demand(type(metrics.get(field)) is int and 0 <= metrics[field] <= count, "invalid local count: " + field)
    for state in ("succeeded", "failed", "blocked"):
        demand(metrics[state] == states[state], "local task count mismatch: " + state)
    waits = []
    task_defs = {t["id"]: t for t in model["broker"]["tasks"]}
    for identity, row in receipt["tasks"].items():
        expected = task_defs[identity]
        demand(row.get("repo") == expected["repo"] and row.get("needs") == expected["needs"], "local task contract mismatch")
        for field in ("ready_wait_seconds", "execution_seconds", "verification_seconds"):
            value = row.get(field)
            demand(value is None or (type(value) in {int, float} and math.isfinite(value) and value >= 0), "invalid local task duration")
        if row.get("ready_wait_seconds") is not None:
            waits.append(row["ready_wait_seconds"])
        if row["state"] != "blocked":
            demand(row.get("ready_wait_seconds") is not None and row.get("execution_seconds") is not None, "local execution timing missing")
    demand(metrics["ready_wait_sample_count"] == len(waits), "local queue sample population mismatch")
    for field, fraction in (("ready_wait_p50_seconds", .5), ("ready_wait_p95_seconds", .95)):
        observed = metrics.get(field)
        if not waits:
            demand(observed is None, "percentile without local samples")
        else:
            expected = sorted(waits)[math.ceil(len(waits) * fraction) - 1]
            demand(type(observed) in {int, float} and math.isfinite(observed) and observed >= 0
                   and math.isclose(observed, expected, rel_tol=1e-9, abs_tol=1e-12), "local percentile mismatch")
    demand(type(bounds.get("workers")) is int and bounds["workers"] > 0
           and metrics["max_running"] <= bounds["workers"], "local receipt worker bound mismatch")
    demand(type(bounds.get("max_pending")) is int and bounds["max_pending"] > 0
           and metrics["peak_ready"] <= bounds["max_pending"], "local receipt queue bound mismatch")
    validate_local_timeline(receipt, task_defs)
    executed = [row for row in receipt["tasks"].values() if row.get("started_at_seconds") is not None]
    intervals = [(row["started_at_seconds"], row["finished_at_seconds"]) for row in executed]
    demand(observed_execution_peak(intervals) <= metrics["max_running"] <= bounds["workers"],
           "local concurrency below observed execution or beyond worker bound")
    return receipt


def verify_bundle(out, head=None, *, require_clean=False, source_root=None):
    out = Path(out)
    manifest = read_json(out, "manifest.json")
    demand(manifest.get("schema") == MANIFEST_SCHEMA, "manifest schema")
    demand(manifest.get("publisher") == "EXISTING_METHOD_ATLAS_PAGES_ONLY"
           and manifest.get("authority_transfer") is False and manifest.get("remote_dispatch") is False
           and manifest.get("merge_admission") == "HOLD", "manifest authority violation")
    demand(SHA.fullmatch(manifest.get("source_sha", "")) is not None, "manifest source SHA")
    if head:
        demand(manifest["source_sha"] == head, "bundle head mismatch")
    if require_clean:
        demand(manifest.get("source_dirty") is False, "dirty source cannot be published")
    members = manifest.get("files_sha256", {})
    demand({"index.html", "style.css", "app.js", "atlas.json", "inventory.json", "burndown.json", "broker-plan.json", "source-check.json"} <= members.keys(), "incomplete member set")
    for name, expected in members.items():
        path = artifact_path(out, name)
        demand(path.is_file() and digest(path.read_bytes()) == expected, "member hash mismatch: " + name)
        demand(path.stat().st_size == manifest["files_bytes"].get(name), "member size mismatch: " + name)
    actual_members = {p.relative_to(out).as_posix() for p in out.rglob("*") if p.is_file()}
    demand(actual_members == set(members) | {"manifest.json"}, "unmanifested bundle member")
    model = read_json(out, "atlas.json")
    demand(model.get("schema") == SCHEMA and model["source"]["head_sha"] == manifest["source_sha"], "model identity mismatch")
    demand(model.get("authority_transfer") is False and model.get("remote_dispatch") is False
           and model.get("merge_admission") == "HOLD", "model authority violation")
    demand(model["source"]["dirty"] == manifest["source_dirty"], "source cleanliness mismatch")
    if "coverage" in model:
        demand({"metric_observations.json", "coverage_burndown.jsonl"} <= members.keys(), "coverage outputs missing")
        demand(read_json(out, "metric_observations.json") == model["coverage"], "coverage model mismatch")
        ledger = [json.loads(line) for line in safe_path(out, "coverage_burndown.jsonl").read_text(encoding="utf-8").splitlines() if line]
        demand(ledger == model["coverage"]["ledger_records"], "coverage ledger mismatch")
    if model.get("broker", {}).get("local_receipt") is not None:
        receipt = validate_local_receipt(model["broker"]["local_receipt"], model)
        demand("local-run.json" in members and read_json(out, "local-run.json") == receipt, "local receipt member mismatch")
    hashes = model["source"]["source_files_sha256"]
    demand(isinstance(hashes, dict) and hashes, "empty source hash map")
    for name, expected in hashes.items():
        safe_path(out, name)
        demand(isinstance(expected, str) and re.fullmatch(r"[0-9a-f]{64}", expected), "invalid source hash")
    expected_source = digest(canonical(hashes))
    demand(manifest.get("source_digest") == expected_source == model["source"].get("source_digest"),
           "source digest mismatch")
    if source_root is not None:
        if model["source"].get("inventory_policy") == SNAPSHOT_POLICY:
            expected_members = set(source_snapshot_paths(source_root, read_json(source_root, PROFILE)))
            demand(set(hashes) == expected_members, "source inventory membership changed")
        for name, expected in hashes.items():
            path = safe_path(source_root, name)
            demand(path.is_file() and digest(path.read_bytes()) == expected,
                   "source bytes changed: " + name)
    return manifest


def build(root, out, head, snapshot=None, local_receipt=None):
    root, out = runtime_root(root), Path(out).resolve()
    demand(not out.is_relative_to(root) and not root.is_relative_to(out), "output overlaps source root")
    model = source_model(root, head, snapshot)
    identities = [g["id"] for g in model["graphs"]]
    stems = [artifact_stem(identity) for identity in identities]
    demand(len(identities) == len(set(identities)), "duplicate graph identity")
    demand(len(stems) == len({stem.casefold() for stem in stems}), "graph artifact filename collision")
    if local_receipt is not None:
        model["broker"]["local_receipt"] = validate_local_receipt(local_receipt, model)
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        verify_bundle(out)
    with tempfile.TemporaryDirectory(prefix=".atlas-build-", dir=out.parent) as temporary:
        staged = Path(temporary) / "bundle"
        staged.mkdir()
        (staged / "graphs").mkdir()
        for g, stem in zip(model["graphs"], stems):
            g["mermaid"] = graph_mermaid(g)
            g["mermaid_path"] = "graphs/" + stem + ".mmd"
            g["svg_path"] = "graphs/" + stem + ".light.svg"
            g["paths"] = {"mermaid": g["mermaid_path"], "svg_light": g["svg_path"],
                          "svg_dark": "graphs/" + stem + ".dark.svg"}
            g["canonical_mermaid_sha256"] = digest(g["mermaid"].encode())
            artifact_path(staged, g["mermaid_path"]).write_text(g["mermaid"], encoding="utf-8")
            artifact_path(staged, g["paths"]["svg_light"]).write_text(graph_svg(g, "light"), encoding="utf-8")
            artifact_path(staged, g["paths"]["svg_dark"]).write_text(graph_svg(g, "dark"), encoding="utf-8")
        for d in model["inventory"]["diagrams"]:
            path = "graphs/source-" + digest(d["path"].encode())[:12] + ".mmd"
            target = artifact_path(staged, path)
            demand(not target.exists(), "source diagram artifact filename collision")
            target.write_bytes(safe_path(root, d["path"]).read_bytes())
            d["artifact_path"] = path
        renderer = module("atlas_execution_renderer", HERE / "render.py")
        renderer.render(model, staged)
        module("atlas_coverage_contract", HERE / "coverage_contract.py").write_outputs(model["coverage"], staged)
        if local_receipt is not None:
            (staged / "local-run.json").write_bytes(canonical(local_receipt))
        for name, value in [("atlas.json", model), ("inventory.json", model["inventory"]),
                            ("source-check.json", model["source_check"]),
                            ("burndown.json", model["burndown"]), ("broker-plan.json", model["broker"])]:
            (staged / name).write_bytes(canonical(value))
        members = sorted(p for p in staged.rglob("*") if p.is_file())
        manifest = {"schema": MANIFEST_SCHEMA, "source_sha": head, "source_dirty": model["source"]["dirty"],
                    "source_digest": model["source"]["source_digest"], "publisher": "EXISTING_METHOD_ATLAS_PAGES_ONLY",
                    "authority_transfer": False, "remote_dispatch": False, "merge_admission": "HOLD",
                    "files_sha256": {p.relative_to(staged).as_posix(): digest(p.read_bytes()) for p in members},
                    "files_bytes": {p.relative_to(staged).as_posix(): p.stat().st_size for p in members}}
        (staged / "manifest.json").write_bytes(canonical(manifest))
        verify_bundle(staged, head, source_root=root)
        if out.exists():
            # Only our already-verified, fully manifest-owned directory is replaced.
            shutil.rmtree(out)
        shutil.move(str(staged), str(out))
    return {"status": "LOCAL_SOURCE_BUILD_PASS", "out": str(out), "graphs": len(model["graphs"]),
            "members": len(manifest["files_sha256"]), "source_digest": manifest["source_digest"]}


def run_local(root, out, head, workers=2):
    root, out = runtime_root(root), Path(out).resolve()
    demand(not out.is_relative_to(root) and not root.is_relative_to(out), "local run output must be outside the source checkout")
    demand(not out.exists() or not any(out.iterdir()), "local run requires a new or empty output directory")
    demand(git(root, "rev-parse", "HEAD") == head, "checkout/head mismatch")
    profile = read_json(root, PROFILE)
    policy = read_json(root, "mission-control/federation-atlas/orchestration/BROKER_POLICY_v1.json")
    source_hashes = {p: digest(safe_path(root, p).read_bytes()) for p in source_snapshot_paths(root, profile)}
    run_source_digest = digest(canonical(source_hashes))
    out.mkdir(parents=True, exist_ok=True)
    blocks = {b["id"]: b for b in profile["blocks"]}
    adapters = {"method": ("method-atlas", []), "control": ("burndown", []),
                "superstitch": ("superstitch", ["--head", head]), "convergence": ("convergence", ["--head", head])}
    def generator(identity):
        block_id, extra = adapters[identity]
        target = out / identity
        command = [sys.executable, str(root / blocks[block_id]["source_path"]), "--out", str(target), *extra]
        env = {**os.environ, "GITHUB_SHA": head}
        result = subprocess.run(command, cwd=root, env=env, capture_output=True, text=True, timeout=240, check=False)
        (out / (identity + ".log")).write_text(result.stdout + result.stderr, encoding="utf-8")
        demand(result.returncode == 0, identity + " generator failed; see " + identity + ".log")
        checked = [validate_artifact(target, port) for port in blocks[block_id]["outputs"]]
        if identity in {"superstitch", "convergence"}:
            verified = subprocess.run([*command, "--verify-only"], cwd=root, env=env, capture_output=True, text=True, timeout=60, check=False)
            demand(verified.returncode == 0, identity + " output verification failed")
        return {"status": "OUTPUT_CONTRACT_PASS", "artifacts": checked,
                "output_files_sha256": output_files(target)}
    def assemble():
        target = out / "assemble"
        shutil.copytree(out / "method", target)
        for path in (out / "control").iterdir():
            if path.is_file():
                shutil.copyfile(path, target / path.name)
        for name in ("superstitch", "convergence", "orchestration"):
            shutil.copytree(out / name, target / name)
        return {"status": "VERIFIED_MEMBERS_JOINED", "output_files_sha256": output_files(target)}
    def portal():
        command = [sys.executable, str(root / blocks["pages-portal"]["source_path"]), "--atlas", str(out / "assemble"), "--out", str(out / "portal"), "--sha", head]
        result = subprocess.run(command, cwd=root, capture_output=True, text=True, timeout=240, check=False)
        (out / "portal.log").write_text(result.stdout + result.stderr, encoding="utf-8")
        demand(result.returncode == 0, "Pages packaging failed; see portal.log")
        for port in blocks["pages-portal"]["outputs"]:
            validate_artifact(out / "portal", port)
        site_manifest = read_json(out / "portal", "site-manifest.json")
        demand(site_manifest.get("source_git_sha") == head, "Pages package source mismatch")
        for name, expected in site_manifest["public_files_sha256"].items():
            member = safe_path(out / "portal", name)
            demand(member.is_file() and digest(member.read_bytes()) == expected, "Pages member hash mismatch: " + name)
        return {"status": "LOCAL_PACKAGE_PASS_NOT_PUBLISHED", "output_files_sha256": output_files(out / "portal")}
    def orchestration():
        result = build(root, out / "orchestration", head)
        return {**result, "output_files_sha256": output_files(out / "orchestration")}
    handlers = {"validate": lambda: validate_profile(root),
                **{key: (lambda identity=key: generator(identity)) for key in adapters},
                "orchestration": orchestration, "assemble": assemble, "portal": portal}
    broker = module("atlas_local_broker", HERE / "broker.py")
    receipt = broker.run_local(tasks(profile), handlers, workers=workers,
                               max_pending=policy.get("default_max_pending", 8), root=root, policy=policy)
    final_hashes = {p: digest(safe_path(root, p).read_bytes()) for p in source_snapshot_paths(root, profile)}
    source_changed = source_hashes != final_hashes or git(root, "rev-parse", "HEAD") != head
    receipt.update(source_sha=head, source_digest=run_source_digest, source_dirty=bool(git(root, "status", "--porcelain")),
                   source_changed_during_run=source_changed,
                   evidence_class="LOCAL_EXECUTION_NOT_NATIVE_CI", output_directory=str(out))
    if source_changed:
        receipt.update(success=False, outcome="SOURCE_CHANGED_DURING_LOCAL_RUN",
                       error="Source snapshot changed during execution; rebuild from a stable checkout.")
    (out / "local-run.json").write_bytes(canonical(receipt))
    return receipt


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["check", "build", "plan", "run-local"])
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--head")
    parser.add_argument("--snapshot", type=Path)
    parser.add_argument("--local-receipt", type=Path, help="Attach completed local timings to a build of the identical source snapshot")
    parser.add_argument("--workers", type=int, default=2)
    args = parser.parse_args(argv)
    try:
        head = args.head or git(args.root, "rev-parse", "HEAD")
        if args.command == "check":
            result = validate_profile(args.root)
            if args.out:
                verify_bundle(args.out, head, source_root=args.root)
                result["bundle"] = "VERIFIED"
        else:
            demand(args.out is not None, "--out required")
            snapshot = json.loads(args.snapshot.read_text(encoding="utf-8")) if args.snapshot else None
            if args.command == "build":
                local_receipt = json.loads(args.local_receipt.read_text(encoding="utf-8")) if args.local_receipt else None
                result = build(args.root, args.out, head, snapshot, local_receipt)
            elif args.command == "plan":
                runtime_root(args.root)
                profile = read_json(args.root, PROFILE)
                policy = read_json(args.root, "mission-control/federation-atlas/orchestration/BROKER_POLICY_v1.json")
                demand(SHA.fullmatch(head or "") is not None, "exact head required")
                demand(git(args.root, "rev-parse", "HEAD") == head, "checkout/head mismatch")
                policy["cohort"] = {"repo": profile["repository"], "source_sha": head}
                result = module("atlas_local_broker", HERE / "broker.py").plan(tasks(profile), snapshot, policy)
                if snapshot is None:
                    result["generated_at"] = None
                    result["time_basis"] = "DETERMINISTIC_SOURCE_PLAN_NO_RUNTIME_OBSERVATION"
                args.out.mkdir(parents=True, exist_ok=True)
                (args.out / "broker-plan.json").write_bytes(canonical(result))
            else:
                result = run_local(args.root, args.out, head, args.workers)
        print(json.dumps(result, sort_keys=True))
        return 1 if result.get("success") is False else 0
    except (ValueError, OSError, KeyError, RuntimeError, json.JSONDecodeError, subprocess.TimeoutExpired) as exc:
        print(json.dumps({"status": "FAIL", "error": str(exc), "remote_dispatch": False}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
