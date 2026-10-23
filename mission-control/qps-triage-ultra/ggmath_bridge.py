#!/usr/bin/env python3
"""Governed QPS TRIAGE bridge to pinned GBOGEB/gg_MATH math kernels.

The provider code is never vendored here.  Every bound file is fetched by the
exact 40-character provider SHA in ``ggmath_provider_binding_v1.json`` (or read
from a local provider checkout), SHA-256 verified, and executed from the
verified bytes only.  A digest mismatch, a missing file or an import outside the
bound closure fails closed with a ``DEFER_*`` status.

Adapters wrap kernel output in a ``qps-ggmath-bridge-output/v1`` envelope that
carries the provider identity, the kernel digests used and a ``threshold_kind``
per output.  ``authority_transfer`` is always false.  PCA outputs are never
Bradley-Terry evidence, and reverse-order BT trials must be independently
observed, never produced by swapping labels on forward trials.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.abc
import importlib.util
import json
import math
import os
import re
import sys
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence

HERE = Path(__file__).resolve().parent
BINDING_PATH = HERE / "ggmath_provider_binding_v1.json"
DEFAULT_CACHE = HERE / ".ggmath_cache"
SHA40 = re.compile(r"[0-9a-f]{40}\Z")
SHA256 = re.compile(r"[0-9a-f]{64}\Z")
OUTPUT_SCHEMA = "qps-ggmath-bridge-output/v1"
RECEIPT_SCHEMA = "qps-ggmath-bridge-receipt/v1"
THRESHOLD_KINDS = frozenset({
    "EXACT_IDENTITY", "DISTRIBUTION_DERIVED", "MODEL_DERIVED", "DATA_CALIBRATED",
    "HEURISTIC", "PROJECT_GOVERNED", "NO_UNIVERSAL_THRESHOLD", "RESEARCH_TODO",
})
# Keys that may never be promoted by provider output, with the only admissible values.
NO_PROMOTION = {
    "authority_transfer": (False,),
    "engineering_acceptance": (False, None),
    "qps_acceptance": (False, None),
    "qps_owner_acceptance": (False, None),
    "six_sigma_achievement_proven": (False,),
    "global_stability_proven": (False,),
    "hard_gate_compensation_allowed": (False,),
    "pca_loading_sign_is_physical_polarity": (False,),
}
PCA_MARKER_KEYS = frozenset({
    "loadings", "scores", "components_columns", "eigenvalues", "explained_variance_ratio",
    "pc", "pc_score", "pc_scores", "pca", "pca_score",
})
MIN_PCA_ROWS = 3  # metric_registry.yaml analytics.pca.minimum_observations


class BridgeHold(Exception):
    """Fail-closed governance stop; ``status`` is always a DEFER_* token."""

    def __init__(self, status: str, detail: str = ""):
        super().__init__(f"{status}: {detail}" if detail else status)
        self.status = status
        self.detail = detail


def _require(ok: bool, status: str, detail: str = "") -> None:
    if not ok:
        raise BridgeHold(status, detail)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_text(path: Path) -> str:
    """Digest of a committed text file as git stores it (LF), stable on autocrlf checkouts."""
    return sha256_bytes(Path(path).read_bytes().replace(b"\r\n", b"\n"))


# --------------------------------------------------------------------------- binding

def validate_binding(binding: dict) -> dict:
    bad = "DEFER_BINDING_INVALID"
    _require(isinstance(binding, dict) and binding.get("schema") == "qps-ggmath-provider-binding/v1", bad, "schema")
    _require(binding.get("provider_repo") == "GBOGEB/gg_MATH", bad, "provider repo")
    _require(isinstance(binding.get("provider_sha"), str) and SHA40.fullmatch(binding["provider_sha"]) is not None,
             bad, "provider_sha must be exact 40-hex")
    _require(binding.get("authority_transfer") is False, bad, "authority_transfer must be false")
    _require(binding.get("engineering_acceptance") is False, bad, "engineering_acceptance must be false")
    _require(binding.get("boundaries", {}).get("pca_outputs_are_bt_evidence") is False, bad, "PCA/BT boundary")
    _require(binding["boundaries"].get("reverse_trials_from_swapped_labels") is False, bad, "reverse-trial boundary")
    entries = list(binding.get("bridged_kernels", [])) + list(binding.get("provider_data", []))
    _require(len(entries) > 0, bad, "no bound files")
    seen = set()
    for entry in entries:
        path = entry.get("path")
        _require(isinstance(path, str) and path and not path.startswith(("/", "\\")) and ".." not in path.split("/"),
                 bad, f"path {path!r}")
        _require(path not in seen, bad, f"duplicate path {path}")
        seen.add(path)
        _require(isinstance(entry.get("sha256"), str) and SHA256.fullmatch(entry["sha256"]) is not None,
                 bad, f"sha256 for {path}")
    for name, spec in binding.get("outputs", {}).items():
        _require(spec.get("threshold_kind") in THRESHOLD_KINDS, bad, f"threshold_kind for {name}")
    return binding


def load_binding(path: Path = BINDING_PATH) -> dict:
    return validate_binding(json.loads(Path(path).read_text(encoding="utf-8")))


def _bound_entries(binding: dict) -> list[dict]:
    return list(binding["bridged_kernels"]) + list(binding.get("provider_data", []))


def _raw_url(binding: dict, path: str, sha: str | None = None) -> str:
    template = binding["fetch"]["raw_url_template"]
    return template.format(repo=binding["provider_repo"], sha=sha or binding["provider_sha"], path=path)


def _http_fetch(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=30) as response:  # noqa: S310 - fixed https template
        return response.read()


def fetch_provider(
    binding: dict,
    *,
    cache: Path | None = None,
    provider_root: Path | None = None,
    fetcher: Callable[[str], bytes] | None = None,
) -> Path:
    """Materialise every bound file under ``cache/<sha>/`` after digest verification.

    Bytes are written only after their SHA-256 matches the binding, so the cache
    never holds unverified provider code.
    """
    validate_binding(binding)
    cache = Path(cache or os.environ.get(binding["fetch"]["cache_env"]) or DEFAULT_CACHE)
    env_root = os.environ.get(binding["fetch"]["provider_root_env"])
    provider_root = Path(provider_root) if provider_root else (Path(env_root) if env_root else None)
    fetcher = fetcher or _http_fetch
    root = cache / binding["provider_sha"]
    for entry in _bound_entries(binding):
        target = root / entry["path"]
        if target.is_file() and sha256_bytes(target.read_bytes()) == entry["sha256"]:
            continue
        if provider_root is not None:
            source = provider_root / entry["path"]
            _require(source.is_file(), "DEFER_PROVIDER_FILE_MISSING", entry["path"])
            data = source.read_bytes()
        else:
            try:
                data = fetcher(_raw_url(binding, entry["path"]))
            except OSError as exc:
                raise BridgeHold("DEFER_PROVIDER_FETCH_FAILED", f"{entry['path']}: {exc}") from exc
        got = sha256_bytes(data)
        _require(got == entry["sha256"], "DEFER_PROVIDER_DIGEST_MISMATCH",
                 f"{entry['path']} expected {entry['sha256']} got {got}")
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_name(target.name + ".partial")
        tmp.write_bytes(data)
        tmp.replace(target)
    return root


def verify_provider(binding: dict, root: Path) -> dict[str, bytes]:
    """Re-hash every bound file under ``root``; return the verified bytes by path."""
    verified = {}
    for entry in _bound_entries(binding):
        target = Path(root) / entry["path"]
        _require(target.is_file(), "DEFER_PROVIDER_FILE_MISSING", entry["path"])
        data = target.read_bytes()
        got = sha256_bytes(data)
        _require(got == entry["sha256"], "DEFER_PROVIDER_DIGEST_MISMATCH",
                 f"{entry['path']} expected {entry['sha256']} got {got}")
        verified[entry["path"]] = data
    return verified


# --------------------------------------------------------------------------- pinned import

class _PinnedKernelFinder(importlib.abc.MetaPathFinder, importlib.abc.Loader):
    """Serve ``kernels`` / ``kernels.<name>`` only from digest-verified bytes."""

    def __init__(self, sha: str, sources: dict[str, bytes]):
        self.sha = sha
        self.sources = sources  # module name -> verified bytes

    def find_spec(self, fullname, path=None, target=None):
        if fullname == "kernels":
            return importlib.util.spec_from_loader(fullname, self, is_package=True)
        if fullname.startswith("kernels."):
            if fullname not in self.sources:
                raise ImportError(f"DEFER_UNBOUND_PROVIDER_MODULE: {fullname} is outside the pinned closure")
            return importlib.util.spec_from_loader(fullname, self, origin=f"gg_MATH@{self.sha}/{fullname}")
        return None

    def create_module(self, spec):
        return None

    def exec_module(self, module):
        module.__ggmath_sha__ = self.sha
        if module.__name__ == "kernels":
            module.__path__ = []
            return
        source = self.sources[module.__name__]
        relative = module.__name__.replace(".", "/") + ".py"
        exec(compile(source, f"gg_MATH@{self.sha[:12]}/{relative}", "exec"), module.__dict__)  # noqa: S102


class ProviderKernels:
    """Verified, importable view of the pinned provider kernels."""

    def __init__(self, binding: dict, root: Path):
        self.binding = validate_binding(binding)
        self.sha = binding["provider_sha"]
        self.root = Path(root)
        verified = verify_provider(binding, self.root)
        self.digests = {e["path"]: e["sha256"] for e in _bound_entries(binding)}
        self._sources = {
            path[:-3].replace("/", "."): data
            for path, data in verified.items()
            if path.startswith("kernels/") and path.endswith(".py")
        }
        self._data = {path: data for path, data in verified.items() if not path.startswith("kernels/")}
        self._install()

    def _install(self) -> None:
        existing = sys.modules.get("kernels")
        if existing is not None and getattr(existing, "__ggmath_sha__", None) != self.sha:
            raise BridgeHold("DEFER_KERNEL_NAMESPACE_COLLISION",
                             "a different 'kernels' package is already imported in this process")
        for finder in [f for f in sys.meta_path if isinstance(f, _PinnedKernelFinder)]:
            if finder.sha != self.sha:
                raise BridgeHold("DEFER_KERNEL_NAMESPACE_COLLISION", f"pinned finder for {finder.sha} active")
            return
        sys.meta_path.insert(0, _PinnedKernelFinder(self.sha, self._sources))

    def module(self, name: str):
        full = f"kernels.{name}"
        if full not in self._sources:
            raise BridgeHold("DEFER_UNBOUND_PROVIDER_MODULE", full)
        try:
            return importlib.import_module(full)
        except ImportError as exc:
            raise BridgeHold("DEFER_UNBOUND_PROVIDER_MODULE", str(exc)) from exc

    def data(self, data_id: str) -> Any:
        entry = next((e for e in self.binding.get("provider_data", []) if e["id"] == data_id), None)
        _require(entry is not None, "DEFER_UNBOUND_PROVIDER_DATA", data_id)
        raw = self._data[entry["path"]]
        return json.loads(raw.decode("utf-8")) if entry["path"].endswith(".json") else raw.decode("utf-8")

    def kernel_digests(self, *names: str) -> dict[str, str]:
        return {f"kernels/{n}.py": self.digests[f"kernels/{n}.py"] for n in names}


_LOADED: dict[str, ProviderKernels] = {}


def load_kernels(binding: dict | None = None, **fetch_kwargs) -> ProviderKernels:
    binding = binding or load_binding()
    root = fetch_provider(binding, **fetch_kwargs)
    pk = ProviderKernels(binding, root)
    _LOADED[pk.sha] = pk
    return pk


def unload_kernels() -> None:
    """Remove the pinned finder and every ``kernels.*`` module from this process."""
    for finder in [f for f in sys.meta_path if isinstance(f, _PinnedKernelFinder)]:
        sys.meta_path.remove(finder)
    for name in [n for n in sys.modules if n == "kernels" or n.startswith("kernels.")]:
        del sys.modules[name]
    _LOADED.clear()


# --------------------------------------------------------------------------- envelope

def assert_no_promotion(obj: Any, where: str = "$") -> None:
    """Recursively reject any provider attempt to promote authority or acceptance."""
    if isinstance(obj, dict):
        for key, value in obj.items():
            if key in NO_PROMOTION and value not in NO_PROMOTION[key]:
                raise BridgeHold("DEFER_AUTHORITY_PROMOTION_REJECTED", f"{where}.{key}={value!r}")
            if key == "merge_admission" and value not in ("HOLD", None):
                raise BridgeHold("DEFER_AUTHORITY_PROMOTION_REJECTED", f"{where}.merge_admission={value!r}")
            if key == "formal_credit_delta" and value not in (0, None):
                raise BridgeHold("DEFER_AUTHORITY_PROMOTION_REJECTED", f"{where}.formal_credit_delta={value!r}")
            assert_no_promotion(value, f"{where}.{key}")
    elif isinstance(obj, (list, tuple)):
        for i, value in enumerate(obj):
            assert_no_promotion(value, f"{where}[{i}]")


def jsonable(value: Any, digits: int = 12) -> Any:
    """Convert numpy/tuple output to plain JSON with stable float precision."""
    if hasattr(value, "tolist") and not isinstance(value, (str, bytes)):
        value = value.tolist()
    if isinstance(value, dict):
        return {str(k): jsonable(v, digits) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonable(v, digits) for v in value]
    if isinstance(value, bool) or value is None or isinstance(value, (str, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            return None
        return float(f"{value:.{digits}g}")
    if hasattr(value, "item"):
        return jsonable(value.item(), digits)
    return str(value)


def envelope(pk: ProviderKernels, adapter: str, outputs: Sequence[str], status: str,
             result: dict, kernels: Sequence[str]) -> dict:
    _require(status.startswith(("PASS", "DEFER", "RESEARCH_TODO")), "DEFER_BRIDGE_STATUS_INVALID", status)
    assert_no_promotion(result)
    spec = pk.binding["outputs"]
    threshold_kind = {}
    for name in outputs:
        _require(name in spec and spec[name]["adapter"] == adapter, "DEFER_BINDING_INVALID", f"output {name}")
        threshold_kind[name] = spec[name]["threshold_kind"]
    return {
        "schema": OUTPUT_SCHEMA,
        "adapter": adapter,
        "status": status,
        "threshold_kind": threshold_kind,
        "provider": {"repo": pk.binding["provider_repo"], "sha": pk.sha},
        "kernels": pk.kernel_digests(*kernels),
        "result": jsonable(result),
        "bt_admissible": False if adapter.startswith(("pca", "rmt", "temporal")) else None,
        "authority_transfer": False,
        "engineering_acceptance": False,
    }


# --------------------------------------------------------------------------- Bradley-Terry

def _looks_pca_derived(record: dict) -> bool:
    if record.get("bt_admissible") is False:
        return True
    if PCA_MARKER_KEYS.intersection(record):
        return True
    schema = str(record.get("schema", "")).lower()
    tags = " ".join(str(record.get(k, "")) for k in ("outcome_source", "derived_from", "adapter")).lower()
    return "pca" in schema or "pca" in tags or "rmt" in tags


def admit_bt_records(records: Iterable[dict], admissible_sources: Sequence[str]) -> list[dict]:
    """Admit only measured, explicitly observed comparisons into BT."""
    admitted = []
    for i, record in enumerate(records):
        _require(isinstance(record, dict), "DEFER_BT_RECORD_NOT_OBJECT", f"record {i}")
        if _looks_pca_derived(record):
            raise BridgeHold("DEFER_PCA_DERIVED_WIN_REJECTED", f"record {i} carries PCA/RMT provenance")
        _require(record.get("outcome_source") in admissible_sources, "DEFER_BT_OUTCOME_SOURCE_NOT_OBSERVED",
                 f"record {i}: {record.get('outcome_source')!r}")
        _require(record.get("evidence_class") == "MEASURED", "DEFER_BT_NON_MEASURED_EVIDENCE", f"record {i}")
        admitted.append(record)
    return admitted


def w3_pairs_for_bt(observations: dict) -> list[dict]:
    """Current-frontier W3 pairs, admitted only after the hub's own W3-15 pair rules pass."""
    import w3_bt_gate  # local hub module: identical validation to the W3-15 gate

    policy = observations.get("policy", {})
    pairs = observations.get("current_frontier", {}).get("pairs", [])
    failures = w3_bt_gate.validate_current_pairs(pairs, policy)
    _require(not failures, "DEFER_PAIR_EVIDENCE_VALIDATION_FAILED", json.dumps(failures, sort_keys=True))
    return [dict(p, outcome_source="OBSERVED_PAIRWISE_OUTCOME") for p in pairs]


