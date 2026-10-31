"""Coverage wave 9: mission-control/federation-atlas/flightdeck/pulses/mip_provider_execution.py.

The gg_MATH provider checkout is a tmp_path tree of small fake kernels and its
``git rev-parse`` identity is faked; no real process or provider is used.
Fake kernel behaviour is steered by CW_W9_* environment variables.
"""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
PULSES = REPO_ROOT / "mission-control" / "federation-atlas" / "flightdeck" / "pulses"
MOD_PATH = PULSES / "mip_provider_execution.py"
if str(PULSES) not in sys.path:
    sys.path.insert(0, str(PULSES))
_spec = importlib.util.spec_from_file_location("cw_w9_mip_provider_execution_mod", MOD_PATH)
m = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = m
_spec.loader.exec_module(m)

SHA = "3" * 40

KERNELS = {
    "__init__.py": "",
    "stats_core.py": '''
import os
def wilson_proportion_interval(k, n, level):
    return {"interval": [0.0, 1.0], "level": level, "k": k, "n": n}
def one_way_anova(groups):
    f = float("nan") if os.environ.get("CW_W9_NAN_F") else 2.5
    return {"f_statistic": f, "eta_squared": 0.3, "df_between": len(groups) - 1,
            "df_within": sum(map(len, groups)) - len(groups)}
''',
    "pca_reference.py": '''
import os
def pca_reference(rows, scale=True):
    p = int(os.environ.get("CW_W9_EIG", len(rows[0])))
    eig = [float(p - i) for i in range(p)]
    total = sum(eig)
    return {"n": len(rows), "p": len(rows[0]), "eigenvalues": eig,
            "explained_variance_ratio": [e / total for e in eig]}
def parallel_analysis(rows, simulations, percentile, seed, scale):
    return {"retained_candidate_count": 1, "null_eigenvalue_thresholds": [1.0]}
def bootstrap_loading_stability(rows, simulations, seed, scale, components):
    return {"summary": [0.99], "simulations": simulations}
''',
    "pca_alignment.py": '''
def align_pca_fits(old, current):
    return {"classification": "STABLE", "any_component_identity_ambiguous": False,
            "matches": [[0, 0]]}
''',
    "bradley_terry.py": '''
import os
def rank_pairs(pairs, iterations):
    names = sorted({x for p in pairs for x in p})
    return {"status": os.environ.get("CW_W9_BT", "PASS_TESTABLE_ENGINE"),
            "scores": {n: 1.0 for n in names}}
''',
    "bt_uncertainty.py": '''
import os
def fit_bradley_terry(pairs, penalty):
    return {"status": os.environ.get("CW_W9_FIT", "PASS"), "fit_kind": "MLE",
            "covariance_kind": "FISHER"}
def pair_probability_interval(fit, a, b, level):
    return {"probability": 0.5, "interval": [0.4, 0.6], "level": level}
''',
    "manova_reference.py": '''
def manova_reference(groups):
    return {"schema": "fake.manova.v1", "wilks_lambda": 0.5, "pillai_trace": 0.4,
            "p_value": None, "df_between": len(groups) - 1, "df_within": 30}
''',
}


def design():
    pairs = [["A", "B"], ["B", "A"], ["A", "C"], ["C", "A"], ["B", "C"], ["C", "B"]]
    return {
        "schema": "code-purple.statistical-design.v1",
        "source_bound": True, "cohort_matched": True, "authority_transfer": False,
        "source_sha": "a" * 40, "independent_units": 12, "feature_count": 2,
        "independence_verified": True, "same_scope": True, "same_units": True,
        "complete_terminal": True, "sampling_design_approved": True, "successes": 9,
        "eigenspace_diagnostics_pass": True, "covariance_rank": 2,
        "group_sizes": [4, 4, 4], "residual_diagnostics_pass": True,
        "pairwise_comparisons": len(pairs), "comparison_graph_connected": True,
        "finite_bt_fit_conditions": True,
    }


def request():
    rows = [[float(i), float(i % 3)] for i in range(12)]
    return {
        "schema": m.INPUT, "data_class": "SYNTHETIC_REFERENCE", "authority_transfer": False,
        "provider_sha": SHA, "design": design(),
        "reference_data": {
            "pca_rows": rows, "pca_reference_rows": [r[:] for r in rows],
            "anova_groups": [[1.0, 2.0, 3.0, 4.0], [2.0, 3.0, 4.0, 5.0], [0.0, 1.0, 1.0, 2.0]],
            "manova_groups": [[r[:] for r in rows[j * 4:(j + 1) * 4]] for j in range(3)],
            "winner_loser_pairs": [["A", "B"], ["B", "A"], ["A", "C"], ["C", "A"], ["B", "C"], ["C", "B"]],
        },
    }


