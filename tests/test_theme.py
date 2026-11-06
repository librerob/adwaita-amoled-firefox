"""Check role coverage, compound states, generation and package contents."""

import json
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from contrast import over, ratio
from theme import ROLES, manifest, package, rendered


class ThemeTests(unittest.TestCase):
    def setUp(self):
        self.p = json.loads((ROOT / "palette.json").read_text())
        self.m = manifest()

    def test_generation(self):
        self.assertEqual((ROOT / "theme/manifest.json").read_text(), rendered())
        self.assertEqual(set(ROLES.values()), set(self.p))

    def test_static_boundary(self):
        self.assertFalse(set(self.m) & {"permissions", "host_permissions", "background", "content_scripts", "theme_experiment"})
        self.assertNotIn("images", self.m["theme"])
        self.assertNotIn("dark_theme", self.m)
        self.assertEqual(self.m["theme"]["properties"], {"color_scheme": "dark", "content_color_scheme": "dark"})

    def test_known_inactive_keys_are_omitted(self):
        self.assertFalse(set(self.m["theme"]["colors"]) & {
            "sidebar_highlight", "sidebar_highlight_text", "tab_loading",
            "tab_background_separator", "toolbar_field_separator", "popup_icons"
        })

    def test_text_and_compound_states(self):
        samples = []
        for surface in ("background", "surface", "raised"):
            for state in (None, "hover", "pressed"):
                bg = self.p[surface] if state is None else over(self.p[state], self.p[surface])
                for foreground in ("foreground", "secondary"):
                    value = ratio(self.p[foreground], bg)
                    self.assertGreaterEqual(value, 7, (foreground, surface, state, value))
                    samples.append(value)
                self.assertGreaterEqual(ratio(self.p["accent"], bg), 3)
        self.assertEqual(len(samples), 18)

    def test_selection_pairs(self):
        self.assertGreaterEqual(ratio(self.p["on_selection"], self.p["selection"]), 4.5)
        self.assertGreaterEqual(ratio(self.p["on_accent"], self.p["accent"]), 7)
        # Guard against accidentally applying the normal label color to a blue fill.
        self.assertLess(ratio(self.p["foreground"], self.p["selection"]), 4.5)

    def test_indicators(self):
        for surface in ("background", "surface", "raised"):
            self.assertGreaterEqual(ratio(self.p["accent"], self.p[surface]), 7)
            self.assertGreaterEqual(ratio(self.p["control_border"], self.p[surface]), 3)
            self.assertGreaterEqual(ratio(self.p["selection"], self.p[surface]), 3)
        self.assertNotEqual(self.p["raised"], self.p["background"])
        self.assertEqual(self.m["theme"]["colors"]["tab_line"], self.p["accent"])

    def test_reference_math(self):
        self.assertEqual(ratio("#ffffff", "#000000"), 21)
        self.assertEqual(ratio("#777777", "#777777"), 1)
        self.assertAlmostEqual(ratio("#ffffff", "#2d6be0"), 4.894, places=3)
        self.assertEqual(over("rgba(255,255,255,0.5)", "#000000"), (127.5, 127.5, 127.5, 1))

    def test_archive(self):
        with tempfile.TemporaryDirectory() as temp:
            xpi = package(temp)
            first = xpi.read_bytes()
            self.assertEqual(package(temp).read_bytes(), first)
            self.assertEqual(xpi.with_suffix(".zip").read_bytes(), first)
            with zipfile.ZipFile(xpi) as archive:
                self.assertEqual(archive.namelist(), ["LICENSE", "icon.svg", "manifest.json"])
                self.assertEqual(json.loads(archive.read("manifest.json")), self.m)
                self.assertIsNone(archive.testzip())


if __name__ == "__main__":
    unittest.main()
