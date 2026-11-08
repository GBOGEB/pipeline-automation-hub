"""Synthetic ISO-week schedule challenges; no source or execution authority."""
from datetime import date
import importlib.util
from pathlib import Path
import unittest

PATH = Path(__file__).resolve().parents[1] / "tools" / "iso_schedule.py"
SPEC = importlib.util.spec_from_file_location("jade_iso_schedule", PATH)
m = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(m)


def example():
    return {"schema": m.SCHEMA, "iso_year": 2026, "tasks": [
        {"id": "SOURCE", "title": "Source checksum", "start": "w46MON", "end": "w46TUE"},
        {"id": "MATH", "title": "Independent math checks", "start": "w46THU",
         "end": "w47MON", "depends_on": ["SOURCE"]},
        {"id": "RENDER", "title": "Independent visualization", "start": "w46THU",
         "end": "w47MON", "depends_on": ["SOURCE"]},
        {"id": "GATE", "title": "Human review pending", "start": "w48FRI",
         "end": "w48FRI", "kind": "milestone", "depends_on": ["MATH", "RENDER"]},
    ]}


class IsoSchedule(unittest.TestCase):
    def test_iso_2026_53_week_year_and_cross_calendar_year(self):
        self.assertEqual(m.from_w_code(2026, "w53THU"), date(2026, 12, 31))
        self.assertEqual(m.from_w_code(2026, "w53SUN"), date(2027, 1, 3))
        self.assertEqual(m.week_address(date(2025, 12, 29)),
                         {"iso_year": 2026, "code": "w01MON", "date": "2025-12-29"})

    def test_non_leap_week_rejected(self):
        with self.assertRaises(ValueError):
            m.from_w_code(2025, "w53MON")

    def test_week_code_syntax_and_yearless_rejected(self):
        for year, code in ((2026, "w00MON"), (2026, "w54SUN"),
                           (2026, "w46Mon"), (2026, "w46MONextra"),
                           (None, "w46MON")):
            with self.subTest(year=year, code=code), self.assertRaises(ValueError):
                m.from_w_code(year, code)

    def test_planning_quarters_distinct_from_calendar_quarters(self):
        self.assertEqual(m.planning_quarter(2026, 53), "2026-PQ4")
        self.assertEqual(m.planning_quarter(2026, 14), "2026-PQ2")
        self.assertEqual(m.planning_quarter(2026, 1), "2026-PQ1")

    def test_kahn_fork_join(self):
        r = m.validate_schedule(example())
        self.assertEqual(r["waves"], [["SOURCE"], ["MATH", "RENDER"], ["GATE"]])
        self.assertEqual(r["status"], "DECLARED_PLAN_ONLY")
        self.assertFalse(r["authority_transfer"])

    def test_cycle_rejected(self):
        p = example()
        p["tasks"][0]["depends_on"] = ["GATE"]
        with self.assertRaisesRegex(ValueError, "cycle"):
            m.validate_schedule(p)

    def test_unknown_and_duplicate_dependencies_rejected(self):
        p = example()
        p["tasks"][1]["depends_on"] = ["MISSING"]
        with self.assertRaises(ValueError):
            m.validate_schedule(p)
        p = example()
        p["tasks"][1]["depends_on"] = ["SOURCE", "SOURCE"]
        with self.assertRaisesRegex(ValueError, "duplicate predecessor"):
            m.validate_schedule(p)

    def test_finish_to_start_violation_rejected(self):
        p = example()
        p["tasks"][1]["start"] = "w46TUE"
        with self.assertRaisesRegex(ValueError, "finish-to-start"):
            m.validate_schedule(p)

    def test_backward_and_multi_day_milestone_rejected(self):
        p = example()
        p["tasks"][1]["end"] = "w46MON"
        with self.assertRaisesRegex(ValueError, "end before start"):
            m.validate_schedule(p)
        p = example()
        p["tasks"][-1]["end"] = "w49MON"
        with self.assertRaisesRegex(ValueError, "milestone"):
            m.validate_schedule(p)

    def test_diagrams_are_plan_only_without_fake_execution(self):
        r = m.validate_schedule(example())
        dag = m.mermaid_dag(r)
        gantt = m.mermaid_gantt(r)
        self.assertIn("N0 --> N1", dag)
        self.assertIn("N0 --> N2", dag)
        self.assertIn("N1 --> N3", dag)
        self.assertIn("N2 --> N3", dag)
        self.assertIn("2026-11-09", gantt)
        self.assertIn("milestone", gantt)
        self.assertNotIn("done,", gantt)
        self.assertNotIn("crit,", gantt)

    def test_multiline_titles_do_not_split_mermaid_nodes(self):
        p = example()
        p["tasks"][0]["title"] = 'Source\nchecksum\rwith <angle> & "quotes"'
        r = m.validate_schedule(p)
        dag = m.mermaid_dag(r)
        gantt = m.mermaid_gantt(r)
        self.assertEqual(len(dag.splitlines()), 9)  # header + 4 nodes + 4 edges
        self.assertIn("&lt;angle&gt;", dag)
        self.assertNotIn("Source\nchecksum", dag)
        self.assertNotIn("checksum\rwith", gantt)

    def test_last_supported_date_uses_safe_gantt_duration(self):
        addr = m.week_address(date.max)
        p = {"schema": m.SCHEMA, "iso_year": addr["iso_year"], "tasks": [
            {"id": "FINAL", "title": "Last valid day", "start": addr["code"], "end": addr["code"]},
        ]}
        r = m.validate_schedule(p)
        self.assertIn("9999-12-31, 1d", m.mermaid_gantt(r))

    def test_documented_python_example_parses(self):
        import ast
        document = PATH.parent.parent / "docs" / "ISO_SCHEDULE_ADAPTER.md"
        prose = document.read_text(encoding="utf-8")
        tick = chr(96) * 3
        example_source = prose.split(tick + "python\n", 1)[1].split("\n" + tick, 1)[0]
        ast.parse(example_source)

    def test_portable_receipt_is_json_canonical_and_source_safe(self):
        import hashlib
        import json

        r = m.portable_receipt(example())
        self.assertEqual(r["schema"], m.SCHEMA)
        self.assertEqual(r["generation_method"], "JADE_ISO_SCHEDULE_PORTABLE_RECEIPT_V1")
        self.assertEqual(r["status"], "DECLARED_PLAN_ONLY")
        self.assertFalse(r["authority_transfer"])
        self.assertEqual(r["waves"], [["SOURCE"], ["MATH", "RENDER"], ["GATE"]])
        self.assertEqual(r["tasks"]["SOURCE"]["start"], "2026-11-09")
        digest = r.pop("receipt_sha256")
        wire = json.dumps(r, sort_keys=True, separators=(",", ":"),
                          ensure_ascii=True, allow_nan=False).encode("utf-8")
        self.assertEqual(digest, hashlib.sha256(wire).hexdigest())
        self.assertEqual(r, json.loads(wire))

    def test_portable_receipt_changes_digest_on_task_change(self):
        before = m.portable_receipt(example())
        changed = example()
        changed["tasks"][0]["title"] = "New source"
        after = m.portable_receipt(changed)
        self.assertNotEqual(before["receipt_sha256"], after["receipt_sha256"])

    def test_invalid_task_and_schema_rejected(self):
        p = example()
        p["schema"] = "unexpected"
        with self.assertRaises(ValueError):
            m.validate_schedule(p)
        p = example()
        p["tasks"].append(dict(p["tasks"][0]))
        with self.assertRaisesRegex(ValueError, "duplicate task id"):
            m.validate_schedule(p)


if __name__ == "__main__":
    unittest.main()