def bt_strength(pk: ProviderKernels, records: Iterable[dict], *, level: float = 0.95, resamples: int = 500,
                seed: int = 20260921, penalty: float = 0.1) -> dict:
    """BT strengths with Wald intervals and bootstrap rank frequency.

    A classical MLE is reported only when the directed win graph is strongly
    connected.  Otherwise the status is DEFER_NO_FINITE_MLE and the penalized fit
    is attached under its own label; it is never substituted for the MLE.
    """
    bt = pk.module("bt_uncertainty")
    admitted = admit_bt_records(records, pk.binding["boundaries"]["bt_admissible_outcome_sources"])
    _require(len(admitted) > 0, "DEFER_NO_USABLE_COMPARISONS")
    pairs = [[r["winner"], r["loser"]] for r in admitted]
    guard = bt.finite_mle_guard(pairs)
    classical = bt.fit_bradley_terry(pairs, penalty=0.0)
    fit = classical if classical["status"] == "PASS" else bt.fit_bradley_terry(pairs, penalty=penalty)
    intervals = bt.log_strength_intervals(fit, level=level)
    ranks = bt.bootstrap_ranking_stability(pairs, resamples=resamples, seed=seed, penalty=penalty)
    status = "PASS_CLASSICAL_BT_MLE" if classical["status"] == "PASS" else "DEFER_NO_FINITE_MLE"
    result = {
        "comparisons": len(pairs),
        "finite_mle_guard": guard,
        "reported_fit": {k: fit[k] for k in ("fit_kind", "penalty", "names", "scores", "log_strengths",
                                             "covariance_kind", "log_likelihood")},
        "reported_fit_is_classical_mle": classical["status"] == "PASS",
        "log_strength_intervals": intervals,
        "rank_frequency": ranks,
        "comparison_semantics": "explicit observed winner/loser outcomes only",
    }
    return envelope(pk, "bt_strength", ("bt_finite_mle_guard", "bt_log_strength_intervals", "bt_rank_frequency"),
                    status, result, ("bt_uncertainty", "uncertainty"))


