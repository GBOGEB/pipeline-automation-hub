"""Evidence-gated QPS N5 scale recommendation. No dispatch or merge authority.

W6 adds conservative cohort/independence validation without changing producer
formats or the existing bounded 2x4 / 3x6 recommendations. Missing proof is HOLD.
"""
from __future__ import annotations

import re


class ScaleError(ValueError):
    pass


SCHEMA = "qps-metric-pulse/v1"
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_SCOPE = re.compile(r"[A-Za-z0-9._:/-]{1,128}\Z")


def _yes(flags, name):
    return flags.get(name) is True


def _valid_int(v, low, high):
    return type(v) is int and low <= v <= high


def _population(metrics):
    if not isinstance(metrics, dict) or (metrics.get("schema") != SCHEMA or
            metrics.get("eligible_repos") != 3 or metrics.get("eligible_routes") != 6):
        raise ScaleError("invalid effective census population")
    routes, verified, terminal = (metrics.get(k) for k in (
        "planned_routes", "verified_zip_routes", "terminal_native_jobs"))
    if not all(_valid_int(x, 0, 6) for x in (routes, verified, terminal)) or not (verified <= terminal <= routes):
        raise ScaleError("inconsistent/native-unknown route population")
    if metrics.get("merge_admission") != "HOLD" or metrics.get("qps_engineering_acceptance") is not False:
        raise ScaleError("metrics cannot convey admission or QPS authority")
    return routes, verified, terminal


def _qualified_repeat(previous, current):
    """Check repeatability *eligibility*; not independent native verification.

    Identity fields are required when proposing scale. A pair of manually
    populated pulse records is still advisory until source-owner proof.
    """
    if not isinstance(previous, dict):
        return False
    try:
        prior_routes, prior_zip, prior_terminal = _population(previous)
    except ScaleError:
        return False
    if (prior_routes != 4 or prior_zip != 4 or prior_terminal != 4 or
            not _valid_int(previous.get("pulse_index"), 0, 10**9) or
            not _valid_int(current.get("pulse_index"), 1, 10**9) or
            previous["pulse_index"] >= current["pulse_index"]):
        return False
    for item in (previous, current):
        fp = item.get("scope_fingerprint")
        if not isinstance(fp, str) or _SCOPE.fullmatch(fp) is None:
            return False
        for key in ("source_heads_sha256", "native_receipt_set_sha256"):
            value = item.get(key)
            if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
                return False
    if (previous["scope_fingerprint"] != current["scope_fingerprint"] or
            previous["source_heads_sha256"] != current["source_heads_sha256"] or
            previous["native_receipt_set_sha256"] == current["native_receipt_set_sha256"]):
        return False
    return True


def decide(metrics, flags, *, previous=None):
    if not isinstance(flags, dict):
        raise ScaleError("owner/guard flags must be an object")
    current_routes, verified, terminal = _population(metrics)
    if flags.get("security_p0_p1_present") is True:
        return _result("HOLD_CRITICAL_SECURITY", 0, 0, metrics, "critical security finding")
    if not (_yes(flags, "codex_receiver_merged") and _yes(flags, "qps_receiver_merged")):
        return _result("HOLD_RECEIVER_ADMISSION", 0, 0, metrics, "source receivers not admitted")
    if not _yes(flags, "private_qps_read_authorized"):
        return _result("HOLD_PRIVATE_READ", 0, 0, metrics, "private source authorization absent")
    if not _yes(flags, "source_owner_dispatch_approved"):
        return _result("HOLD_OWNER_APPROVAL", 0, 0, metrics, "dispatch not explicitly authorized")
    if current_routes < 4 or verified < 4 or terminal < 4:
        return _result("GO_PILOT_2x4_ONLY", 2, 4, metrics,
                       "observe four independent exact-head terminal and ZIP receipts")
    if not _yes(flags, "canonical_530_zip_verifier_accepted"):
        return _result("HOLD_CANONICAL_ZIP", 2, 4, metrics,
                       "local integrity is not canonical 530 approval")
    if not _yes(flags, "abacus_receiver_merged"):
        return _result("HOLD_ABACUS_ADMISSION", 2, 4, metrics,
                       "ABACUS remains source-owned HOLD")
    if not _yes(flags, "abacus_effective_required_checks_green"):
        return _result("HOLD_REQUIRED_GATES", 2, 4, metrics,
                       "required checks have not been proven")
    if flags.get("security_p0_p1_present") is not False or not _yes(flags, "security_p0_p1_cleared_or_accepted"):
        return _result("HOLD_SECURITY_CLASSIFICATION", 2, 4, metrics,
                       "P0/P1 security status must be explicitly reviewed and clear")
    if not _qualified_repeat(previous, metrics):
        return _result("HOLD_REPEATABILITY", 2, 4, metrics,
                       "scope, source-heads and distinct native receipt sets required")
    return _result("PROPOSE_3x6_OWNER_REVIEW", 3, 6, metrics,
                   "next expansion needs source SHA, independent proof and owner review")


def _result(status, repos, routes, metrics, why):
    return {
        "schema": "qps-metric-scale-decision/v1", "wave": metrics.get("wave"),
        "status": status, "next_source_repositories": repos,
        "next_read_only_routes": routes, "reason": why,
        "observed_terminal_jobs": metrics.get("terminal_native_jobs"),
        "observed_byte_verified_routes": metrics.get("verified_zip_routes"),
        "nominal_max_source_repos": 3, "nominal_max_routes": 6,
        "new_native_tests_credited": None, "matched_statement_branch_uplift": None,
        "worker_hour_yield": None, "statistical_sigma": None,
        "action_authority": "OWNER_PROPOSAL_ONLY", "dispatch_performed": False,
        "merge_admission": "HOLD", "qps_engineering_acceptance": False,
    }
