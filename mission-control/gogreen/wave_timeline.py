"""GOGREEN evolutionary wave scorecard; source-bound, append-only and read-only.

The six-repository/42-cell catalogue is held fixed. A new cohort must use a new
baseline rather than silently changing the old denominator. NEVER infer approval
from a successful GitHub workflow or treat unknown measurements as zero.
"""
from __future__ import annotations

from datetime import datetime, timezone
import argparse
import hashlib
import html
import json
import re
from pathlib import Path

SCHEMA = "gogreen.rolling-wave-ledger.v1"
SHA = re.compile(r"[0-9a-f]{40}\Z")
ARCHIVE = re.compile(r"sha256:[0-9a-f]{64}\Z")
FULL_REPO = "GBOGEB/pipeline-automation-hub"


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _integer(value, name, *, positive=False):
    if type(value) is not int or value < (1 if positive else 0):
        raise ValueError(f"invalid integer {name}")


def validate(data, previous=None):
    if data.get("schema") != SCHEMA or data.get("cohort") != "SIX_REPO_FIXED_42_CELLS":
        raise ValueError("unsupported cohort or schema")
    if data.get("authority_transfer") is not False or data.get("merge_authorized") is not False:
        raise ValueError("source ledger cannot grant authority")
    if data.get("qps_disposition") != "DEFER":
        raise ValueError("QPS owner cannot be promoted by wave telemetry")
    if data.get("wave_clock") != "LOGICAL_WAVE_NOT_INDEPENDENT_GIT_REVISION":
        raise ValueError("logical wave clock cannot equal Git revision clock")
    rules = data.get("measurement_rules")
    if not isinstance(rules, dict) or not rules or not all(type(v) is bool and v for v in rules.values()):
        raise ValueError("measurement policy must fail closed")
    catalog = data.get("catalog")
    if not isinstance(catalog, list) or len(catalog) != 6:
        raise ValueError("expected six fixed repositories")
    repositories = set()
    target = 0
    for entry in catalog:
        name = entry.get("repository")
        if not isinstance(name, str) or name in repositories or not name.startswith("GBOGEB/"):
            raise ValueError("invalid or duplicate catalog repository")
        repositories.add(name)
        if not SHA.fullmatch(entry.get("sha", "")):
            raise ValueError("catalog SHA invalid")
        _integer(entry.get("target_family_cells"), "catalog target", positive=True)
        target += entry["target_family_cells"]
    if target != 42:
        raise ValueError("fixed source scope denominator drift")
    waves = data.get("waves")
    if not isinstance(waves, list) or len(waves) < 2:
        raise ValueError("at least two observed waves required")
    prev_time = None
    for i, wave in enumerate(waves):
        try:
            stamp = wave["observed_at_utc"]
            if not isinstance(stamp, str) or not stamp.endswith("Z"):
                raise ValueError("missing UTC Z timestamp")
            when = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
            if when.utcoffset() != timezone.utc.utcoffset(None):
                raise ValueError("non-UTC observation")
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("invalid UTC wave evidence timestamp") from exc
        if prev_time is not None and when < prev_time:
            raise ValueError("wave clock chronology reversed")
        prev_time = when
        if wave.get("wave") != f"G{i}" or wave.get("ordinal") != i:
            raise ValueError("wave ordering/regression")
        if wave.get("repository") != FULL_REPO or not SHA.fullmatch(wave.get("source_sha", "")):
            raise ValueError("wave source identity")
        if wave.get("run_conclusion") != "success":
            raise ValueError("only native terminal PASS wave receipts enter this ledger")
        for key in ("run_id", "job_id", "run_attempt", "archive_artifact_id"):
            _integer(wave.get(key), key, positive=True)
        if wave.get("workflow_url") != (
            f"https://github.com/{FULL_REPO}/actions/runs/{wave['run_id']}"
        ):
            raise ValueError("workflow URL provenance mismatch")
        if not ARCHIVE.fullmatch(wave.get("archive_sha256", "")):
            raise ValueError("malformed native artifact archive digest")
        if wave.get("archive_bytes_independently_verified") is not False:
            raise ValueError("uploaded artifact digest is not independent archive byte proof")
        fleet = wave.get("fleet")
        if not isinstance(fleet, dict) or fleet.get("catalog_cells") != target:
            raise ValueError("wave denominator changed")
        for key in ("observed_cells", "status_only_cells", "verified_source_archive_bytes"):
            _integer(fleet.get(key), key)
        if not 0 <= fleet["status_only_cells"] <= fleet["observed_cells"] <= target:
            raise ValueError("invalid observed/status-only cell geometry")
        if i and fleet["observed_cells"] < waves[i - 1]["fleet"]["observed_cells"]:
            raise ValueError("observation regression; append correction events, do not rewrite")
        tests = wave.get("tests")
        if not isinstance(tests, dict) or tests.get("suite_id") != "GOGREEN_G4_NATIVE_UNITTTEST_DISCOVERY":
            raise ValueError("incompatible test discovery family")
        counts = (tests.get("executed"), tests.get("passed"), tests.get("failed"), tests.get("skipped"))
        if all(x is None for x in counts):
            pass
        elif any(type(x) is not int or x < 0 for x in counts):
            raise ValueError("unknown counts cannot be represented as numeric zero")
        elif counts[0] == 0 or counts[0] != counts[1] + counts[2] + counts[3] or counts[2] != 0:
            raise ValueError("invalid or unsuccessful native test receipt")
        focused = wave.get("focused")
        if focused is not None:
            if tests["executed"] is None or focused.get("tool") != "coverage.py":
                raise ValueError("missing native test/coverage lineage")
            if focused.get("source_file") != "mission-control/gogreen/pulse_rollup.py":
                raise ValueError("unexpected focused module")
            if not re.fullmatch("[0-9a-f]{64}", focused.get("source_file_sha256", "")):
                raise ValueError("missing source-file bytes identity")
            if focused.get("tool_version") != "7.13.3":
                raise ValueError("unmatched coverage instrumentation")
            for dimension in ("statements", "branches"):
                values = focused.get(dimension)
                if not isinstance(values, dict):
                    raise ValueError("missing coverage dimension")
                _integer(values.get("covered"), dimension + " covered")
                _integer(values.get("eligible"), dimension + " eligible", positive=True)
                if values["covered"] > values["eligible"]:
                    raise ValueError("impossible coverage ratio")
        roots = wave.get("root_predicates_recovered")
        if roots is not None:
            _integer(roots, "recovered first-red fingerprints")
            if i == 0:
                raise ValueError("historical first-red recovery requires a subsequent wave")
        if not isinstance(wave.get("scope_notes"), str) or not wave["scope_notes"].strip():
            raise ValueError("missing scope statement")
    if previous is not None:
        validate(previous)
        old = previous["waves"]
        if len(waves) <= len(old):
            raise ValueError("append-only new-wave evidence required")
        if data["catalog"] != previous["catalog"] or data["measurement_rules"] != previous["measurement_rules"]:
            raise ValueError("historical catalog or comparability rules rewritten")
        if canonical(waves[: len(old)]) != canonical(old):
            raise ValueError("existing wave evidence tampered with")
    return True