def bt_order_effect(pk: ProviderKernels, trials: Iterable[dict], *, level: float = 0.95) -> dict:
    """Presentation-order effect from forward and independently observed reverse trials.

    Each trial is ``{trial_id, observation_id, pair_id, order, first, second,
    winner, outcome_source, evidence_class}``.  A REVERSE trial must be its own
    observation (``observed_independently`` true, distinct ``observation_id``) with
    the presentation order of its FORWARD partner reversed.  Reverse trials made
    by swapping labels on forward trials are rejected.
    """
    stats = pk.module("stats_core")
    bt = pk.module("bt_uncertainty")
    trials = admit_bt_records(trials, pk.binding["boundaries"]["bt_admissible_outcome_sources"])
    trial_ids, observation_ids, forward_orient = set(), {}, {}
    for t in trials:
        tid, oid = t.get("trial_id"), t.get("observation_id")
        _require(isinstance(tid, str) and tid and tid not in trial_ids, "DEFER_TRIAL_IDENTITY_INVALID", repr(tid))
        trial_ids.add(tid)
        _require(t.get("order") in ("FORWARD", "REVERSE"), "DEFER_TRIAL_ORDER_INVALID", tid)
        _require(t.get("winner") in (t.get("first"), t.get("second")) and t.get("first") != t.get("second"),
                 "DEFER_TRIAL_WINNER_INVALID", tid)
        if t.get("label_swapped") or t.get("derived_from_trial") or t.get("derived_by"):
            raise BridgeHold("DEFER_SWAPPED_LABEL_REVERSE_REJECTED", tid)
        _require(isinstance(oid, str) and oid, "DEFER_REVERSE_TRIAL_NOT_INDEPENDENT", f"{tid} lacks observation_id")
        if oid in observation_ids:
            raise BridgeHold("DEFER_REVERSE_TRIAL_NOT_INDEPENDENT",
                             f"{tid} reuses observation {oid} of {observation_ids[oid]}")
        observation_ids[oid] = tid
        if t["order"] == "REVERSE":
            _require(t.get("observed_independently") is True, "DEFER_REVERSE_TRIAL_NOT_INDEPENDENT", tid)
        else:
            orient = (t["first"], t["second"])
            _require(forward_orient.setdefault(t["pair_id"], orient) == orient,
                     "DEFER_ORDER_ORIENTATION_MISMATCH", tid)
    by_pair: dict[str, dict[str, list[dict]]] = {}
    for t in trials:
        if t["order"] == "REVERSE":
            fwd = forward_orient.get(t["pair_id"])
            _require(fwd is None or (t["first"], t["second"]) == (fwd[1], fwd[0]),
                     "DEFER_ORDER_ORIENTATION_MISMATCH", t["trial_id"])
        by_pair.setdefault(t["pair_id"], {"FORWARD": [], "REVERSE": []})[t["order"]].append(t)
    balanced = sorted(p for p, v in by_pair.items() if v["FORWARD"] and v["REVERSE"])
    per_pair = []
    first_wins = total = 0
    for pair_id in balanced:
        rows = by_pair[pair_id]
        fw = sum(t["winner"] == t["first"] for t in rows["FORWARD"])
        rv = sum(t["winner"] == t["first"] for t in rows["REVERSE"])
        first_wins += fw + rv
        total += len(rows["FORWARD"]) + len(rows["REVERSE"])
        per_pair.append({
            "pair_id": pair_id,
            "forward_orientation": list(forward_orient[pair_id]),
            "forward_trials": len(rows["FORWARD"]), "forward_first_position_wins": fw,
            "reverse_trials": len(rows["REVERSE"]), "reverse_first_position_wins": rv,
            "same_winner_both_orders": len({t["winner"] for t in rows["FORWARD"] + rows["REVERSE"]}) == 1,
        })
    pairs = [[t["winner"], t["first"] if t["winner"] == t["second"] else t["second"]] for t in trials]
    result = {
        "trials": len(trials),
        "pairs_with_forward_and_reverse": len(balanced),
        "pairs_missing_independent_reverse": sorted(p for p in by_pair if p not in balanced),
        "per_pair": per_pair,
        "finite_mle_guard": bt.finite_mle_guard(pairs),
        "reverse_trial_rule": "INDEPENDENTLY_OBSERVED_ONLY_NEVER_SWAPPED_LABELS",
    }
    if not balanced:
        return envelope(pk, "bt_order_effect", ("bt_order_effect",), "DEFER_NO_INDEPENDENT_REVERSE_TRIALS",
                        result, ("stats_core", "bt_uncertainty"))
    wilson = stats.wilson_proportion_interval(first_wins, total, level=level)
    lo, hi = wilson["interval"]
    result["first_position_win_rate"] = wilson
    result["order_effect_pp"] = 100.0 * (wilson["estimate"] - 0.5)
    status = "PASS_ORDER_EFFECT_DETECTED" if (hi < 0.5 or lo > 0.5) else "PASS_ORDER_EFFECT_NOT_RESOLVED"
    return envelope(pk, "bt_order_effect", ("bt_order_effect",), status, result, ("stats_core", "bt_uncertainty"))


