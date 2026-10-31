"""Coverage wave r9: build_sideload_operator validation, telemetry render, build and CLI."""
import copy
import hashlib
import importlib.util
import json
import runpy
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
MOD_DIR = REPO_ROOT / "mission-control" / "federation-atlas"
MOD_PATH = MOD_DIR / "build_sideload_operator.py"
if str(MOD_DIR) not in sys.path:
    sys.path.insert(0, str(MOD_DIR))
_spec = importlib.util.spec_from_file_location("cw_r9_build_sideload_operator_mod", MOD_PATH)
m = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(m)

BASE = json.loads(m.SOURCE.read_text(encoding="utf-8"))
OLD_NOTICE = "Cluster API, workload, edge and artifact byte proof remain UNKNOWN unless linked native receipts are independently authenticated."


def case():
    return copy.deepcopy(BASE)


def telemetry():
    return {
        "schema": "missioncontrol.sideload.w169.telemetry-projection.v1",
        "source_class": "HISTORICAL_EXACT_SHA_NATIVE_ARTIFACT_LOCALLY_HASH_VERIFIED",
        "qps_disposition": "DEFER",
        "release": "HOLD",
        "authority_transfer": False,
        "metrics": {"request_p95_ms": 12.3456, "cold_start_p95_seconds": 3.14159, "restart_count": 0},
        "unbound": {"queue_p95": None, "cpu_peak": None},
        "source_sha": "abc<123>",
        "source_run_id": 111,
        "source_job_id": 222,
        "attempt": 1,
        "source_url": "https://example.invalid/a?b=1&c=2",
    }


def test_source_structure():
    assert isinstance(BASE, dict)
    for k in ("lanes", "promotion_gates", "metrics", "source_snapshot", "safe_defaults"):
        assert k in BASE


@pytest.mark.parametrize("mutate,msg", [
    (lambda d: d.__setitem__("schema", "x"), "unsupported schema"),
    (lambda d: d.__setitem__("role", "DISPATCHER"), "view cannot dispatch"),
    (lambda d: d.pop("trust_levels"), "trust enum"),
    (lambda d: d.__setitem__("lanes", []), "four named"),
    (lambda d: d["lanes"][0].__setitem__("status", "ACCEPTED"), "accepted deployment"),
    (lambda d: d["lanes"][1].__setitem__("repo", "evil/x"), "unbound source owner"),
    (lambda d: d["lanes"][1].pop("repo"), "unbound source owner"),
    (lambda d: d["lanes"][2].__setitem__("ref", ""), "unbound source owner"),
    (lambda d: d["safe_defaults"].__setitem__("engineering_disposition", "ACCEPT"), "bypass"),
    (lambda d: d.pop("safe_defaults"), "bypass"),
    (lambda d: d.__setitem__("promotion_gates", []), "sequence"),
    (lambda d: d.pop("source_contract"), "KEB contract"),
    (lambda d: d.__setitem__("source_contract", {"schema": "other"}), "KEB contract"),
])
def test_validate_rejections(mutate, msg):
    d = case()
    mutate(d)
    with pytest.raises(ValueError, match=msg):
        m.validate(d)


def test_validate_empty_object_rejected():
    with pytest.raises(ValueError, match="unsupported schema"):
        m.validate({})


def test_render_without_telemetry_contains_cards_and_payload():
    d = case()
    page = m.render(d)
    assert page.startswith("<!doctype html>")
    assert page.count('<article class="lane"') == 4
    assert page.count("UNKNOWN / HOLD</td>") == 6
    assert OLD_NOTICE in page
    assert "W169 real Kubernetes" not in page
    payload = page.split('<script id="source" type="application/json">')[1].split("</script>")[0]
    assert "<" not in payload and ">" not in payload and "&" not in payload
    assert json.loads(payload) == d


def test_render_payload_escapes_markup_chars():
    d = case()
    d["source_snapshot"] = "<b>&"
    page = m.render(d)
    assert "SNAPSHOT: &lt;b&gt;&amp;" in page
    assert "\\u003cb\\u003e\\u0026" in page


def test_render_with_valid_telemetry():
    page = m.render(case(), telemetry())
    assert OLD_NOTICE not in page
    assert "One historical W169 kind API/workload run is byte-verified" in page
    assert "W169 real Kubernetes: one exact-head run" in page
    assert "Request p95: 12.35 ms" in page
    assert "Cold-start p95: 3.14 s" in page
    assert "Restarts: 0" in page
    assert "Source: abc&lt;123&gt;" in page
    assert "run 111 / job 222 / attempt 1" in page
    assert 'href="https://example.invalid/a?b=1&amp;c=2"' in page
    assert page.index('aria-label="Native W169 observed telemetry"') < page.index("<h2>Observability fields</h2>")