@pytest.fixture
def provider(tmp_path, monkeypatch):
    root = tmp_path / "gg_MATH"
    (root / "kernels").mkdir(parents=True)
    for name, text in KERNELS.items():
        (root / "kernels" / name).write_text(text, encoding="utf-8")
    calls = []

    def check_output(cmd, text=False, timeout=None):
        calls.append(list(cmd))
        return SHA + "\n"

    monkeypatch.setattr(m.subprocess, "check_output", check_output)
    monkeypatch.setattr(sys, "path", list(sys.path))
    for k in [k for k in sys.modules if k == "kernels" or k.startswith("kernels.")]:
        monkeypatch.delitem(sys.modules, k)
    yield root, calls
    for k in [k for k in sys.modules if k == "kernels" or k.startswith("kernels.")]:
        del sys.modules[k]


# ------------------------------------------------------------------ verify_provider
def test_verify_provider_happy_path_inserts_path_once(provider):
    root, calls = provider
    assert m.verify_provider(root, SHA) == SHA
    assert calls[0][:2] == ["git", "-C"] and calls[0][-2:] == ["rev-parse", "HEAD"]
    n = sys.path.count(str(root.resolve()))
    assert n == 1
    m.verify_provider(root, SHA)
    assert sys.path.count(str(root.resolve())) == 1


@pytest.mark.parametrize("expected", [None, "abc", "G" * 40])
def test_verify_provider_rejects_inexact_sha(provider, expected):
    with pytest.raises(ValueError, match="exact provider SHA"):
        m.verify_provider(provider[0], expected)