def bt_reverse_pressure(pk: ProviderKernels, pulses: dict, *, penalty: float = 0.1) -> dict:
    """Runtime reverse-pressure BT over measured lane queue waits (longer wait wins).

    Uses GM-I-A ``bt_gate`` policy; it ranks queue pressure, not intervention
    superiority, and is never fed by PCA output.
    """
    bt = pk.module("bt_uncertainty")
    gate = pulses.get("bt_gate", {})
    rows = [r for r in pulses.get("rows", []) if r.get("evidence_class") == "MEASURED"]
    _require(pulses.get("authority_transfer") is False, "DEFER_AUTHORITY_PROMOTION_REJECTED", "pulse document")
    lanes = sorted(f[: -len("_queue_seconds")] for f in pulses.get("features", []) if f.endswith("_queue_seconds"))
    records = []
    for row in rows:
        for i, a in enumerate(lanes):
            for b in lanes[i + 1:]:
                qa, qb = row.get(f"{a}_queue_seconds"), row.get(f"{b}_queue_seconds")
                if not all(isinstance(q, (int, float)) and not isinstance(q, bool) for q in (qa, qb)):
                    raise BridgeHold("DEFER_MISSING_MEASUREMENT_NO_IMPUTATION", f"{row.get('pulse_id')} {a}/{b}")
                if qa == qb:
                    continue
                win, lose = (a, b) if qa > qb else (b, a)
                records.append({"winner": win, "loser": lose, "pulse_id": row["pulse_id"],
                                "outcome_source": "MEASURED_DURATION_COMPARISON", "evidence_class": "MEASURED"})
    admit_bt_records(records, pk.binding["boundaries"]["bt_admissible_outcome_sources"])
    minimum = int(gate.get("minimum_repeat_pulses", 3))
    result = {"lanes": lanes, "measured_pulses": len(rows), "minimum_repeat_pulses": minimum,
              "comparisons": len(records), "comparison_semantics": gate.get("comparison_semantics"),
              "interpretation": gate.get("interpretation")}
    if len(rows) < minimum:
        return envelope(pk, "bt_reverse_pressure", ("bt_reverse_pressure",), "DEFER_INSUFFICIENT_REPEAT_PULSES",
                        result, ("bt_uncertainty",))
    pairs = [[r["winner"], r["loser"]] for r in records]
    guard = bt.finite_mle_guard(pairs, name_universe=lanes)
    result["finite_mle_guard"] = guard
    if guard["status"] != "PASS_FINITE_MLE_CONDITION":
        result["penalized_diagnostic"] = bt.fit_bradley_terry(pairs, penalty=penalty, name_universe=lanes)
        return envelope(pk, "bt_reverse_pressure", ("bt_reverse_pressure",), "DEFER_NO_FINITE_MLE",
                        result, ("bt_uncertainty",))
    result["fit"] = bt.fit_bradley_terry(pairs, penalty=0.0, name_universe=lanes)
    return envelope(pk, "bt_reverse_pressure", ("bt_reverse_pressure",), "PASS_REVERSE_PRESSURE_BT",
                    result, ("bt_uncertainty",))


