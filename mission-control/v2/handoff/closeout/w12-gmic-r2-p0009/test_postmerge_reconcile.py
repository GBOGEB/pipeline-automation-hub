"""Negative and continuity checks against the frozen P0008 B01-B46 projection, independent of live GitHub."""
import copy
import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from postmerge_reconcile import FROZEN_BLOB, HIST, git_blob_sha, load_frozen_rows, project, verify_manifest

HERE = Path(__file__).resolve().parent
WITNESS = json.loads((HERE / 'POSTMERGE_WITNESS.json').read_text(encoding='utf-8'))
MANIFEST = json.loads((HERE / 'RELEASE_MANIFEST.json').read_text(encoding='utf-8'))
FROZEN = load_frozen_rows()


def fixture():
    return json.loads(HIST.read_text(encoding='utf-8'))


def row(baseline, bid):
    return next(x for x in baseline['items'] if x['id'] == bid)


class PostmergeWitnessTests(unittest.TestCase):
    def test_keeps_all_46_without_credit(self):
        result = project(fixture(), WITNESS)
        self.assertEqual(len(result['historical_unchanged_46']), 46)
        self.assertEqual(sum(x['historical_state'] == 'DONE' for x in result['historical_unchanged_46']), 22)
        self.assertIsNone(result['current_parent_closure_count_verified'])
        self.assertFalse(result['controls']['authority_transfer'])

    def test_merged_source_never_promotes_original_open_items(self):
        result = project(fixture(), WITNESS)
        for bid in ('B08', 'B15', 'B21', 'B22', 'B23', 'B24', 'B32', 'B34', 'B38'):
            out = next(x for x in result['historical_unchanged_46'] if x['id'] == bid)
            self.assertNotEqual(out['historical_state'], 'DONE')
            self.assertEqual(out['historical_state'], FROZEN[bid][2])
            self.assertTrue(out['current_phase_observation'])
            self.assertEqual(out['status_authority'], 'HISTORICAL_FROZEN_UNCHANGED')

    def test_duplicate_pr_rejected(self):
        bad = copy.deepcopy(WITNESS)
        bad['commit_observations'].append(bad['commit_observations'][0])
        with self.assertRaises(ValueError):
            project(fixture(), bad)

    def test_unknown_item_rejected(self):
        bad = copy.deepcopy(WITNESS)
        bad['commit_observations'][0]['b_items'].append('B99')
        with self.assertRaises(ValueError):
            project(fixture(), bad)

    def test_claimed_retroactive_admission_rejected(self):
        bad = copy.deepcopy(WITNESS)
        bad['controls']['merge_admission_retroactively_verified'] = True
        with self.assertRaises(ValueError):
            project(fixture(), bad)

    def test_hosted_ic3_fabrication_rejected(self):
        bad = copy.deepcopy(WITNESS)
        bad['controls']['ic3_hosted_pass_verified'] = True
        with self.assertRaises(ValueError):
            project(fixture(), bad)

    def test_baseline_truncation_or_promotion_rejected(self):
        for change in ('missing', 'promotion'):
            bad = fixture()
            if change == 'missing':
                bad['items'].pop()
            else:
                bad['items'][20]['state'] = 'DONE'
            with self.assertRaises(ValueError):
                project(bad, WITNESS)


class FrozenRowPinTests(unittest.TestCase):
    """Codex P2: aggregate 46/22/24 is not enough; each row must equal the frozen projection."""

    def test_frozen_projection_blob_is_pinned(self):
        self.assertEqual(git_blob_sha(HIST.read_bytes()), FROZEN_BLOB)
        self.assertEqual(len(FROZEN), 46)

    def test_state_swap_with_equal_totals_rejected(self):
        bad = fixture()
        b01, b08 = row(bad, 'B01'), row(bad, 'B08')
        b01['state'], b08['state'] = b08['state'], b01['state']
        by_state = {}
        for x in bad['items']:
            by_state[x['state']] = by_state.get(x['state'], 0) + 1
        self.assertEqual(by_state, fixture()['counts']['by_state'])
        self.assertEqual(sum(x['state'] == 'DONE' for x in bad['items'][:38]), 20)
        with self.assertRaises(ValueError):
            project(bad, WITNESS)

    def test_dod_rewrite_rejected(self):
        bad = fixture()
        row(bad, 'B24')['minimum_dod_dov'] += ' (closed by merged PR)'
        with self.assertRaises(ValueError):
            project(bad, WITNESS)

    def test_priority_change_rejected(self):
        bad = fixture()
        target = row(bad, 'B09')
        target['priority'] = 'P1' if target['priority'] == 'P0' else 'P0'
        with self.assertRaises(ValueError):
            project(bad, WITNESS)

    def test_tampered_frozen_file_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            copy_path = Path(tmp) / HIST.name
            raw = HIST.read_bytes().replace(b'"REVIEW_WAIT"', b'"DONE"', 1)
            copy_path.write_bytes(raw)
            with self.assertRaises(ValueError):
                load_frozen_rows(copy_path)


