"""Wave 9 coverage tests for mission-control/qps-triage-ultra/ggmath_bridge.py.

The existing suite (test_ggmath_bridge.py) runs the real pinned gg_MATH kernels.
These tests reach the remaining fail-closed and status branches with a fake
ProviderKernels (stub kernel modules, the committed binding) or a synthetic
binding whose bound files live under tmp_path.  No network: urlopen and the
fetcher are faked.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
import types
import urllib.request
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
MOD_PATH = REPO / "mission-control" / "qps-triage-ultra" / "ggmath_bridge.py"
BINDING_FILE = MOD_PATH.parent / "ggmath_provider_binding_v1.json"


@pytest.fixture(scope="module")
def gb():
    spec = importlib.util.spec_from_file_location("cw_w9_ggmath_bridge", MOD_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def binding():
    return json.loads(BINDING_FILE.read_text(encoding="utf-8"))


@pytest.fixture
def clean_kernels(monkeypatch):
    """Isolate sys.modules['kernels*'] and sys.meta_path; restore both afterwards."""
    saved = {n: m for n, m in sys.modules.items() if n == "kernels" or n.startswith("kernels.")}
    for name in saved:
        del sys.modules[name]
    monkeypatch.setattr(sys, "meta_path", list(sys.meta_path))
    yield
    for name in [n for n in sys.modules if n == "kernels" or n.startswith("kernels.")]:
        del sys.modules[name]
    sys.modules.update(saved)


class FakePK:
    def __init__(self, binding, **modules):
        self.binding = binding
        self.sha = "f" * 40
        self._modules = modules

    def module(self, name):
        return self._modules[name]

    def kernel_digests(self, *names):
        return {f"kernels/{n}.py": "0" * 64 for n in names}


def ns(**kw):
    return types.SimpleNamespace(**kw)


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def synthetic_binding(binding, root: Path, sha: str = "a" * 40) -> dict:
    files = {
        "kernels/toy.py": b"VALUE = 7\n",
        "data/x.json": b'{"k": 1}',
        "data/t.txt": b"hello",
    }
    for rel, data in files.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_bytes(data)
    out = json.loads(json.dumps(binding))
    out["provider_sha"] = sha
    out["bridged_kernels"] = [{"path": "kernels/toy.py", "sha256": _sha(files["kernels/toy.py"])}]
    out["provider_data"] = [
        {"id": "X", "path": "data/x.json", "sha256": _sha(files["data/x.json"])},
        {"id": "T", "path": "data/t.txt", "sha256": _sha(files["data/t.txt"])},
    ]
    return out


# ---------------------------------------------------------------- binding / fetch

def test_duplicate_bound_path_rejected(gb, binding):
    binding["bridged_kernels"].append(dict(binding["bridged_kernels"][0]))
    with pytest.raises(gb.BridgeHold) as exc:
        gb.validate_binding(binding)
    assert exc.value.status == "DEFER_BINDING_INVALID"
    assert "duplicate" in exc.value.detail


def test_http_fetch_reads_response(gb, monkeypatch):
    seen = {}

    class Resp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return b"payload"

    def fake_urlopen(url, timeout):
        seen["url"], seen["timeout"] = url, timeout
        return Resp()

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    assert gb._http_fetch("https://example.invalid/x") == b"payload"
    assert seen == {"url": "https://example.invalid/x", "timeout": 30}


def test_fetch_failure_fails_closed(gb, binding, tmp_path, monkeypatch):
    monkeypatch.delenv("GGMATH_PROVIDER_ROOT", raising=False)

    def boom(url):
        raise OSError("offline")

    with pytest.raises(gb.BridgeHold) as exc:
        gb.fetch_provider(binding, cache=tmp_path / "cache", fetcher=boom)
    assert exc.value.status == "DEFER_PROVIDER_FETCH_FAILED"
    assert not any((tmp_path / "cache").rglob("*.py"))


def test_rebind_recomputes_digests(gb, binding):
    calls = []

    def fetcher(url):
        calls.append(url)
        return url.encode("utf-8")

    new_sha = "b" * 40
    out = gb.rebind(binding, new_sha, fetcher=fetcher)
    assert out["provider_sha"] == new_sha
    assert "provider_tree_sha" not in out
    entries = out["bridged_kernels"] + out["provider_data"]
    assert len(calls) == len(entries)
    assert all(new_sha in url for url in calls)
    assert all(e["sha256"] == _sha(u.encode("utf-8")) for e, u in zip(entries, calls))
    assert binding["provider_sha"] != new_sha  # input not mutated


def test_rebind_rejects_short_sha(gb, binding):
    with pytest.raises(gb.BridgeHold) as exc:
        gb.rebind(binding, "abc", fetcher=lambda u: b"")
    assert exc.value.status == "DEFER_BINDING_INVALID"


def test_write_json_lf(gb, tmp_path):
    p = tmp_path / "o.json"
    gb.write_json(p, {"b": 1, "a": 2})
    raw = p.read_bytes()
    assert b"\r\n" not in raw and raw.endswith(b"\n")
    assert list(json.loads(raw)) == ["a", "b"]


# ---------------------------------------------------------------- pinned import

def test_provider_kernels_synthetic_closure(gb, binding, tmp_path, clean_kernels):
    root = tmp_path / "prov"
    b = synthetic_binding(binding, root)
    pk = gb.ProviderKernels(b, root)
    assert pk.module("toy").VALUE == 7
    assert pk.data("X") == {"k": 1}
    assert pk.data("T") == "hello"
    with pytest.raises(gb.BridgeHold) as exc:
        pk.module("not_bound")
    assert exc.value.status == "DEFER_UNBOUND_PROVIDER_MODULE"
    # A second view with the same SHA reuses the active finder.
    before = len(sys.meta_path)
    gb.ProviderKernels(b, root)
    assert len(sys.meta_path) == before


def test_namespace_collision_foreign_kernels_module(gb, binding, tmp_path, clean_kernels):
    root = tmp_path / "prov"
    b = synthetic_binding(binding, root)
    sys.modules["kernels"] = types.ModuleType("kernels")
    with pytest.raises(gb.BridgeHold) as exc:
        gb.ProviderKernels(b, root)
    assert exc.value.status == "DEFER_KERNEL_NAMESPACE_COLLISION"


def test_namespace_collision_other_finder(gb, binding, tmp_path, clean_kernels):
    root = tmp_path / "prov"
    b = synthetic_binding(binding, root)
    sys.meta_path.insert(0, gb._PinnedKernelFinder("c" * 40, {}))
    with pytest.raises(gb.BridgeHold) as exc:
        gb.ProviderKernels(b, root)
    assert exc.value.status == "DEFER_KERNEL_NAMESPACE_COLLISION"


# ---------------------------------------------------------------- jsonable

def test_jsonable_odd_values(gb):
    class Arr:
        def tolist(self):
            return [1.5, float("inf")]

    class Scalar:
        def item(self):
            return 2.25

    class Other:
        def __str__(self):
            return "other"

    out = gb.jsonable({"a": Arr(), "s": Scalar(), "o": Other(), "n": float("nan")})
    assert out == {"a": [1.5, None], "s": 2.25, "o": "other", "n": None}


# ---------------------------------------------------------------- BT reverse pressure

def _pulses(rows, minimum=2):
    return {"authority_transfer": False, "features": ["a_queue_seconds", "b_queue_seconds", "other"],
            "bt_gate": {"minimum_repeat_pulses": minimum, "comparison_semantics": "wait", "interpretation": "x"},
            "rows": [dict(r, evidence_class="MEASURED") for r in rows]}


def _bt(guard_status):
    return ns(finite_mle_guard=lambda pairs, name_universe: {"status": guard_status},
              fit_bradley_terry=lambda pairs, penalty, name_universe: {"penalty": penalty, "n": len(pairs)})


def test_reverse_pressure_missing_measurement(gb, binding):
    pk = FakePK(binding, bt_uncertainty=_bt("PASS_FINITE_MLE_CONDITION"))
    with pytest.raises(gb.BridgeHold) as exc:
        gb.bt_reverse_pressure(pk, _pulses([{"pulse_id": "p1", "a_queue_seconds": 1, "b_queue_seconds": None}]))
    assert exc.value.status == "DEFER_MISSING_MEASUREMENT_NO_IMPUTATION"


ROWS = [{"pulse_id": "p1", "a_queue_seconds": 5, "b_queue_seconds": 5},
        {"pulse_id": "p2", "a_queue_seconds": 10, "b_queue_seconds": 1},
        {"pulse_id": "p3", "a_queue_seconds": 1, "b_queue_seconds": 10}]


def test_reverse_pressure_no_finite_mle(gb, binding):
    pk = FakePK(binding, bt_uncertainty=_bt("DEFER_SEPARATED"))
    env = gb.bt_reverse_pressure(pk, _pulses(ROWS))
    assert env["status"] == "DEFER_NO_FINITE_MLE"
    assert env["result"]["comparisons"] == 2  # the tie is skipped
    assert "penalized_diagnostic" in env["result"] and "fit" not in env["result"]


def test_reverse_pressure_pass(gb, binding):
    pk = FakePK(binding, bt_uncertainty=_bt("PASS_FINITE_MLE_CONDITION"))
    env = gb.bt_reverse_pressure(pk, _pulses(ROWS))
    assert env["status"] == "PASS_REVERSE_PRESSURE_BT"
    assert env["result"]["fit"]["penalty"] == 0.0
    assert env["authority_transfer"] is False


# ---------------------------------------------------------------- PCA / RMT

def _rows(n, p=2):
    return [[float(i + j * (i % 3)) for j in range(p)] for i in range(n)]


def _cal(**over):
    c = {"pa_retained_candidate": [True, True], "observed_eigenvalues": [1.5, 0.5],
         "mp_upper_asymptotic": 1.2, "mp_lower_asymptotic": 0.1,
         "pa95_component_thresholds": [1.1, 0.9], "guard": {"status": "PASS"}}
    c.update(over)
    return c


def test_numeric_rows_rejects_non_numeric(gb, binding):
    pk = FakePK(binding, rmt_calibration=ns())
    with pytest.raises(gb.BridgeHold) as exc:
        gb.rmt_calibration(pk, [[1.0, "x"], [1.0, 2.0], [3.0, 4.0]], evidence_class="MEASURED")
    assert exc.value.status == "DEFER_NON_NUMERIC_PCA_INPUT"


def test_rmt_numerical_degeneracy(gb, binding):
    def bad(x, **kw):
        raise ZeroDivisionError("flat")

    pk = FakePK(binding, rmt_calibration=ns(finite_sample_rmt_calibration=bad))
    env = gb.rmt_calibration(pk, _rows(4), evidence_class="MEASURED")
    assert env["status"] == "DEFER_NUMERICAL_DEGENERACY"
    assert env["bt_admissible"] is False


def _retention_pk(binding, *, boot, gap_status="PASS_EIGENGAP_GUARD", cal=None):
    def bootstrap(x, components, resamples, seed):
        if isinstance(boot, Exception):
            raise boot
        return boot

    return FakePK(
        binding,
        rmt_calibration=ns(finite_sample_rmt_calibration=lambda x, **kw: cal or _cal()),
        pca_uncertainty=ns(eigengap_diagnostics=lambda ev, components: {"status": gap_status, "k": components},
                           bootstrap_pca_uncertainty=bootstrap),
    )


def test_pca_retention_bootstrap_rejected(gb, binding):
    pk = _retention_pk(binding, boot=ValueError("too few"))
    env = gb.pca_retention(pk, _rows(12), ["f1", "f2"], evidence_class="MEASURED")
    assert env["status"] == "DEFER_BOOTSTRAP_REJECTED"
    assert env["result"]["scree"]["leading_retained_candidates"] == 2  # loop ran to the end
    assert env["result"]["sample_adequate"] is True


def test_pca_retention_eigengap_defer(gb, binding):
    pk = _retention_pk(binding, boot={"status": "PASS"}, gap_status="DEFER_EIGENGAP_TOO_SMALL")
    env = gb.pca_retention(pk, _rows(12), ["f1", "f2"], evidence_class="MEASURED")
    assert env["status"] == "DEFER_EIGENGAP_TOO_SMALL"


def test_pca_retention_pass(gb, binding):
    pk = _retention_pk(binding, boot={"status": "PASS"},
                       cal=_cal(pa_retained_candidate=[False, False]))
    env = gb.pca_retention(pk, _rows(12), ["f1", "f2"], evidence_class="MEASURED")
    assert env["status"] == "PASS_PCA_RETENTION_DIAGNOSTIC"
    assert env["result"]["eigengap"]["k"] == 1  # k floors at one
    assert env["bt_admissible"] is False


def _alignment_pk(binding, *, ambiguous=False, temporal=None, raise_exc=False):
    def ref(x, scale, components):
        if raise_exc:
            raise ValueError("rank deficient")
        return {"components_columns": [[1.0, 0.0]]}

    return FakePK(
        binding,
        pca_reference=ns(pca_reference=ref),
        pca_alignment=ns(align_pca_fits=lambda a, b: {"any_component_identity_ambiguous": ambiguous}),
        pca_uncertainty=ns(temporal_subspace_uncertainty=lambda a, b, **kw: temporal or {"status": "PASS"}),
    )


def test_pca_alignment_non_measured(gb, binding):
    with pytest.raises(gb.BridgeHold) as exc:
        gb.pca_alignment(_alignment_pk(binding), _rows(4), _rows(4), components=1, evidence_class="SYNTHETIC")
    assert exc.value.status == "DEFER_NON_MEASURED_PCA_INPUT"


@pytest.mark.parametrize("kwargs,ref_n,expected", [
    ({}, 2, "DEFER_INSUFFICIENT_OBSERVATIONS"),
    ({"raise_exc": True}, 4, "DEFER_NUMERICAL_DEGENERACY"),
    ({"ambiguous": True}, 4, "DEFER_COMPONENT_IDENTITY_AMBIGUOUS"),
    ({"temporal": {"status": "DEFER_UNSTABLE"}}, 4, "DEFER_UNSTABLE"),
    ({}, 4, "PASS_PCA_ALIGNMENT_DIAGNOSTIC"),
])
def test_pca_alignment_statuses(gb, binding, kwargs, ref_n, expected):
    pk = _alignment_pk(binding, **kwargs)
    env = gb.pca_alignment(pk, _rows(ref_n), _rows(4), components=1, evidence_class="MEASURED")
    assert env["status"] == expected
    assert env["adapter"] == "pca_alignment"
    assert set(env["threshold_kind"]) == {"pca_alignment_congruence", "pca_temporal_subspace_uncertainty"}


# ---------------------------------------------------------------- temporal trace from rows

def test_temporal_trace_builds_basis_from_rows(gb, binding):
    class StateClock:
        def __init__(self, k, t, a, wave=None, pulse=None):
            self.k, self.t, self.a = k, t, a

    seen = []

    def pca_reference(x, scale, components):
        seen.append((len(x), components))
        return {"components_columns": [[1.0], [0.0]]}

    pk = FakePK(
        binding,
        temporal_subspace_trace=ns(temporal_subspace_trace=lambda prepared: {
            "adjacent": [{"grassmann_geodesic_distance": 0.1}] * (len(prepared) - 1)}),
        temporal_pca_receipt=ns(StateClock=StateClock,
                                multiclock_step=lambda a, b, distance: {"from": a.k, "to": b.k, "d": distance}),
        pca_reference=ns(pca_reference=pca_reference),
    )
    states = [{"k": i, "t": f"2026-10-0{i + 1}T00:00:00Z", "a": float(i), "rows": _rows(4), "components": "1"}
              for i in range(2)]
    env = gb.temporal_trace(pk, states, evidence_class="MEASURED")
    assert env["status"] == "PASS_TEMPORAL_SUBSPACE_TRACE"
    assert seen == [(4, 1), (4, 1)]
    assert len(env["result"]["multiclock_steps"]) == 1


# ---------------------------------------------------------------- build_receipt guarded holds

def test_build_receipt_guards_bridge_holds(gb, binding, monkeypatch):
    def hold(*a, **kw):
        raise gb.BridgeHold("DEFER_TEST_HOLD", "stub")

    for name in ("bt_strength", "bt_reverse_pressure", "pca_retention", "temporal_trace", "convergence",
                 "w3_pairs_for_bt"):
        monkeypatch.setattr(gb, name, hold)
    monkeypatch.setattr(gb, "research_interfaces", lambda pk: {"status": "RESEARCH_TODO"})
    fake_kpi = types.ModuleType("ggmath_flow_kpi")
    fake_kpi.flow_kpi = lambda jobs, **kw: {"status": "PASS_STUB", "jobs": len(jobs)}
    fake_kpi.jobs_from_gm_i_a = lambda pulses: []
    fake_kpi.jobs_from_fleet_ledger = lambda ledger: []
    fake_kpi.excluded_from_fleet_ledger = lambda ledger: []
    monkeypatch.setitem(sys.modules, "ggmath_flow_kpi", fake_kpi)

    class PK(FakePK):
        def data(self, data_id):
            return {"features": ["a"], "rows": []}

    pk = PK(binding, temporal_subspace_trace=ns(rank3_r4_basis=lambda th: [[1.0], [th]]))
    receipt = gb.build_receipt(pk)
    assert receipt["schema"] == gb.RECEIPT_SCHEMA
    assert receipt["authority_transfer"] is False
    held = [v for v in receipt["measured"].values() if v.get("status") == "DEFER_TEST_HOLD"]
    assert len(held) == 4
    assert receipt["reference_challenges"]["convergence_reference_cohort"]["status"] == "DEFER_TEST_HOLD"
    assert receipt["reference_challenges"]["temporal_trace_rank3_r4"]["adapter"] == "hold"


# ---------------------------------------------------------------- CLI

@pytest.fixture
def cli(gb, binding, monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "path", list(sys.path))
    monkeypatch.setattr(gb, "BINDING_PATH", tmp_path / "binding.json")
    monkeypatch.setattr(gb, "load_binding", lambda: binding)
    pk = types.SimpleNamespace(sha="d" * 40, digests={"a": 1, "b": 2})
    monkeypatch.setattr(gb, "load_kernels", lambda b, provider_root=None: pk)
    return gb


def test_main_fetch(cli, capsys):
    assert cli.main(["fetch"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out == {"provider_sha": "d" * 40, "verified_files": 2}


def test_main_build(cli, monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(cli, "build_receipt", lambda pk: {"schema": "x", "sha": pk.sha})
    out = tmp_path / "receipt.json"
    assert cli.main(["build", "--out", str(out)]) == 0
    assert json.loads(out.read_text(encoding="utf-8"))["sha"] == "d" * 40
    assert "wrote" in capsys.readouterr().out


def test_main_rebind(cli, monkeypatch, capsys):
    monkeypatch.setattr(cli, "rebind", lambda b, sha: dict(b, provider_sha=sha))
    assert cli.main(["rebind", "--sha", "e" * 40]) == 0
    written = json.loads(cli.BINDING_PATH.read_text(encoding="utf-8"))
    assert written["provider_sha"] == "e" * 40
    assert "rebound" in capsys.readouterr().out


def test_main_bridge_hold(cli, monkeypatch, capsys):
    def hold(b, provider_root=None):
        raise cli.BridgeHold("DEFER_PROVIDER_FETCH_FAILED", "offline")

    monkeypatch.setattr(cli, "load_kernels", hold)
    assert cli.main(["fetch"]) == 2
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "DEFER_PROVIDER_FETCH_FAILED" and out["authority_transfer"] is False


def test_load_binding_from_file(gb, binding, tmp_path):
    p = tmp_path / "binding.json"
    p.write_text(json.dumps(binding), encoding="utf-8")
    assert gb.load_binding(p)["provider_sha"] == binding["provider_sha"]
