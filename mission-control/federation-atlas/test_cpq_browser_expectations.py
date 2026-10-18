"""CPQ browser proof derives expected rows from the producer report (offline, no Playwright).

Regression: the browser check hard-coded 9 open / 2 active rows from an earlier
queue state; the I3 queue (19 rows, 10 open, 6 active) failed it legitimately.
"""
import copy
import json
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import cpq_browser_check as b  # noqa: E402  (must import without Playwright installed)
import cpq_convergence_n5 as c  # noqa: E402

SHA = 'a' * 40


def real_report():
    q = json.loads((HERE / 'CODE_PURPLE_BD_QUEUE_v1.json').read_text())
    t = json.loads((HERE / 'TOP7_CENSUS_PULSES_v1.json').read_text())
    return c.converge(q, t, SHA)


class BrowserExpectationTests(unittest.TestCase):
    def test_real_queue_expectations_match_report_metrics(self):
        r = real_report()
        e = b.expectations(r)
        m = r['metrics']
        self.assertEqual(e, {k: m[k] for k in ('canonical_rows', 'open', 'done', 'active')})
        # Same filters the page applies, recomputed independently from item states.
        states = [i['state'] for i in r['items']]
        self.assertEqual(e['open'], sum(s in c.OPEN for s in states))
        self.assertEqual(e['done'], sum(s in c.DONE for s in states))
        self.assertEqual(e['active'], states.count('ACTIVE'))

    def test_wrong_schema_rejected(self):
        r = real_report(); r['schema'] = 'fake'
        with self.assertRaisesRegex(AssertionError, 'CPQ003_REPORT_SCHEMA'):
            b.expectations(r)

    def test_non_integer_or_negative_counts_rejected(self):
        for bad in (None, '10', 10.0, True, -1):
            r = real_report(); r['metrics']['open'] = bad
            with self.subTest(bad=bad), self.assertRaisesRegex(AssertionError, 'CPQ003_REPORT_COUNTS'):
                b.expectations(r)

    def test_inconsistent_counts_rejected(self):
        for mutate in (lambda m: m.update(done=m['done'] + 1),
                       lambda m: m.update(active=m['open'] + 1),
                       lambda m: m.update(open=0, done=m['canonical_rows'])):
            r = real_report(); mutate(r['metrics'])
            with self.assertRaisesRegex(AssertionError, 'CPQ003_REPORT_INCONSISTENT'):
                b.expectations(r)

    def test_item_population_must_match_and_include_search_target(self):
        r = real_report(); r['items'] = r['items'][:-1]
        with self.assertRaisesRegex(AssertionError, 'CPQ003_REPORT_ITEMS'):
            b.expectations(r)
        r = real_report()
        r['items'] = [dict(i, id='X') if i['id'] == 'CPQ-010' else i for i in r['items']]
        with self.assertRaisesRegex(AssertionError, 'CPQ003_REPORT_ITEMS'):
            b.expectations(r)

    def test_html_embeds_same_population(self):
        r = real_report()
        html = c.render_html(r)
        self.assertIn('All %d' % r['metrics']['canonical_rows'], html)
        self.assertIn('id="items"', html)  # seeded-negative injection point still present


if __name__ == '__main__':
    unittest.main()