# --------------------------------------------------------------------------- PCA / RMT

def _numeric_rows(rows: Sequence[Sequence[float]]) -> list[list[float]]:
    out = []
    for i, row in enumerate(rows):
        values = []
        for v in row:
            if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(float(v)):
                raise BridgeHold("DEFER_NON_NUMERIC_PCA_INPUT", f"row {i}")
            values.append(float(v))
        out.append(values)
    _require(len({len(r) for r in out}) == 1 and out and len(out[0]) >= 2, "DEFER_PCA_SHAPE_INVALID")
    return out


def rmt_calibration(pk: ProviderKernels, rows, *, evidence_class: str, simulations: int = 200,
                    seed: int = 0) -> dict:
    rmt = pk.module("rmt_calibration")
    _require(evidence_class == "MEASURED", "DEFER_NON_MEASURED_PCA_INPUT", evidence_class)
    x = _numeric_rows(rows)
    if len(x) < MIN_PCA_ROWS:
        return envelope(pk, "rmt_calibration", ("rmt_finite_sample_calibration",),
                        "DEFER_INSUFFICIENT_OBSERVATIONS", {"n": len(x), "minimum": MIN_PCA_ROWS},
                        ("rmt_calibration", "rmt_signal", "pca_reference", "matrix_core", "stats_core"))
    try:
        cal = rmt.finite_sample_rmt_calibration(x, simulations=simulations, seed=seed, scale=True)
    except (ValueError, ZeroDivisionError) as exc:
        return envelope(pk, "rmt_calibration", ("rmt_finite_sample_calibration",), "DEFER_NUMERICAL_DEGENERACY",
                        {"reason": str(exc)}, ("rmt_calibration",))
    return envelope(pk, "rmt_calibration", ("rmt_finite_sample_calibration",), "PASS_RMT_CALIBRATION_DIAGNOSTIC",
                    cal, ("rmt_calibration", "rmt_signal", "pca_reference", "matrix_core", "stats_core"))