def test_render_telemetry_float_restart_and_missing_unbound():
    t = telemetry()
    t["metrics"]["restart_count"] = 2.0
    t.pop("unbound")
    page = m.render(case(), t)
    assert "Restarts: 2.0" in page


def _set(path, value):
    def f(t):
        tgt = t
        for p in path[:-1]:
            tgt = tgt[p]
        tgt[path[-1]] = value
    return f


@pytest.mark.parametrize("mutate,msg", [
    (_set(["schema"], "x"), "unsupported runtime telemetry schema"),
    (_set(["source_class"], "LIVE"), "untrusted W169"),
    (_set(["qps_disposition"], "ACCEPT"), "engineering approval"),
    (_set(["release"], "PASS"), "engineering approval"),
    (_set(["authority_transfer"], 0), "engineering approval"),
    (_set(["metrics", "request_p95_ms"], True), "unverified runtime metric"),
    (_set(["metrics", "cold_start_p95_seconds"], "3"), "unverified runtime metric"),
    (_set(["metrics", "restart_count"], None), "unverified runtime metric"),
    (_set(["metrics"], {}), "unverified runtime metric"),
    (_set(["unbound", "cpu_peak"], 0), "falsely promoted"),
])
def test_render_telemetry_rejections(mutate, msg):
    t = telemetry()
    mutate(t)
    with pytest.raises(ValueError, match=msg):
        m.render(case(), t)


def test_render_validates_obj_first():
    d = case()
    d["role"] = "X"
    with pytest.raises(ValueError, match="dispatch"):
        m.render(d, telemetry())


def test_build_with_custom_source_and_telemetry(tmp_path):
    src = tmp_path / "src.json"
    src.write_text(json.dumps(case()), encoding="utf-8")
    tel = tmp_path / "tel.json"
    tel.write_text(json.dumps(telemetry()), encoding="utf-8")
    out = tmp_path / "nested" / "out"
    r = m.build(out, src, tel)
    html_bytes = (out / "sideload-operator.html").read_bytes()
    assert r["html_sha256"] == hashlib.sha256(html_bytes).hexdigest()
    assert r["source_sha256"] == hashlib.sha256(src.read_bytes()).hexdigest()
    assert r["admission"] == "HOLD" and r["authority_transfer"] is False
    assert r["native_cluster_receipt"] is None
    assert r["source_class"] == "STATIC_SOURCE_DECLARATION"
    assert b"W169 real Kubernetes" in html_bytes
    text = (out / "sideload-operator-receipt.json").read_text(encoding="utf-8")
    assert json.loads(text) == r
    assert text.endswith("}\n")


def test_build_invalid_source_writes_nothing(tmp_path):
    d = case()
    d["schema"] = "bad"
    src = tmp_path / "bad.json"
    src.write_text(json.dumps(d), encoding="utf-8")
    out = tmp_path / "out"
    with pytest.raises(ValueError, match="unsupported schema"):
        m.build(out, src)
    assert not out.exists()


def test_cli_main(tmp_path, monkeypatch, capsys):
    out = tmp_path / "cli"
    monkeypatch.setattr(sys, "argv", [str(MOD_PATH), "--out", str(out)])
    runpy.run_path(str(MOD_PATH), run_name="__main__")
    printed = json.loads(capsys.readouterr().out)
    assert printed["schema"] == "missioncontrol.code-purple.sideload-ui-receipt.v1"
    page = (out / "sideload-operator.html").read_bytes()
    assert printed["html_sha256"] == hashlib.sha256(page).hexdigest()


def test_cli_with_telemetry(tmp_path, monkeypatch, capsys):
    tel = tmp_path / "tel.json"
    tel.write_text(json.dumps(telemetry()), encoding="utf-8")
    out = tmp_path / "cli2"
    monkeypatch.setattr(sys, "argv", [str(MOD_PATH), "--out", str(out), "--source", str(m.SOURCE), "--telemetry", str(tel)])
    runpy.run_path(str(MOD_PATH), run_name="__main__")
    assert json.loads(capsys.readouterr().out)["admission"] == "HOLD"
    assert b"Request p95: 12.35 ms" in (out / "sideload-operator.html").read_bytes()


def test_cli_requires_out(monkeypatch):
    monkeypatch.setattr(sys, "argv", [str(MOD_PATH)])
    with pytest.raises(SystemExit) as e:
        runpy.run_path(str(MOD_PATH), run_name="__main__")
    assert e.value.code == 2
