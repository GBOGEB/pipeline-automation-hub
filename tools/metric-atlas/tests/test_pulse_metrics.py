import copy
import unittest
from metric_atlas.pulse_metrics import summarize, compare_pulses, PulseMetricError


def postflight(statuses):
    rows = []
    for i, status in enumerate(statuses):
        terminal = status in ("VERIFIED_LOCAL_ZIP_AND_NATIVE_JOB", "HOLD_ARTIFACT_BYTES_UNKNOWN",
                              "HOLD_ARTIFACT_BYTES_INVALID")
        artifact = {"byte_integrity": "PASS", "zip_bytes": 100, "member_bytes": 60,
                    "zip_sha256": "f" * 64, "canonical_530_accepted": False
                    } if status == "VERIFIED_LOCAL_ZIP_AND_NATIVE_JOB" else None
        rows.append({"repo": "GBOGEB/CODEX" if i < 2 else "GBOGEB/cryoplant-project",
                     "route": "native_checks" if i % 2 == 0 else "coverage_catalog",
                     "status": status, "terminal_job_id": 100 + i if terminal else None,
                     "artifact": artifact})
    return {"schema": "qps-metric-postflight/v1", "wave": "N4",
            "eligible_repos": 3, "eligible_routes": 6,
            "planned_repos": len(set(x["repo"] for x in rows)),
            "planned_routes": len(rows),
            "terminal_native_jobs_confirmed": sum(
                x["terminal_job_id"] is not None for x in rows),
            "byte_verified_routes": sum(x["artifact"] is not None for x in rows),
            "rows": rows}


class MetricsTests(unittest.TestCase):
    def test_all_unknown_is_not_success(self):
        result = summarize(postflight(["HOLD_RECEIPT_MISSING"] * 4), pulse_index=4)
        self.assertEqual(result["verified_zip_routes"], 0)
        self.assertEqual(result["terminal_native_jobs"], 0)
        self.assertIsNone(result["branch_coverage"])
        self.assertIsNone(result["worker_hours"])
        self.assertEqual(result["zip_fraction"], 0.0)

    def test_mixed_status_and_scale(self):
        x = summarize(postflight(["VERIFIED_LOCAL_ZIP_AND_NATIVE_JOB",
            "HOLD_ARTIFACT_BYTES_UNKNOWN", "HOLD_RECEIPT_MISSING",
            "HOLD_RECEIPT_MISSING"]), pulse_index=4)
        self.assertEqual((x["terminal_native_jobs"], x["verified_zip_routes"]), (2, 1))
        self.assertEqual((x["zip_fraction"], x["zip_given_terminal"]), (.25, .5))

    def test_reject_denominator_fabrication(self):
        p = postflight(["HOLD_RECEIPT_MISSING"] * 4)
        p["planned_routes"] = 6
        with self.assertRaises(PulseMetricError):
            summarize(p, pulse_index=4)

    def test_reject_false_terminal_counter(self):
        p = postflight(["HOLD_RECEIPT_MISSING"] * 4)
        p["terminal_native_jobs_confirmed"] = 1
        with self.assertRaises(PulseMetricError):
            summarize(p, pulse_index=4)

    def test_reject_artifact_missing_source_bytes(self):
        p = postflight(["VERIFIED_LOCAL_ZIP_AND_NATIVE_JOB"] * 4)
        del p["rows"][0]["artifact"]["member_bytes"]
        with self.assertRaises(PulseMetricError):
            summarize(p, pulse_index=4)

    def test_duplicate_route_rejected(self):
        p = postflight(["HOLD_RECEIPT_MISSING"] * 4)
        p["rows"][1]["route"] = "native_checks"
        with self.assertRaises(PulseMetricError):
            summarize(p, pulse_index=4)

    def test_identical_scope_gain(self):
        a = summarize(postflight(["HOLD_RECEIPT_MISSING"] * 4), pulse_index=4)
        b = summarize(postflight(["VERIFIED_LOCAL_ZIP_AND_NATIVE_JOB"] * 4), pulse_index=5)
        m = compare_pulses([a, b])
        self.assertEqual(m["delta_zip"], 4)
        self.assertEqual(m["velocity_routes_per_pulse"], 4)
        self.assertIsNone(m["rolling_n20"])

    def test_unmatched_scope_not_compared(self):
        a = summarize(postflight(["HOLD_RECEIPT_MISSING"] * 4), pulse_index=4)
        b = summarize(postflight(["HOLD_RECEIPT_MISSING"] * 2), pulse_index=5)
        m = compare_pulses([a, b])
        self.assertEqual(m["status"], "UNMATCHED_COHORT")
        self.assertIsNone(m["delta_zip"])

    def test_n20_is_unknown(self):
        m = compare_pulses([summarize(postflight(["HOLD_RECEIPT_MISSING"] * 4), pulse_index=i)
                            for i in range(4, 8)])
        self.assertIsNone(m["rolling_n20"])
        self.assertIsNone(m["stability_mad"])

    def test_duplicate_pulse_rejected(self):
        a = summarize(postflight(["HOLD_RECEIPT_MISSING"] * 4), pulse_index=4)
        with self.assertRaises(PulseMetricError):
            compare_pulses([a, copy.deepcopy(a)])


if __name__ == "__main__":
    unittest.main()
