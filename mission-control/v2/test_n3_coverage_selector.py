"""Regression: focused coverage must exclude test modules with shared suffixes."""
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MODULES = ('n3_continuation.py', 'n3_integrity.py',
           'n3_metrics.py', 'n3_dashboard.py')


class CoverageSelectorTests(unittest.TestCase):
    def test_exact_basename_excludes_tests(self):
        paths = ([f'mission-control/v2/{name}' for name in MODULES]
                 + [f'mission-control/v2/test_{name}' for name in MODULES])
        matching = [p for p in paths if Path(p).name in MODULES]
        self.assertEqual(len(matching), 4)
        self.assertFalse(any(Path(p).name.startswith('test_') for p in matching))
        self.assertEqual(len([p for p in paths if p.endswith(MODULES)]), 8)

    def test_native_workflow_uses_exact_basename(self):
        path = ROOT / '.github/workflows/mission-control-n3-evidence.yml'
        contents = path.read_text(encoding='utf-8')
        self.assertIn('Path(k).name in modules', contents)
        self.assertNotIn('k.endswith(modules)', contents)


if __name__ == '__main__':
    unittest.main()
