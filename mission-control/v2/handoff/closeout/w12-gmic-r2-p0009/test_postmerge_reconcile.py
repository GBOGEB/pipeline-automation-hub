"""Negative and continuity checks, synthetic baseline independent of live GitHub."""
import copy
import json
import unittest
from pathlib import Path

from postmerge_reconcile import project

HERE = Path(__file__).resolve().parent
WITNESS = json.loads((HERE / 'POSTMERGE_WITNESS.json').read_text(encoding='utf-8'))


def fixture():
    rows = []
    for n in range(1, 47):
        done = {1, 2, 3, 4, 5, 6, 7, 12, 14, 16, 17, 18, 20, 27, 28, 30, 31, 33, 35, 36, 39, 40}
        state = 'DONE' if n in done else 'REVIEW_WAIT'
        rows.append({'id': f'B{n:02d}', 'priority': 'P0' if n % 3 == 0 else 'P1', 'state': state})
    return {'items': rows, 'counts': {'total': 46, 'done': 22, 'open': 24}}


class PostmergeWitnessTests(unittest.TestCase):
    def test_keeps_all_46_without_credit(self):
        result = project(fixture(), WITNESS)
        self.assertEqual(len(result['historical_unchanged_46']), 46)
        self.assertEqual(sum(x['historical_state'] == 'DONE' for x in result['historical_unchanged_46']), 22)
        self.assertIsNone(result['current_parent_closure_count_verified'])
        self.assertFalse(result['controls']['authority_transfer'])

    def test_merged_source_never_promotes_original_review_wait(self):
        result = project(fixture(), WITNESS)
        for bid in ('B08', 'B15', 'B21', 'B22', 'B23', 'B24', 'B32', 'B34', 'B38'):
            row = next(x for x in result['historical_unchanged_46'] if x['id'] == bid)
            self.assertEqual(row['historical_state'], 'REVIEW_WAIT')
            self.assertTrue(row['current_phase_observation'])
            self.assertEqual(row['status_authority'], 'HISTORICAL_FROZEN_UNCHANGED')

    def test_duplicate_pr_rejected(self):
        bad = copy.deepcopy(WITNESS)
        bad['commit_observations'].append(bad['commit_observations'][0])
        with self.assertRaises(AssertionError):
            project(fixture(), bad)

    def test_unknown_item_rejected(self):
        bad = copy.deepcopy(WITNESS)
        bad['commit_observations'][0]['b_items'].append('B99')
        with self.assertRaises(AssertionError):
            project(fixture(), bad)

    def test_claimed_retroactive_admission_rejected(self):
        bad = copy.deepcopy(WITNESS)
        bad['controls']['merge_admission_retroactively_verified'] = True
        with self.assertRaises(AssertionError):
            project(fixture(), bad)

    def test_hosted_ic3_fabrication_rejected(self):
        bad = copy.deepcopy(WITNESS)
        bad['controls']['ic3_hosted_pass_verified'] = True
        with self.assertRaises(AssertionError):
            project(fixture(), bad)

    def test_baseline_truncation_or_promotion_rejected(self):
        for change in ('missing', 'promotion'):
            bad = fixture()
            if change == 'missing':
                bad['items'].pop()
            else:
                bad['items'][20]['state'] = 'DONE'
            with self.assertRaises(AssertionError):
                project(bad, WITNESS)


if __name__ == '__main__':
    unittest.main()
