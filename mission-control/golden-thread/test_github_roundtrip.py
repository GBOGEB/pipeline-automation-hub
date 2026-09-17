import copy
import json
import tempfile
import unittest
from pathlib import Path

import github_roundtrip as gr


class GitHubRoundTripTests(unittest.TestCase):
    def setUp(self):
        self.truth = {
            "schema": "missioncontrol.test_truth.v1",
            "semantic_generation_k": 7,
            "event_sequence_e": 42,
            "values": {"alpha": 1, "beta": [2, 3]},
            "authority_transfer": False,
        }

    def test_builds_seven_semantically_equal_renditions(self):
        files, manifest = gr.build_bundle(self.truth)
        self.assertEqual(len(files), 7)
        self.assertEqual(
            set(files),
            {
                "GOLDEN_THREAD_TRUTH.json",
                "GOLDEN_THREAD_TRUTH.yaml",
                "GOLDEN_THREAD_TRUTH.md",
                "GOLDEN_THREAD_TRUTH.html",
                "GOLDEN_THREAD_TRUTH.docx",
                "GOLDEN_THREAD_TRUTH.xlsx",
                "GOLDEN_THREAD_TRUTH.pptx",
            },
        )
        self.assertFalse(manifest["authority_transfer"])
        self.assertFalse(manifest["visual_fidelity_credit"])
        receipt = gr.verify_bundle(self.truth, files)
        self.assertEqual(receipt["status"], "PASS")
        self.assertEqual(receipt["rendition_count"], 7)

    def test_bundle_is_byte_deterministic(self):
        files_a, manifest_a = gr.build_bundle(self.truth)
        files_b, manifest_b = gr.build_bundle(self.truth)
        self.assertEqual(files_a, files_b)
        self.assertEqual(manifest_a, manifest_b)

    def test_changed_truth_changes_every_semantic_extraction(self):
        files, _ = gr.build_bundle(self.truth)
        changed = copy.deepcopy(self.truth)
        changed["values"]["alpha"] = 99
        receipt = gr.verify_bundle(changed, files)
        self.assertEqual(receipt["status"], "FAIL")
        self.assertTrue(all(v["status"] == "FAIL" for v in receipt["results"].values()))

    def test_office_zip_metadata_is_not_semantic_credit(self):
        files, _ = gr.build_bundle(self.truth)
        receipt = gr.verify_bundle(self.truth, files)
        for name in ("GOLDEN_THREAD_TRUTH.docx", "GOLDEN_THREAD_TRUTH.xlsx", "GOLDEN_THREAD_TRUTH.pptx"):
            self.assertEqual(receipt["results"][name]["status"], "PASS")
        self.assertFalse(receipt["visual_fidelity_credit"])


if __name__ == "__main__":
    unittest.main()