def pca_retention(pk: ProviderKernels, rows, features: Sequence[str], *, evidence_class: str,
                  simulations: int = 200, seed: int = 0, resamples: int = 300) -> dict:
    """Scree with MP edge and PA95, eigengap guard and bootstrap subspace uncertainty."""
    pcau = pk.module("pca_uncertainty")
    kernels = ("rmt_calibration", "rmt_signal", "pca_reference", "pca_uncertainty", "matrix_core", "stats_core")
    outputs = ("pca_mp_edge", "pca_pa95", "pca_eigengap_guard", "pca_bootstrap_subspace")
    cal = rmt_calibration(pk, rows, evidence_class=evidence_class, simulations=simulations, seed=seed)
    x = _numeric_rows(rows)
    n, p = len(x), len(x[0])
    _require(len(features) == p, "DEFER_PCA_SHAPE_INVALID", "feature names")
    adequacy = n >= max(10, 3 * p)
    base = {"features": list(features), "n": n, "p": p, "sample_adequacy_rule": "n >= max(10, 3*p)",
            "sample_adequate": adequacy, "bt_admissible": False}
    if not cal["status"].startswith("PASS"):
        return envelope(pk, "pca_retention", outputs, cal["status"], {**base, "calibration": cal["result"]}, kernels)
    c = cal["result"]
    retained = 0
    for flag in c["pa_retained_candidate"]:
        if not flag:
            break
        retained += 1
    k = max(1, retained)
    gap = pcau.eigengap_diagnostics(c["observed_eigenvalues"], components=k)
    try:
        boot = pcau.bootstrap_pca_uncertainty(x, components=k, resamples=resamples, seed=20260921)
    except ValueError as exc:
        boot = {"status": "DEFER_BOOTSTRAP_REJECTED", "reason": str(exc)}
    scree = {
        "observed_eigenvalues": c["observed_eigenvalues"],
        "mp_upper_asymptotic": c["mp_upper_asymptotic"],
        "mp_lower_asymptotic": c["mp_lower_asymptotic"],
        "pa95_component_thresholds": c["pa95_component_thresholds"],
        "pa_retained_candidate": c["pa_retained_candidate"],
        "leading_retained_candidates": retained,
    }
    if not adequacy:
        status = "DEFER_BELOW_SAMPLE_ADEQUACY_DESCRIPTIVE_ONLY"
    elif boot.get("status") != "PASS":
        status = "DEFER_" + str(boot.get("status", "BOOTSTRAP")).removeprefix("DEFER_")
    elif gap["status"] != "PASS_EIGENGAP_GUARD":
        status = gap["status"]
    else:
        status = "PASS_PCA_RETENTION_DIAGNOSTIC"
    return envelope(pk, "pca_retention", outputs, status,
                    {**base, "scree": scree, "eigengap": gap, "bootstrap": boot, "calibration_guard": c["guard"]},
                    kernels)


def pca_alignment(pk: ProviderKernels, reference_rows, current_rows, *, components: int, evidence_class: str,
                  resamples: int = 300) -> dict:
    """Component assignment/sign alignment plus subspace uncertainty between two windows."""
    ref_mod = pk.module("pca_reference")
    align = pk.module("pca_alignment")
    pcau = pk.module("pca_uncertainty")
    kernels = ("pca_reference", "pca_alignment", "pca_uncertainty", "matrix_core", "stats_core")
    outputs = ("pca_alignment_congruence", "pca_temporal_subspace_uncertainty")
    _require(evidence_class == "MEASURED", "DEFER_NON_MEASURED_PCA_INPUT", evidence_class)
    a, b = _numeric_rows(reference_rows), _numeric_rows(current_rows)
    if min(len(a), len(b)) < MIN_PCA_ROWS:
        return envelope(pk, "pca_alignment", outputs, "DEFER_INSUFFICIENT_OBSERVATIONS",
                        {"n_reference": len(a), "n_current": len(b)}, kernels)
    try:
        fit_a = ref_mod.pca_reference(a, scale=True, components=components)
        fit_b = ref_mod.pca_reference(b, scale=True, components=components)
        aligned = align.align_pca_fits(fit_a, fit_b)
        temporal = pcau.temporal_subspace_uncertainty(a, b, components=components, resamples=resamples, scale=True)
    except ValueError as exc:
        return envelope(pk, "pca_alignment", outputs, "DEFER_NUMERICAL_DEGENERACY", {"reason": str(exc)}, kernels)
    if aligned["any_component_identity_ambiguous"]:
        status = "DEFER_COMPONENT_IDENTITY_AMBIGUOUS"
    elif temporal.get("status") != "PASS":
        status = "DEFER_" + str(temporal.get("status")).removeprefix("DEFER_")
    else:
        status = "PASS_PCA_ALIGNMENT_DIAGNOSTIC"
    return envelope(pk, "pca_alignment", outputs, status,
                    {"alignment": aligned, "temporal_subspace": temporal, "bt_admissible": False}, kernels)


# --------------------------------------------------------------------------- temporal / convergence

def _epoch(t: str) -> float:
    dt = datetime.fromisoformat(str(t).replace("Z", "+00:00"))
    _require(dt.tzinfo is not None, "DEFER_CLOCK_INVALID", f"{t} lacks timezone")
    return dt.timestamp()