class ReleaseManifestTests(unittest.TestCase):
    """Codex P2: every manifest member must be committed and match its checksum."""

    def test_committed_manifest_verifies(self):
        verify_manifest(MANIFEST, HERE)
        self.assertNotIn('dashboard.html', MANIFEST['files_sha256'])

    def _staged(self, tmp):
        for name in MANIFEST['files_sha256']:
            shutil.copyfile(HERE / name, Path(tmp) / name)
        return copy.deepcopy(MANIFEST)

    def test_missing_member_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest = self._staged(tmp)
            manifest['files_sha256']['dashboard.html'] = hashlib.sha256(b'absent').hexdigest()
            with self.assertRaises(ValueError):
                verify_manifest(manifest, Path(tmp))

    def test_checksum_mismatch_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest = self._staged(tmp)
            with (Path(tmp) / 'README.md').open('ab') as fh:
                fh.write(b'tampered\n')
            with self.assertRaises(ValueError):
                verify_manifest(manifest, Path(tmp))

    def test_nested_or_parent_path_rejected(self):
        for name in ('../README.md', 'sub/README.md', '..'):
            manifest = copy.deepcopy(MANIFEST)
            manifest['files_sha256'][name] = MANIFEST['files_sha256']['README.md']
            with self.assertRaises(ValueError):
                verify_manifest(manifest, HERE)


class OptimizationIntegrityTests(unittest.TestCase):
    """Runtime validation must remain active under -O and PYTHONOPTIMIZE."""

    def _optimized(self, source):
        import subprocess
        import sys
        import os
        env = dict(os.environ, PYTHONOPTIMIZE="1")
        result = subprocess.run([sys.executable, "-O", "-c", source],
                                cwd=HERE, env=env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_optimized_state_swap_still_rejected(self):
        self._optimized("""import json
from postmerge_reconcile import HIST, WITNESS, project
b = json.loads(HIST.read_text(encoding='utf-8'))
w = json.loads(WITNESS.read_text(encoding='utf-8'))
b['items'][0]['state'], b['items'][7]['state'] = b['items'][7]['state'], b['items'][0]['state']
try:
    project(b, w)
except ValueError:
    raise SystemExit(0)
raise SystemExit(1)
""")

    def test_optimized_wrong_historical_total_rejected(self):
        self._optimized("""import json
from postmerge_reconcile import HIST, WITNESS, project
b = json.loads(HIST.read_text(encoding='utf-8'))
w = json.loads(WITNESS.read_text(encoding='utf-8'))
b['counts']['total'] = 999
try:
    project(b, w)
except ValueError:
    raise SystemExit(0)
raise SystemExit(1)
""")

    def test_optimized_missing_release_member_rejected(self):
        self._optimized("""import json
from postmerge_reconcile import MANIFEST, verify_manifest
m = json.loads(MANIFEST.read_text(encoding='utf-8'))
m['files_sha256']['missing.html'] = '0' * 64
try:
    verify_manifest(m)
except ValueError:
    raise SystemExit(0)
raise SystemExit(1)
""")

    def test_optimized_authority_promotion_rejected(self):
        self._optimized("""import json
from postmerge_reconcile import HIST, WITNESS, project
b = json.loads(HIST.read_text(encoding='utf-8'))
w = json.loads(WITNESS.read_text(encoding='utf-8'))
w['controls']['authority_transfer'] = True
try:
    project(b, w)
except ValueError:
    raise SystemExit(0)
raise SystemExit(1)
""")


class FrozenMetadataTests(unittest.TestCase):
    def test_all_historical_count_metadata_is_immutable(self):
        for field, wrong in (
            ('total', 999),
            ('by_state', {'DONE': 46}),
            ('raw_completion_percent', -1),
        ):
            with self.subTest(field=field):
                b = fixture()
                b['counts'][field] = wrong
                with self.assertRaises(ValueError):
                    project(b, WITNESS)

    def test_unapproved_extra_historical_row_data_rejected(self):
        b = fixture()
        b['items'][0]['unverified_admission'] = True
        with self.assertRaises(ValueError):
            project(b, WITNESS)



if __name__ == '__main__':
    unittest.main()