def _percent(numerator, denominator):
    return round(100 * numerator / denominator, 4)


def _coverage_delta(previous, current, dimension):
    a, b = previous.get("focused"), current.get("focused")
    if a is None or b is None:
        return None
    identity = ("tool", "tool_version", "source_file", "source_file_sha256")
    if any(a[key] != b[key] for key in identity):
        return None
    before, after = a[dimension], b[dimension]
    if before["eligible"] != after["eligible"]:
        return None
    return round(100 * (after["covered"] - before["covered"]) / before["eligible"], 4)


def build(data, *, source_sha):
    validate(data)
    if not SHA.fullmatch(source_sha):
        raise ValueError("current native head SHA required")
    result = []
    for i, wave in enumerate(data["waves"]):
        fleet = wave["fleet"]
        tests = wave["tests"]
        row = {
            "wave": wave["wave"], "kind": wave["kind"], "observed_at_utc": wave["observed_at_utc"],
            "source_sha": wave["source_sha"], "run_id": wave["run_id"],
            "job_id": wave["job_id"], "run_attempt": wave["run_attempt"],
            "workflow_url": wave["workflow_url"],
            "artifact_id": wave["archive_artifact_id"],
            "artifact_digest": wave["archive_sha256"],
            "observed_cells": fleet["observed_cells"],
            "catalog_cells": fleet["catalog_cells"],
            "evidence_breadth_pct": _percent(fleet["observed_cells"], fleet["catalog_cells"]),
            "status_only_cells": fleet["status_only_cells"],
            "verified_source_archive_bytes": fleet["verified_source_archive_bytes"],
            "regression_tests_pass": tests["passed"],
            "recovered_first_red_fingerprints": wave["root_predicates_recovered"],
            "scope_notes": wave["scope_notes"],
            "focused": wave["focused"],
            "delta": {
                "observed_cells": None, "breadth_percentage_points": None,
                "native_tests": None, "focused_statement_coverage_pp": None,
                "focused_branch_coverage_pp": None,
                "recovered_roots": None,
            },
        }
        if i:
            prev = data["waves"][i - 1]
            row["delta"]["observed_cells"] = fleet["observed_cells"] - prev["fleet"]["observed_cells"]
            row["delta"]["breadth_percentage_points"] = round(
                row["evidence_breadth_pct"] -
                _percent(prev["fleet"]["observed_cells"], prev["fleet"]["catalog_cells"]), 4,
            )
            if prev["tests"]["passed"] is not None and tests["passed"] is not None:
                row["delta"]["native_tests"] = tests["passed"] - prev["tests"]["passed"]
            row["delta"]["focused_statement_coverage_pp"] = _coverage_delta(prev, wave, "statements")
            row["delta"]["focused_branch_coverage_pp"] = _coverage_delta(prev, wave, "branches")
            if prev["root_predicates_recovered"] is not None and wave["root_predicates_recovered"] is not None:
                row["delta"]["recovered_roots"] = (
                    wave["root_predicates_recovered"] - prev["root_predicates_recovered"]
                )
        result.append(row)
    return {
        "schema": "gogreen.rolling-wave-report.v1",
        "producer_source_sha": source_sha,
        "source_catalog_repo_count": len(data["catalog"]),
        "source_catalog_target_cells": sum(x["target_family_cells"] for x in data["catalog"]),
        "wave_clock": data["wave_clock"], "waves": result,
        "future": {"next_wave": f"G{len(result)}", "status": "WAIT_FOR_NATIVE_EVIDENCE"},
        "improvement_claims": {
            "fleet_breadth_gain_last_wave_pp": result[-1]["delta"]["breadth_percentage_points"],
            "native_test_gain_last_wave": result[-1]["delta"]["native_tests"],
            "global_root_closures": None, "fleet_code_coverage": None,
            "archive_bytes_verified": 0, "real_worker_launches": None,
            "independent_trials": None, "PCA_eligible": False,
            "Bradley_Terry_eligible": False,
        },
        "admission": "HOLD", "qps_disposition": "DEFER",
        "authority_transfer": False, "merge_authorized": False,
    }