def temporal_trace(pk: ProviderKernels, states: Sequence[dict], *, evidence_class: str) -> dict:
    """Principal-angle / Grassmann history over ordered retained subspaces.

    Each state carries ``k`` (event index), ``t`` (ISO-8601 with timezone),
    ``a`` (cumulative exposure) and either ``basis`` or measured ``rows`` plus
    ``components``.  Event, wall and exposure clocks stay separate.
    """
    trace_mod = pk.module("temporal_subspace_trace")
    receipt_mod = pk.module("temporal_pca_receipt")
    ref_mod = pk.module("pca_reference")
    kernels = ("temporal_subspace_trace", "temporal_pca_receipt", "subspace_metrics", "pca_reference",
               "matrix_core", "stats_core")
    _require(evidence_class in ("MEASURED", "SYNTHETIC_REFERENCE"), "DEFER_EVIDENCE_CLASS_INVALID", evidence_class)
    _require(len(states) >= 2, "DEFER_INSUFFICIENT_TEMPORAL_DEPTH", f"{len(states)} states")
    clocks, prepared = [], []
    try:
        for s in states:
            clock = receipt_mod.StateClock(k=s["k"], t=s["t"], a=s["a"], wave=s.get("wave"), pulse=s.get("pulse"))
            basis = s.get("basis")
            if basis is None:
                basis = ref_mod.pca_reference(_numeric_rows(s["rows"]), scale=True,
                                              components=int(s["components"]))["components_columns"]
            clocks.append(clock)
            prepared.append({"k": clock.k, "t": _epoch(clock.t), "a": clock.a, "basis": basis,
                             "eigenvalues": s.get("eigenvalues")})
        trace = trace_mod.temporal_subspace_trace(prepared)
        steps = [receipt_mod.multiclock_step(clocks[i], clocks[i + 1],
                                             distance=trace["adjacent"][i]["grassmann_geodesic_distance"])
                 for i in range(len(clocks) - 1)]
    except (KeyError, ValueError) as exc:
        return envelope(pk, "temporal_trace", ("temporal_subspace_trace",), "DEFER_TEMPORAL_INPUT_REJECTED",
                        {"reason": str(exc)}, kernels)
    return envelope(pk, "temporal_trace", ("temporal_subspace_trace",), "PASS_TEMPORAL_SUBSPACE_TRACE",
                    {"evidence_class": evidence_class, "trace": trace, "multiclock_steps": steps,
                     "bt_admissible": False}, kernels)


def convergence(pk: ProviderKernels, payload: dict) -> dict:
    """gg_MATH convergence classification plus a visual-series contract check."""
    conv = pk.module("convergence_control")
    visual = pk.module("visual_engine_bridge")
    kernels = ("convergence_control", "visual_engine_bridge")
    try:
        receipt = conv.assess_convergence(payload)
        obs = receipt["observations"]
        series_payload = {
            "schema": visual.SCHEMA,
            "source": {"repo": payload.get("source_repo", "UNKNOWN"), "head_sha": obs[-1]["sha"]},
            "authority": {"engineering_acceptance": False, "cross_repo_coverage_credit": None,
                          "merge_admission": "HOLD", "qps_owner_acceptance": None},
            "series": [{"id": "COVERAGE", "label": receipt["population_id"],
                        "points": [{"pulse": f"n{r['n']}", "state": "HISTORICAL", "value": r["covered"],
                                    "eligible": r["denominator"], "native_receipt": None} for r in obs]}],
        }
        visual.check(series_payload)
    except (KeyError, TypeError, ValueError) as exc:
        return envelope(pk, "convergence", ("convergence_classification",), "DEFER_CONVERGENCE_INPUT_REJECTED",
                        {"reason": str(exc)}, kernels)
    velocities = [
        {"from_n": a["n"], "to_n": b["n"], "velocity_pp_per_pulse": (b["coverage_pp"] - a["coverage_pp"]) / (b["n"] - a["n"])}
        for a, b in zip(obs, obs[1:])
    ]
    return envelope(pk, "convergence", ("convergence_classification",), "PASS_CONVERGENCE_CLASSIFIED",
                    {"receipt": receipt, "velocity_series": velocities,
                     "visual_series_contract": "PASS_" + visual.SCHEMA}, kernels)


def research_interfaces(pk: ProviderKernels) -> dict:
    bt = pk.module("bt_uncertainty")
    pcau = pk.module("pca_uncertainty")
    return envelope(pk, "research_interfaces", ("bt_bayesian", "grassmann_state_space"), "RESEARCH_TODO",
                    {"bayesian_bt": bt.bayesian_bradley_terry_interface(),
                     "grassmann_state_space": pcau.grassmann_state_space_interface()},
                    ("bt_uncertainty", "pca_uncertainty"))


# --------------------------------------------------------------------------- receipt

def _synthetic_trace_states(pk: ProviderKernels) -> list[dict]:
    """gg_MATH's own analytic rank-3/R^4 challenge: d_G equals |theta| exactly."""
    basis = pk.module("temporal_subspace_trace").rank3_r4_basis
    thetas = (0.0, 0.10, 0.25, 0.20, 0.35)
    return [{"k": i, "t": f"2026-10-0{i + 1}T00:00:00Z", "a": float(i * 10), "basis": basis(th),
             "pulse": f"SYN-{i}"} for i, th in enumerate(thetas)]


def _synthetic_convergence_payload() -> dict:
    covered = (40, 55, 63, 66, 66, 67, 67)
    shas = ["%040x" % (0xA11CE + i) for i in range(len(covered))]
    return {
        "schema": "gg_math.convergence_input.v1", "evidence_class": "SYNTHETIC_REFERENCE",
        "authority_transfer": False, "tolerance_pp": 1.5, "cap_tolerance_pp": 2.0,
        "source_repo": "SYNTHETIC/REFERENCE",
        "observations": [{"n": i, "k": k, "d": 100, "scope_id": "SYNTHETIC_REFERENCE_COHORT", "sha": shas[i],
                          "run_id": 1000 + i, "attempt": 1} for i, k in enumerate(covered)],
    }


