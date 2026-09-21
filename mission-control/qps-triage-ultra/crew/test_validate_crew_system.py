import importlib.util
import pathlib
import unittest

HERE = pathlib.Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location(
    "validate_crew_system", HERE / "validate_crew_system.py"
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class ConceptualControlTypeTests(unittest.TestCase):
    def test_accepts_json_false(self):
        self.assertTrue(MODULE.conceptual_control_allowed(False))

    def test_accepts_future_marker(self):
        self.assertTrue(MODULE.conceptual_control_allowed("BOUNDED_AFTER_PROMOTION"))

    def test_rejects_numeric_and_other_values(self):
        for value in (0, 1, None, "", "false", "CONTROL"):
            with self.subTest(value=value):
                self.assertFalse(MODULE.conceptual_control_allowed(value))


if __name__ == "__main__":
    unittest.main()
