"""Adversarial static HTML QA checks; no published admission from parser success."""
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from html_contract import inspect, resolve_reference

BASE = "<!doctype html><html><head><title>QA</title><meta name='viewport' content='width=device-width'></head><body><h1>QA</h1>{}</body></html>"


class HTMLContractTests(unittest.TestCase):
    def run_html(self, extra="", assets=()):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            for name in assets:
                f=root/name
                f.parent.mkdir(exist_ok=True,parents=True)
                f.write_text("fixture")
            return inspect(BASE.format(extra),base_dir=root)

    def fail(self, source, term):
        self.assertTrue(any(term in x for x in source["errors"]), source)

    def test_positive_named_button_and_labelled_select(self):
        r=self.run_html("<label>Refresh<select id='interval'><option>Manual</option></select></label><button>Reload</button>")
        self.assertEqual(r["status"],"PASS")
        self.assertEqual((r["button_count"],r["select_count"]),(1,1))

    def test_local_link_file_exists(self):
        self.assertEqual(self.run_html("<a href='metrics.json'>data</a>",assets=['metrics.json'])["status"],"PASS")

    def test_external_link_secured(self):
        r=self.run_html("<a href='https://github.com/GBOGEB/pipeline-automation-hub' target='_blank' rel='noopener noreferrer'>GitHub</a>")
        self.assertEqual(r["status"],"PASS")

    def test_hidden_dynamic_link_waits_for_browser_qa(self):
        r=self.run_html("<a id='sourceLink' hidden target='_blank' rel='noopener noreferrer'>Open selected source</a>")
        self.assertEqual(r["status"],"PASS")

    def test_duplicate_ids_fail(self):
        self.fail(self.run_html("<b id='a'></b><i id='a'></i>"),"DUPLICATE_DOM_IDS")

    def test_broken_anchor_fails(self):
        self.fail(self.run_html("<a href='#missing'>Missing</a>"),"BROKEN_INTERNAL_ANCHOR")

    def test_resolved_anchor_passes(self):
        self.assertEqual(self.run_html("<a href='#here'>Here</a><section id='here'></section>")["status"],"PASS")

    def test_missing_local_link_fails(self):
        self.fail(self.run_html("<a href='gone.html'>Gone</a>"),"MISSING_LOCAL_FILE")

    def test_script_scheme_rejected(self):
        self.fail(self.run_html("<a href='javascript:alert(1)'>Bad</a>"),"UNSAFE_SCHEME")

    def test_protocol_relative_forbidden(self):
        self.fail(self.run_html("<a href='//attacker.example/path'>Bad</a>"),"PROTOCOL_RELATIVE_URL_FORBIDDEN")

    def test_absolute_site_path_not_portable(self):
        self.fail(self.run_html("<a href='/some/path'>Absolute</a>"),"ABSOLUTE_SITE_PATH_NOT_PORTABLE")

    def test_parent_directory_escape_fails(self):
        self.fail(self.run_html("<a href='../outside.html'>Bad</a>"),"LOCAL_PATH_ESCAPE")

    def test_unsecured_new_window_rejected(self):
        self.fail(self.run_html("<a href='https://github.com' target='_blank'>Unsafe</a>"),"UNSAFE_NEW_TAB")

    def test_unlabelled_button_rejected(self):
        self.fail(self.run_html("<button></button>"),"BUTTON_WITHOUT_ACCESSIBLE_NAME")

    def test_named_button_aria_passes(self):
        self.assertEqual(self.run_html("<button aria-label='Reload'></button>")["status"],"PASS")

    def test_unlabelled_select_rejected(self):
        self.fail(self.run_html("<select id='x'><option>a</option></select>"),"UNLABELED_SELECT")

    def test_label_for_passes(self):
        self.assertEqual(self.run_html("<label for='x'>Kind</label><select id='x'></select>")["status"],"PASS")

    def test_unlabelled_image_rejected(self):
        self.fail(self.run_html("<img src='a.png'>",assets=["a.png"]),"IMAGE_WITHOUT_ALT")

    def test_missing_image_file_rejected(self):
        self.fail(self.run_html("<img src='missing.png' alt='test'>"),"ASSET_MISSING_LOCAL_FILE")

    def test_missing_title_rejected(self):
        self.fail(self.run_html("").__class__ and inspect(BASE.replace("<title>QA</title>","").format(""),base_dir=Path(".")),"MISSING_TITLE")

    def test_primary_heading_required(self):
        self.fail(inspect("<html><head><title>X</title><meta name='viewport' content='x'></head><body></body></html>",base_dir=Path(".")),"MISSING_OR_MULTIPLE_H1")

    def test_viewport_required(self):
        self.fail(inspect("<html><head><title>X</title></head><body><h1>X</h1></body></html>",base_dir=Path(".")),"MISSING_VIEWPORT_META")

    def test_script_http_fails(self):
        self.fail(self.run_html("<script src='http://example.com/a.js'></script>"),"INSECURE_SCRIPT_DEPENDENCY")

    def test_stable_no_mutation(self):
        source=BASE.format("<button>Next</button>")
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(inspect(source,base_dir=Path(d)),inspect(source,base_dir=Path(d)))
        self.assertIn("<button>",source)

    def test_html_schema_and_hold(self):
        p=self.run_html("<button>Done</button>")
        self.assertEqual(p["merge_admission"],"HOLD")
        self.assertIs(p["authority_transfer"],False)

if __name__=="__main__":
    unittest.main()