def test_verify_provider_missing_dir_and_symlink(tmp_path, provider):
    with pytest.raises(ValueError, match="checkout missing"):
        m.verify_provider(tmp_path / "nope", SHA)
    link = tmp_path / "link"
    try:
        os.symlink(provider[0], link, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks unavailable on this host")
    with pytest.raises(ValueError, match="checkout missing"):
        m.verify_provider(link, SHA)


@pytest.mark.parametrize("exc", [OSError("no git"), subprocess.TimeoutExpired("git", 10)])
def test_verify_provider_git_unavailable(provider, monkeypatch, exc):
    def boom(*a, **k):
        raise exc
    monkeypatch.setattr(m.subprocess, "check_output", boom)
    with pytest.raises(ValueError, match="git identity unavailable"):
        m.verify_provider(provider[0], SHA)


def test_verify_provider_sha_mismatch_and_missing_kernel(provider):
    root, _ = provider
    with pytest.raises(ValueError, match="SHA mismatch"):
        m.verify_provider(root, "f" * 40)
    (root / "kernels" / "manova_reference.py").unlink()
    with pytest.raises(ValueError, match="missing canonical provider kernels"):
        m.verify_provider(root, SHA)


# ------------------------------------------------------------------ evaluate
@pytest.mark.parametrize("mutate", [
    lambda r: r.update(schema="other"),
    lambda r: r.update(authority_transfer=True),
    lambda r: r.pop("authority_transfer"),
])
def test_evaluate_rejects_invalid_request(mutate):
    req = request()
    mutate(req)
    with pytest.raises(ValueError, match="invalid provider request"):
        m.evaluate(req)
    with pytest.raises(ValueError, match="invalid provider request"):
        m.evaluate(["not", "a", "dict"])


def test_evaluate_rejects_unsupported_class():
    req = request()
    req["data_class"] = "NATIVE_ACCEPTED"
    with pytest.raises(ValueError, match="unsupported evidence class"):
        m.evaluate(req)


def test_native_unverified_holds_without_provider():
    req = request()
    req["data_class"] = "NATIVE_UNVERIFIED"
    out = m.evaluate(req)
    assert out["provider_executed"] is False and out["provider_sha"] is None
    assert {v["status"] for v in out["methods"].values()} == {"HOLD_NATIVE_INDEPENDENCE_NOT_ATTESTED"}
    assert out["admission"] == "HOLD" and out["merge_authorized"] is False


def test_synthetic_requires_provider_root():
    with pytest.raises(ValueError, match="pinned provider checkout required"):
        m.evaluate(request())


def test_reference_data_must_be_dict(provider):
    req = request()
    req["reference_data"] = []
    with pytest.raises(ValueError, match="synthetic reference data required"):
        m.evaluate(req, provider_root=provider[0])


def test_all_methods_eligible_full_reference(provider):
    out = m.evaluate(request(), provider_root=provider[0])
    assert out["provider_sha"] == SHA and out["provider_executed"] is True
    meth = out["methods"]
    assert set(meth["wilson"]["confidence_bands"]) == {"90", "95", "99"}
    assert meth["wilson"]["confidence_bands"]["95"]["level"] == 0.95
    pca = meth["pca"]
    assert pca["status"] == "SYNTHETIC_REFERENCE_ONLY" and pca["eigengap_1_2"] == 1.0
    assert pca["pc1_explained_variance_pct"] == round(100 * 2 / 3, 6)
    assert pca["temporal_alignment"]["classification"] == "STABLE"
    assert meth["anova"]["f_statistic"] == 2.5 and meth["anova"]["p_value"] is None
    bt = meth["bradley_terry"]
    assert bt["status"] == "SYNTHETIC_REFERENCE_ONLY" and bt["comparison_n"] == 6
    assert [(c["a"], c["b"]) for c in bt["pairwise_probabilities"]] == [("A", "B"), ("A", "C"), ("B", "C")]
    assert meth["manova"]["provider_schema"] == "fake.manova.v1"
    assert meth["manova"]["independence_authenticated"] is None
    assert out["numerical_reference_is_process_inference"] is False


def test_pca_without_temporal_and_single_eigenvalue(provider, monkeypatch):
    monkeypatch.setenv("CW_W9_EIG", "1")
    req = request()
    del req["reference_data"]["pca_reference_rows"]
    out = m.evaluate(req, provider_root=provider[0])
    assert out["methods"]["pca"]["eigengap_1_2"] is None
    assert out["methods"]["pca"]["temporal_alignment"] is None


def test_nothing_eligible_holds_every_method(provider):
    req = request()
    d = req["design"]
    d.update(successes=None, eigenspace_diagnostics_pass=False, residual_diagnostics_pass=False,
             finite_bt_fit_conditions=False)
    out = m.evaluate(req, provider_root=provider[0])
    meth = out["methods"]
    for k in ("wilson", "pca", "anova", "bradley_terry"):
        assert meth[k] == {"status": "HOLD_UNQUALIFIED"}
    assert meth["manova"]["status"] == "HOLD_DESIGN_NOT_QUALIFIED"
    assert meth["manova"]["requested_eligibility"] == "HOLD_DESIGN_NOT_QUALIFIED"


@pytest.mark.parametrize("mutate, msg", [
    (lambda d: d["pca_rows"].pop(), "PCA observations"),
    (lambda d: d.__setitem__("pca_rows", "x"), "PCA observations"),
    (lambda d: d["pca_rows"][0].pop(), "PCA observations"),
    (lambda d: d["pca_reference_rows"][0].pop(), "temporal PCA"),
    (lambda d: d.__setitem__("pca_reference_rows", "x"), "temporal PCA"),
    (lambda d: d["anova_groups"][0].pop(), "ANOVA group replication"),
    (lambda d: d.__setitem__("anova_groups", None), "ANOVA group replication"),
    (lambda d: d["winner_loser_pairs"].pop(), "BT pairwise"),
    (lambda d: d["manova_groups"].pop(), "MANOVA multivariate"),
    (lambda d: d["manova_groups"][1].pop(), "MANOVA multivariate"),
    (lambda d: d["manova_groups"][2][0].pop(), "MANOVA multivariate"),
    (lambda d: d.__setitem__("manova_groups", {}), "MANOVA multivariate"),
])
def test_reference_geometry_mismatch_fails_closed(provider, mutate, msg):
    req = request()
    mutate(req["reference_data"])
    with pytest.raises(ValueError, match=msg):
        m.evaluate(req, provider_root=provider[0])


def test_undefined_anova_f_rejected(provider, monkeypatch):
    monkeypatch.setenv("CW_W9_NAN_F", "1")
    with pytest.raises(ValueError, match="undefined ANOVA F"):
        m.evaluate(request(), provider_root=provider[0])


def test_bt_engine_hold_and_no_finite_mle(provider, monkeypatch):
    monkeypatch.setenv("CW_W9_BT", "DISCONNECTED")
    out = m.evaluate(request(), provider_root=provider[0])
    assert out["methods"]["bradley_terry"] == {"status": "HOLD_DISCONNECTED", "pairwise_probabilities": None}
    monkeypatch.delenv("CW_W9_BT")
    monkeypatch.setenv("CW_W9_FIT", "SEPARATED")
    out = m.evaluate(request(), provider_root=provider[0])
    assert out["methods"]["bradley_terry"] == {"status": "HOLD_NO_FINITE_MLE", "pairwise_probabilities": None}


# ------------------------------------------------------------------ main
def test_main_writes_sorted_receipt(tmp_path):
    req = request()
    req["data_class"] = "NATIVE_UNVERIFIED"
    src = tmp_path / "req.json"
    src.write_text(json.dumps(req), encoding="utf-8")
    out = tmp_path / "deep" / "out.json"
    assert m.main(["--input", str(src), "--out", str(out)]) == 0
    text = out.read_text(encoding="utf-8")
    assert text.endswith("\n") and json.loads(text)["schema"] == m.OUT


def test_main_with_provider(tmp_path, provider):
    src = tmp_path / "req.json"
    src.write_text(json.dumps(request()), encoding="utf-8")
    out = tmp_path / "out.json"
    assert m.main(["--input", str(src), "--provider-root", str(provider[0]), "--out", str(out)]) == 0
    assert json.loads(out.read_text(encoding="utf-8"))["provider_executed"] is True


def test_main_rejects_missing_linked_and_aliased_input(tmp_path):
    src = tmp_path / "req.json"
    with pytest.raises(ValueError, match="untrusted/linked"):
        m.main(["--input", str(src), "--out", str(tmp_path / "o.json")])
    src.write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="input output alias"):
        m.main(["--input", str(src), "--out", str(src)])
    link = tmp_path / "link.json"
    try:
        os.symlink(src, link)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks unavailable on this host")
    with pytest.raises(ValueError, match="untrusted/linked"):
        m.main(["--input", str(link), "--out", str(tmp_path / "o.json")])
