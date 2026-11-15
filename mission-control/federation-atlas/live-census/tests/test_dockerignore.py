"""The .dockerignore allowlist must match what the Dockerfile COPYs, and nothing more."""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def copy_sources():
    sources = []
    for line in (ROOT / 'Dockerfile').read_text().splitlines():
        parts = line.split()
        if parts and parts[0].upper() == 'COPY':
            args = [p for p in parts[1:] if not p.startswith('--')]
            sources.extend(a.rstrip('/') for a in args[:-1])
    return sources


def ignore_rules():
    rules = []
    for line in (ROOT / '.dockerignore').read_text().splitlines():
        line = line.strip()
        if line and not line.startswith('#'):
            rules.append(line)
    return rules


class DockerignoreAllowlist(unittest.TestCase):
    def test_excludes_everything_first(self):
        self.assertEqual(ignore_rules()[0], '*')

    def test_allowlist_equals_copy_sources(self):
        allowed = {r[1:].rstrip('/') for r in ignore_rules() if r.startswith('!')}
        sources = set(copy_sources())
        self.assertTrue(sources, 'Dockerfile has no COPY lines')
        self.assertEqual(allowed, sources)

    def test_copy_sources_exist(self):
        for src in copy_sources():
            self.assertTrue((ROOT / src).exists(), src)

    def test_output_stays_out_of_context(self):
        allowed = {r[1:].rstrip('/') for r in ignore_rules() if r.startswith('!')}
        self.assertFalse(any(a == 'output' or a.startswith('output/') for a in allowed))


if __name__ == '__main__':
    unittest.main()
