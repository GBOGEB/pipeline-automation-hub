"""N5 first-red repair: a missing cross-repo credential defers, it never fakes a census.

Scheduled runs 38962605983..39123163815 failed with HTTP 404 because the
repository-scoped GITHUB_TOKEN cannot read sibling private repositories and
CROSS_REPO_READ_TOKEN was never installed. These controls pin the repaired contract:
  * credential absent + required  -> typed DEFERRED receipt, zero requests, no snapshot
  * credential present + GET 404  -> still fail-closed exit 2 (real first-red preserved)
  * flag not given                -> legacy behaviour unchanged (GITHUB_TOKEN fallback)
"""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'source'))
import live_census as c  # noqa: E402
from source_access import (CROSS_REPO_TOKEN_ENV, DEFERRED_NO_TOKEN,  # noqa: E402
                           SourceAccessError, credential_deferral)

R = '/repos/GBOGEB/ABACUS/commits/main'


def env_without_cross_token(**extra):
    env = {k: v for k, v in os.environ.items() if k != CROSS_REPO_TOKEN_ENV}
    env.update(extra)
    return env


class CredentialDeferralTests(unittest.TestCase):
    def test_absent_token_defers_without_any_request(self):
        with tempfile.TemporaryDirectory() as t, \
                mock.patch.dict(os.environ, env_without_cross_token(GITHUB_TOKEN='repo-scoped'), clear=True), \
                mock.patch.object(c, 'acquire', side_effect=AssertionError('network attempted')) as acq:
            result = c.cli(['--refresh', '--require-cross-repo-token', '--out', t])
            self.assertEqual(result, DEFERRED_NO_TOKEN)
            acq.assert_not_called()
            self.assertFalse((Path(t) / 'snapshot.json').exists())
            self.assertFalse((Path(t) / 'manifest.json').exists())
            d = json.loads((Path(t) / 'access_diagnostic.json').read_text())
            self.assertEqual(d['disposition'], DEFERRED_NO_TOKEN)
            self.assertEqual(d['requests_attempted'], 0)
            self.assertFalse(d['fresh_census_generated'])

    def test_blank_token_is_treated_as_absent(self):
        with tempfile.TemporaryDirectory() as t, \
                mock.patch.dict(os.environ, env_without_cross_token(**{CROSS_REPO_TOKEN_ENV: '  '}), clear=True), \
                mock.patch.object(c, 'acquire', side_effect=AssertionError('network attempted')):
            self.assertEqual(c.cli(['--refresh', '--require-cross-repo-token', '--out', t]), DEFERRED_NO_TOKEN)

    def test_present_token_still_fails_closed_on_404(self):
        with tempfile.TemporaryDirectory() as t, \
                mock.patch.dict(os.environ, env_without_cross_token(**{CROSS_REPO_TOKEN_ENV: 'x'}), clear=True), \
                mock.patch.object(c, 'acquire', side_effect=SourceAccessError(R, 404)):
            with self.assertRaises(SystemExit) as caught:
                c.cli(['--refresh', '--require-cross-repo-token', '--out', t])
            self.assertEqual(caught.exception.code, 2)
            d = json.loads((Path(t) / 'access_diagnostic.json').read_text())
            self.assertEqual(d['http_status'], 404)
            self.assertEqual(d['disposition'], 'HOLD_OWNER_SOURCE_ACCESS_OR_REF_VERIFICATION')

    def test_legacy_refresh_without_flag_unchanged(self):
        with tempfile.TemporaryDirectory() as t, \
                mock.patch.dict(os.environ, env_without_cross_token(), clear=True), \
                mock.patch.object(c, 'acquire', side_effect=SourceAccessError(R, 404)) as acq:
            with self.assertRaises(SystemExit) as caught:
                c.cli(['--refresh', '--out', t])
            self.assertEqual(caught.exception.code, 2)
            acq.assert_called_once()

    def test_deferral_grants_no_authority_and_leaks_no_secret(self):
        d = credential_deferral()
        self.assertFalse(d['merge_authorized'])
        self.assertFalse(d['crew_dispatch_authorized'])
        self.assertFalse(d['engineering_acceptance'])
        self.assertIsNone(d['accepted_causal_root_closures'])
        self.assertIsNone(d['source_present'])
        self.assertNotIn('Authorization', json.dumps(d))
        self.assertEqual(d['credential_env'], CROSS_REPO_TOKEN_ENV)

    def test_deferral_cannot_pass_snapshot_verify(self):
        with tempfile.TemporaryDirectory() as t, \
                mock.patch.dict(os.environ, env_without_cross_token(), clear=True):
            c.cli(['--refresh', '--require-cross-repo-token', '--out', t])
            with self.assertRaises(FileNotFoundError):
                c.cli(['--verify', t])


if __name__ == '__main__':
    unittest.main()