def build_receipt(pk: ProviderKernels) -> dict:
    """Run every adapter on committed hub evidence (plus labelled gg_MATH reference challenges)."""
    import ggmath_flow_kpi

    telemetry = json.loads((HERE / "w3_fleet_telemetry.json").read_text(encoding="utf-8"))
    fields = telemetry["comparability_contract"]["required_common_numeric_fields"]
    rows = [[r[f] for f in fields] for r in telemetry["rows"]]
    observations = json.loads((HERE / "w3_bt_observations.json").read_text(encoding="utf-8"))
    pulses = pk.data("GM_I_A_MULTI_CLOCK_MEASURED_PULSES")
    ledger = json.loads((HERE / "analytics" / "EXPEDITION_FLEET_ITERATION_LEDGER_v1.json").read_text(encoding="utf-8"))
    variable = [j for j in range(len(fields)) if len({row[j] for row in rows}) > 1]
    pca_rows = [[row[j] for j in variable] for row in rows]

    def guarded(fn, *args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except BridgeHold as hold:
            return {"schema": OUTPUT_SCHEMA, "adapter": fn.__name__, "status": hold.status, "detail": hold.detail,
                    "authority_transfer": False, "engineering_acceptance": False}

    adapters = {
        "bt_strength_w3_current_frontier": guarded(lambda: bt_strength(pk, w3_pairs_for_bt(observations))),
        "bt_reverse_pressure_gm_i_a": guarded(bt_reverse_pressure, pk, pulses),
        "pca_retention_w3_fleet": guarded(pca_retention, pk, pca_rows, [fields[j] for j in variable],
                                          evidence_class="MEASURED"),
        "pca_retention_gm_i_a": guarded(pca_retention, pk, [[r[f] for f in pulses["features"]] for r in pulses["rows"]],
                                        pulses["features"], evidence_class="MEASURED"),
        "flow_kpi_gm_i_a": ggmath_flow_kpi.flow_kpi(ggmath_flow_kpi.jobs_from_gm_i_a(pulses),
                                                    source=pk.binding["provider_data"][0]["path"],
                                                    source_sha=pk.sha),
        "flow_kpi_fleet_ledger": ggmath_flow_kpi.flow_kpi(
            ggmath_flow_kpi.jobs_from_fleet_ledger(ledger),
            source="analytics/EXPEDITION_FLEET_ITERATION_LEDGER_v1.json", source_sha=None,
            excluded=ggmath_flow_kpi.excluded_from_fleet_ledger(ledger)),
        "research_interfaces": research_interfaces(pk),
    }
    reference = {
        "temporal_trace_rank3_r4": guarded(temporal_trace, pk, _synthetic_trace_states(pk),
                                           evidence_class="SYNTHETIC_REFERENCE"),
        "convergence_reference_cohort": guarded(convergence, pk, _synthetic_convergence_payload()),
    }
    receipt = {
        "schema": RECEIPT_SCHEMA,
        "provider": {"repo": pk.binding["provider_repo"], "sha": pk.sha},
        "binding_sha256": sha256_text(BINDING_PATH),
        "inputs": {
            "w3_fleet_telemetry.json": sha256_text(HERE / "w3_fleet_telemetry.json"),
            "w3_bt_observations.json": sha256_text(HERE / "w3_bt_observations.json"),
            "analytics/EXPEDITION_FLEET_ITERATION_LEDGER_v1.json":
                sha256_text(HERE / "analytics" / "EXPEDITION_FLEET_ITERATION_LEDGER_v1.json"),
            pk.binding["provider_data"][0]["path"]: pk.binding["provider_data"][0]["sha256"],
        },
        "measured": adapters,
        "reference_challenges": {
            "evidence_class": "SYNTHETIC_REFERENCE",
            "note": "Renderer and kernel challenges only; not QPS evidence and never promoted.",
            **reference,
        },
        "authority_transfer": False,
        "engineering_acceptance": False,
    }
    assert_no_promotion(receipt)
    return jsonable(receipt)


def rebind(binding: dict, new_sha: str, *, fetcher: Callable[[str], bytes] | None = None) -> dict:
    """Return a binding bumped to ``new_sha`` with every digest recomputed from that SHA."""
    _require(isinstance(new_sha, str) and SHA40.fullmatch(new_sha) is not None, "DEFER_BINDING_INVALID",
             "new sha must be exact 40-hex")
    fetcher = fetcher or _http_fetch
    out = json.loads(json.dumps(binding))
    out["provider_sha"] = new_sha
    out.pop("provider_tree_sha", None)
    for entry in out["bridged_kernels"] + out.get("provider_data", []):
        entry["sha256"] = sha256_bytes(fetcher(_raw_url(binding, entry["path"], new_sha)))
    return validate_binding(out)


def write_json(path: Path, value: dict) -> None:
    Path(path).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("fetch", help="fetch and digest-verify the pinned provider files")
    f.add_argument("--provider-root", type=Path)
    b = sub.add_parser("build", help="run all adapters and write the bridge receipt")
    b.add_argument("--provider-root", type=Path)
    b.add_argument("--out", type=Path, default=HERE / "ggmath_bridge_receipt.json")
    r = sub.add_parser("rebind", help="bump the binding to a new exact provider SHA")
    r.add_argument("--sha", required=True)
    args = ap.parse_args(argv)
    sys.path.insert(0, str(HERE))
    try:
        binding = load_binding()
        if args.cmd == "rebind":
            write_json(BINDING_PATH, rebind(binding, args.sha))
            print(f"rebound to {args.sha}")
            return 0
        pk = load_kernels(binding, provider_root=args.provider_root)
        if args.cmd == "fetch":
            print(json.dumps({"provider_sha": pk.sha, "verified_files": len(pk.digests)}, sort_keys=True))
            return 0
        write_json(args.out, build_receipt(pk))
        print(f"wrote {args.out}")
        return 0
    except BridgeHold as hold:
        print(json.dumps({"status": hold.status, "detail": hold.detail, "authority_transfer": False},
                         sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
