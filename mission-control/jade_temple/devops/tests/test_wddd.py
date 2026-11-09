"""w##DDD week codes (devops/wddd.py): every date claim of the 2026-11-08 B1/B2 handover, plus its fixes (offline)."""
import importlib.util
import re
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location(name, HERE / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


W = load("wddd")
BE_HOLIDAYS = frozenset({date(2026, 11, 11), date(2026, 12, 25), date(2027, 1, 1)})
HANDOVER_DATES = (
    ("w01MON", date(2025, 12, 29)),
    ("w13SUN", date(2026, 3, 29)),
    ("w14MON", date(2026, 3, 30)),
    ("w26SUN", date(2026, 6, 28)),
    ("w27MON", date(2026, 6, 29)),
    ("w39SUN", date(2026, 9, 27)),
    ("w40MON", date(2026, 9, 28)),
    ("w46MON", date(2026, 11, 9)),
    ("w46WED", date(2026, 11, 11)),
    ("w47FRI", date(2026, 11, 20)),
    ("w48FRI", date(2026, 11, 27)),
    ("w49TUE", date(2026, 12, 1)),
    ("w50FRI", date(2026, 12, 11)),
    ("w51FRI", date(2026, 12, 18)),
    ("w52FRI", date(2026, 12, 25)),
    ("w53THU", date(2026, 12, 31)),
    ("w53SUN", date(2027, 1, 3)),
)


def workdays_in_week(iso_year, week, holidays=BE_HOLIDAYS):
    mon = W.from_w_code(f"{iso_year}-w{week:02d}MON")
    days = (mon + timedelta(i) for i in range(7))
    return sum(1 for d in days if d.weekday() < 5 and d not in holidays)


class IsoYear(unittest.TestCase):
    def test_2026_has_53_iso_weeks(self):
        self.assertEqual(date(2026, 1, 1).weekday(), 3)  # Thursday, hence 53 weeks
        self.assertEqual([W.weeks_in_iso_year(y) for y in (2025, 2026, 2027, 2020, 2032)], [52, 53, 52, 53, 53])

    def test_week_count_matches_the_calendar(self):
        for y in range(2000, 2041):
            with self.subTest(year=y):
                last = date.fromisocalendar(y + 1, 1, 1) - timedelta(days=1)
                self.assertEqual(W.weeks_in_iso_year(y), last.isocalendar()[1])


class Codes(unittest.TestCase):
    def test_handover_dates(self):
        for code, expected in HANDOVER_DATES:
            with self.subTest(code=code):
                self.assertEqual(W.from_w_code(code, iso_year=2026), expected)
                self.assertEqual(W.from_w_code(f"2026-{code}"), expected)
                self.assertEqual(W.to_w_code(expected), code)
                self.assertEqual(W.to_w_code(expected, with_year=True), f"2026-{code}")

    def test_round_trip_2024_to_2028(self):
        d = date(2024, 1, 1)
        while d < date(2029, 1, 1):
            self.assertEqual(W.from_w_code(W.to_w_code(d, with_year=True)), d)
            d += timedelta(days=1)

    def test_round_trip_at_the_ends_of_the_date_range(self):
        # the year is zero-padded to four digits, so every code the encoder emits parses (Codex P2, #1137)
        self.assertEqual(W.to_w_code(date.min, with_year=True), "0001-w01MON")
        self.assertEqual(W.iso_week_key(date.min), "0001-W01")
        self.assertEqual(W.to_w_code(date.max, with_year=True), "9999-w52FRI")
        self.assertEqual(W.from_w_code("9999-w52FRI"), date.max)
        for start in (date.min, date.max - timedelta(days=800)):
            for i in range(800):
                d = start + timedelta(days=i)
                self.assertEqual(W.from_w_code(W.to_w_code(d, with_year=True)), d)

    def test_parsing_is_lenient_on_case_and_whitespace_only(self):
        self.assertEqual(W.from_w_code(" 2026-W46mon "), date(2026, 11, 9))
        self.assertEqual(W.from_w_code("2026-w46MON", iso_year=2026), date(2026, 11, 9))

    def test_bad_codes_raise(self):
        for code, year in (("w46MON", None),  # bare code without a year
                           ("2026-w46MON", 2027),  # conflicting years
                           ("w53MON", 2027),  # 2027 has 52 weeks
                           ("w00MON", 2026), ("w46XYZ", 2026), ("w4MON", 2026), ("46MON", 2026),
                           ("2026-w46MONDAY", None), ("٢٠٢٦-w46MON", None)):  # non-ASCII digits
            with self.subTest(code=code, year=year), self.assertRaises(ValueError):
                W.from_w_code(code, iso_year=year)

    def test_year_boundary_is_ambiguous_without_year(self):
        # one bare label, two calendar years: the reason codes near w01 and w53 carry the ISO year
        self.assertEqual(W.to_w_code(date(2025, 12, 29)), "w01MON")
        self.assertEqual(W.to_w_code(date(2026, 12, 28)), "w53MON")
        self.assertEqual(W.to_w_code(date(2025, 12, 29), with_year=True), "2026-w01MON")
        self.assertEqual(W.to_w_code(date(2027, 1, 3), with_year=True), "2026-w53SUN")


class WeekKey(unittest.TestCase):
    def test_hub_week_key(self):
        self.assertEqual(W.iso_week_key(date(2026, 11, 9)), "2026-W46")
        self.assertEqual(W.iso_week_key(date(2027, 1, 3)), "2026-W53")
        self.assertEqual(W.iso_week_key(date(2025, 12, 29)), "2026-W01")

    def test_datetime_uses_its_own_date(self):
        self.assertEqual(W.iso_week_key(datetime(2027, 1, 3, 23, 59, tzinfo=timezone.utc)), "2026-W53")
        self.assertEqual(W.iso_week_key(datetime(2027, 1, 4, 0, 0, tzinfo=timezone.utc)), "2027-W01")

    def test_key_and_code_agree(self):
        d = date(2024, 1, 1)
        while d < date(2029, 1, 1):
            code = W.to_w_code(d, with_year=True)
            self.assertEqual(W.iso_week_key(d), code[:5] + "W" + code[6:8])
            d += timedelta(days=1)


class Quarter(unittest.TestCase):
    def test_quarter_13w(self):
        self.assertEqual([W.quarter_13w(w) for w in (1, 13, 14, 26, 27, 39, 40, 52, 53)],
                         ["Q1", "Q1", "Q2", "Q2", "Q3", "Q3", "Q4", "Q4", "Q4"])
        for bad in (0, 54):
            with self.subTest(week=bad), self.assertRaises(ValueError):
                W.quarter_13w(bad)


class Mermaid(unittest.TestCase):
    def test_W_is_not_the_iso_week(self):
        # B1 used `axisFormat w%W`. %W is the Monday-based week of the calendar year, not the ISO week:
        # in 2026 it reads one lower. Mermaid formats axes with d3-time-format, where %W and %V mean the same.
        d = date(2026, 11, 9)
        self.assertEqual(d.strftime("%W"), "45")
        self.assertEqual(d.strftime("%V"), "46")

    def test_pattern_doc_uses_iso_axis_and_new_year(self):
        doc = (HERE / "WDDD_WEEK_CODES.md").read_text(encoding="utf-8")
        blocks = re.findall(r"```mermaid\n(.*?)```", doc, flags=re.S)
        self.assertGreaterEqual(len(blocks), 5)
        axes = re.findall(r"^\s*axisFormat\s+(.*)$", doc, flags=re.M)
        self.assertTrue(axes)
        self.assertTrue(all("%V" in a and "%W" not in a for a in axes), axes)
        for excl in re.findall(r"^\s*excludes\s+(.*)$", doc, flags=re.M):
            self.assertIn("2027-01-01", excl)


class Workdays(unittest.TestCase):
    def test_gantt_workday_span(self):
        # `:t1, 2026-11-09, 9d` under `excludes weekends, 2026-11-11, ...` ends on w47FRI
        self.assertEqual(W.add_workdays(date(2026, 11, 9), 9, BE_HOLIDAYS), date(2026, 11, 20))
        self.assertEqual(W.add_workdays(date(2026, 11, 7), 1), date(2026, 11, 9))  # a Saturday start rolls on

    def test_span_needs_a_workday(self):
        for n in (0, -1):
            with self.subTest(n=n), self.assertRaises(ValueError):
                W.add_workdays(date(2026, 11, 9), n)

    def test_b2_workday_counts(self):
        self.assertEqual([workdays_in_week(2026, w) for w in range(46, 54)], [4, 5, 5, 5, 5, 5, 4, 4])
        self.assertEqual(sum(workdays_in_week(2026, w) for w in (46, 47, 48)), 14)
        self.assertEqual(sum(workdays_in_week(2026, w) for w in (49, 50, 51, 52, 53)), 23)


if __name__ == "__main__":
    unittest.main()
