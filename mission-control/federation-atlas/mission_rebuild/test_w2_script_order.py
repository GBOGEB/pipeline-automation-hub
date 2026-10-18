"""W2 page script-order contract (static; runs without Plotly installed).

Regression: native W2 QA timed out (30 s) waiting for '.inlay .js-plotly-plot'.
plotly.io.to_html(include_plotlyjs=False, full_html=False) emits each card as a
div plus an inline <script> that calls Plotly.newPlot immediately, but the page
injected the Plotly library only after </main>, so every inline call ran before
Plotly existed and no inlay mounted. Same class as N3 fix dabefbc.
"""
import re
import unittest
from pathlib import Path

SRC = (Path(__file__).resolve().parent / "w2_plotly.py").read_text(encoding="utf-8")


def template():
    m = re.search(r"page=r'''(.*?)'''", SRC, flags=re.S)
    if m is None:
        raise AssertionError("W2 page template not found")
    return m.group(1)


class W2ScriptOrderTests(unittest.TestCase):
    def setUp(self):
        self.t = template()

    def test_library_loads_before_cards(self):
        lib = self.t.index("<script>__PLOTLY_LIBRARY__</script>")
        self.assertLess(lib, self.t.index("__CARDS__"))
        self.assertLess(self.t.index("<body>"), lib)

    def test_library_injected_exactly_once(self):
        self.assertEqual(self.t.count("__PLOTLY_LIBRARY__"), 1)

    def test_cards_still_use_inline_fragments_without_bundled_library(self):
        # The order contract above only matters because fragments are inline newPlot calls.
        self.assertIn("include_plotlyjs=False", SRC)
        self.assertIn("full_html=False", SRC)

    def test_inlays_resized_after_grid_mount(self):
        self.assertRegex(self.t, r'addEventListener\("load".*Plotly\.Plots\.resize')

    def test_modal_and_filters_after_library(self):
        lib = self.t.index("__PLOTLY_LIBRARY__")
        self.assertLess(lib, self.t.index('Plotly.newPlot("expanded"'))
        self.assertLess(lib, self.t.index('id="plot-specs"'))

    def test_seeded_negative_old_order_detected(self):
        old = self.t.replace("<body><script>__PLOTLY_LIBRARY__</script>", "<body>", 1).replace(
            "</main>", "</main><script>__PLOTLY_LIBRARY__</script>", 1)
        self.assertGreater(old.index("__PLOTLY_LIBRARY__"), old.index("__CARDS__"))


if __name__ == "__main__":
    unittest.main()
