"""Static contracts for the approved Atelier Darkroom brand assets."""
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).parents[1]


class BrandAssetTests(unittest.TestCase):
    def test_design_tokens_match_approved_palette(self):
        tokens = json.loads((ROOT / "static/brand-tokens.json").read_text())
        self.assertEqual(tokens["visualDirection"], "Darkroom Obsidian & Warm Archival Paper")
        self.assertEqual(tokens["colors"]["darkroomBase"], "#111215")
        self.assertEqual(tokens["colors"]["darkroomSurface"], "#181A1F")
        self.assertEqual(tokens["colors"]["accent"], "#E04F33")
        self.assertEqual(tokens["colors"]["archivalBase"], "#F6F4EF")
        self.assertEqual(tokens["typography"]["display"], "Instrument Sans")
        self.assertEqual(tokens["typography"]["applicationUI"], "Plus Jakarta Sans")
        self.assertEqual(tokens["typography"]["promptEditorAndTechnical"], "JetBrains Mono")

    def test_brand_tokens_load_before_core_styles(self):
        source = (ROOT / "templates/index.html").read_text()
        token_link = source.index("css/brand-tokens.css")
        core_link = source.index("filename='style.css'")
        self.assertLess(token_link, core_link)
        self.assertIn("family=Instrument+Sans", source)
        self.assertIn("family=Plus+Jakarta+Sans", source)
        self.assertIn("family=JetBrains+Mono", source)

    def test_wordmark_is_present_and_uses_brand_palette(self):
        source = (ROOT / "static/brand/atelier-wordmark.svg").read_text()
        self.assertIn("#E04F33", source)
        self.assertIn("#F3F2EE", source)
        self.assertIn("Atelier", source)
        self.assertIn("PROMPT ENGINE", source)

    def test_home_uses_clean_emblem_from_asset_pack(self):
        source = (ROOT / "templates/partials/home.html").read_text()
        self.assertIn("brand/atelier-mark.svg", source)
        self.assertTrue((ROOT / "static/brand/atelier-mark.svg").is_file())
        self.assertNotIn("filename='logo.png'", source)


    def test_catalog_json_files_are_valid_and_theme_index_is_complete(self):
        catalog_root = ROOT / "static/Catalog"
        json_files = sorted(catalog_root.rglob("*.json"))
        self.assertGreater(len(json_files), 10, "Expected the active catalog data set")

        parsed = {}
        for path in json_files:
            with self.subTest(catalog_file=str(path.relative_to(ROOT))):
                parsed[path] = json.loads(path.read_text(encoding="utf-8"))

        index = parsed[catalog_root / "index.json"]
        self.assertEqual(index["version"], "catalog-v2")
        self.assertTrue(index["themes"])
        theme_ids = set()
        for theme in index["themes"]:
            self.assertNotIn(theme["id"], theme_ids, "Theme IDs must be unique")
            theme_ids.add(theme["id"])
            theme_path = (catalog_root / theme["file"]).resolve()
            self.assertTrue(theme_path.is_relative_to(catalog_root.resolve()))
            self.assertIn(theme_path, parsed, f"Missing indexed theme file: {theme['file']}")
            self.assertEqual(parsed[theme_path].get("id"), theme["id"])

    def test_active_frontend_has_no_retired_appearance_json_endpoint(self):
        scripts = sorted((ROOT / "static/js").glob("*.js"))
        self.assertTrue(scripts)
        for path in scripts:
            with self.subTest(script=path.name):
                source = path.read_text(encoding="utf-8")
                self.assertNotIn("/static/data/appearance.json", source)


if __name__ == "__main__":
    unittest.main()