def _num(value, unit="", *, signed=False):
    if value is None:
        return "UNKNOWN"
    prefix = "+" if signed and value > 0 else ""
    return f"{prefix}{value}{unit}"


def render_markdown(report):
    rows = [
        "# MissionControl | rolling G0→G1→G2→... wave scorecard",
        "",
        "Each wave is immutable after recording. Gain means previous **comparable** wave only.",
        "",
        "| Wave | Breadth | Δ cells | Δ pp | Native tests | Δ tests | Statement coverage | Branch coverage | First-red evidence |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for x in report["waves"]:
        focused = x["focused"]
        statement = "UNKNOWN" if focused is None else (
            f"{focused['statements']['covered']}/{focused['statements']['eligible']}"
        )
        branch = "UNKNOWN" if focused is None else (
            f"{focused['branches']['covered']}/{focused['branches']['eligible']}"
        )
        roots = "UNKNOWN" if x["recovered_first_red_fingerprints"] is None else (
            f"{x['recovered_first_red_fingerprints']} PR-head predicates (not global roots)"
        )
        d = x["delta"]
        rows.append(
            f"| [{x['wave']}]({x['workflow_url']}) | {x['observed_cells']}/{x['catalog_cells']} "
            f"({x['evidence_breadth_pct']:.2f}%) | {_num(d['observed_cells'], signed=True)} | "
            f"{_num(d['breadth_percentage_points'], ' pp', signed=True)} | "
            f"{_num(x['regression_tests_pass'])} | {_num(d['native_tests'], signed=True)} | "
            f"{statement} | {branch} | {roots} |"
        )
    rows.extend([
        "",
        "**Boundary:** Native tests are not fleet coverage. Unknown is not zero. "
        "Archive upload digests are not independent ZIP-byte evidence.",
        "PCA/Bradley–Terry remain ineligible; neither a merged PR nor a green CI "
        "wave authorizes QPS admission.",
        "",
        f"Next: {report['future']['next_wave']} — {report['future']['status']}.",
        f"Producer exact SHA: {report['producer_source_sha']}.",
    ])
    return "\n".join(rows) + "\n"


def render_html(report):
    esc = lambda v: html.escape(str(v), quote=True)
    max_cells = report["source_catalog_target_cells"]
    rows = []
    bars = []
    for w in report["waves"]:
        p = w["evidence_breadth_pct"]
        delta = w["delta"]
        d = _num(delta["breadth_percentage_points"], " pp", signed=True)
        new_tests = _num(delta["native_tests"], signed=True)
        tests = _num(w["regression_tests_pass"])
        recovered = _num(w["recovered_first_red_fingerprints"])
        url = esc(w["workflow_url"])
        label = esc(w["wave"])
        bar = f'<div class="bar" role="img" aria-label="{label}: {p:.2f} percent of {max_cells} cells"><span style="width:{p:.2f}%"></span></div>'
        bars.append(
            f'<div class="measure"><div class="between"><strong>{label} evidence breadth</strong>'
            f'<b>{p:.2f}%</b></div>{bar}<div class="small">Δ {esc(d)} from prior comparable wave</div></div>'
        )
        roots = "UNKNOWN" if recovered == "UNKNOWN" else esc(recovered) + " PR-head fingerprints"
        focused = w["focused"]
        stmt = "UNKNOWN" if focused is None else f"{focused['statements']['covered']}/{focused['statements']['eligible']}"
        br = "UNKNOWN" if focused is None else f"{focused['branches']['covered']}/{focused['branches']['eligible']}"
        rows.append(
            f'<tr><th scope="row"><a href="{url}">{label}</a><div class="small">{esc(w["observed_at_utc"])}</div><div class="small">{esc(w["scope_notes"])}</div></th>'
            f'<td>{w["observed_cells"]}/{max_cells}</td>'
            f'<td>{esc(d)}</td><td>{esc(tests)}</td>'
            f'<td>{esc(new_tests)}</td><td>{esc(stmt)}</td><td>{esc(br)}</td>'
            f'<td>{roots}</td></tr>'
        )
    cards = []
    newest = report["waves"][-1]
    for title, value, sub in (
        ("Fleet evidence breadth", f"{newest['observed_cells']}/{max_cells}", f"{newest['evidence_breadth_pct']:.2f}% observed"),
        ("Native regression tests", _num(newest["regression_tests_pass"]), f"Δ {_num(newest['delta']['native_tests'], signed=True)}"),
        ("Focused statement coverage", (f"{newest['focused']['statements']['covered']}/{newest['focused']['statements']['eligible']}" if newest["focused"] is not None else "UNKNOWN"), "Not whole-repository"),
        ("Source first-reds recovered", _num(newest["recovered_first_red_fingerprints"]), "Not global causal-root closure"),
    ):
        cards.append(
            f'<section class="card"><p class="small">{esc(title)}</p><div class="number">{esc(value)}</div>'
            f'<p class="small">{esc(sub)}</p></section>'
        )
    return """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="dark light"><title>MissionControl | Evolutionary G0→G1→G2 Waves</title>
<style>
:root{color-scheme:dark;--bg:#0e0e0e;--fg:#fafafa;--muted:#b5b5b5;--line:#363636;--track:#2b2b2b}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.55 system-ui,Segoe UI,sans-serif}
main{max-width:1150px;margin:auto;padding:28px 22px 50px}h1{font-size:1.7rem}h2{font-size:1.15rem;margin-top:30px}
a{color:#fff;text-decoration:underline;text-underline-offset:3px}a:focus-visible{outline:3px solid white;outline-offset:4px}
.small{font-size:.81rem;color:var(--muted);margin:4px 0}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(185px,1fr));gap:12px}
.card{border:1px solid var(--line);border-radius:8px;padding:14px}.number{font-weight:750;font-size:1.6rem}
.between{display:flex;align-items:center;justify-content:space-between}.measure{margin:14px 0}.bar{height:10px;background:var(--track);border-radius:20px;overflow:hidden}.bar>span{height:100%;display:block;background:#939393}
.table-scroll{overflow-x:auto}table{border-collapse:collapse;width:100%;min-width:750px}th,td{padding:10px;text-align:right;border-bottom:1px solid var(--line);font-variant-numeric:tabular-nums}th:first-child,td:first-child{text-align:left}
thead th{color:#ddd}footer{margin-top:28px;color:var(--muted);border-top:1px solid var(--line);padding-top:16px}
@media (prefers-color-scheme:light){:root{--bg:#fff;--fg:#161616;--muted:#555;--line:#ddd;--track:#eee}a{color:#222}.bar>span{background:#555}}
</style></head><body><main>
<h1>MissionControl — evolutionary wave scorecard</h1>
<p>New waves are appended, with independently bounded deltas. No wave overwrites earlier measurements.</p>
<div class="grid">""" + "".join(cards) + """</div>
<h2>Fleet evidence breadth, wave by wave</h2>""" + "".join(bars) + """
<h2>Horizontal measurement history</h2><div class="table-scroll"><table>
<thead><tr><th scope="col">Wave / native evidence</th><th scope="col">Fleet cells</th><th scope="col">Δ breadth</th>
<th scope="col">Native tests</th><th scope="col">Δ tests</th><th scope="col">Statements</th>
<th scope="col">Branches</th><th scope="col">First-red evidence</th></tr></thead><tbody>""" + "".join(rows) + """</tbody></table></div>
<h2>Next wave</h2><p>""" + esc(report["future"]["next_wave"]) + """ — awaiting source-bound terminal measurements.
Unmeasured improvement remains <strong>UNKNOWN</strong>, not zero.</p>
<footer>Scope: fixed six repositories / 42 cells. Coverage: one exact-source G4 module, not fleet.
Run badges and artifacts are not owner approval. PCA/BT and QPS acceptance remain HOLD.
<br>Report producer source SHA: <code>""" + esc(report["producer_source_sha"]) + """</code></footer>
</main></body></html>
"""


def emit(report, out):
    out.mkdir(parents=True, exist_ok=True)
    payload = (json.dumps(report, sort_keys=True, indent=2) + "\n").encode()
    digest = hashlib.sha256(payload).hexdigest()
    (out / "wave_timeline.json").write_bytes(payload)
    (out / "wave_timeline.sha256").write_text(digest + "\n", encoding="ascii")
    (out / "wave_timeline.md").write_text(render_markdown(report), encoding="utf-8")
    (out / "wave_timeline.html").write_text(render_html(report), encoding="utf-8")
    return digest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--previous", type=Path)
    a = parser.parse_args()
    data = json.loads(a.input.read_text())
    previous = json.loads(a.previous.read_text()) if a.previous else None
    validate(data, previous=previous)
    report = build(data, source_sha=a.source_sha)
    digest = emit(report, a.out)
    print(json.dumps({"waves": len(report["waves"]), "latest": report["waves"][-1]["wave"],
                      "next": report["future"]["next_wave"], "digest": digest,
                      "merge_authorized": False}, sort_keys=True))


if __name__ == "__main__":
    main()
