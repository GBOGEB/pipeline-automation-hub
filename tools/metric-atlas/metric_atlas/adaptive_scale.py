"""QPS N5 deterministic, fail-closed census scale recommendation.

Output is an owner decision aid, NEVER a dispatcher or merge controller.
Native receipts and #530 canonical acceptance are independent controls.
"""
from __future__ import annotations


class ScaleError(ValueError):
    pass


SCHEMA = "qps-metric-pulse/v1"


def _yes(flags, name):
    return flags.get(name) is True


def decide(metrics, flags, *, previous=None):
    if (metrics.get("schema") != SCHEMA or metrics.get("eligible_repos") != 3
            or metrics.get("eligible_routes") != 6):
        raise ScaleError("invalid effective census population")
    current_routes = metrics.get("planned_routes")
    verified = metrics.get("verified_zip_routes")
    terminal = metrics.get("terminal_native_jobs")
    if (type(current_routes) is not int or current_routes < 0 or current_routes > 6 or
            type(verified) is not int or type(terminal) is not int or
            not (0 <= verified <= terminal <= current_routes)):
        raise ScaleError("inconsistent/native-unknown route population")
    if (metrics.get("merge_admission") != "HOLD" or
            metrics.get("qps_engineering_acceptance") is not False):
        raise ScaleError("metrics cannot convey admission or QPS authority")
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
    if not _yes(flags, "security_p0_p1_cleared_or_accepted"):
        return _result("HOLD_SECURITY_CLASSIFICATION", 2, 4, metrics,
                       "P0/P1 security disposition unknown")
    if (not isinstance(previous, dict) or
            previous.get("scope_fingerprint") != metrics.get("scope_fingerprint") or
            previous.get("planned_routes") != 4 or
            previous.get("verified_zip_routes") != 4 or
            previous.get("pulse_index", 10**9) >= metrics.get("pulse_index", -1)):
        return _result("HOLD_REPEATABILITY", 2, 4, metrics,
                       "two comparable successful four-route pulses required")
    return _result("PROPOSE_3x6_OWNER_REVIEW", 3, 6, metrics,
                   "next expansion needs its own source SHA admission verification")


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
        "action_authority": "OWNER_PROPOSAL_ONLY",
        "dispatch_performed": False, "merge_admission": "HOLD",
        "qps_engineering_acceptance": False,
    }
