"""Contract tests for the shared browser catalog service."""
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class CatalogServiceContractTests(unittest.TestCase):
    def read(self, relative_path):
        return (ROOT / relative_path).read_text(encoding="utf-8")

    def test_catalog_service_is_loaded_before_consumers(self):
        template = self.read("templates/index.html")
        service = template.index("js/catalog-service.js")
        theme = template.index("js/theme.js")
        jewellery = template.index("js/jewellery.js")
        self.assertLess(service, theme)
        self.assertLess(service, jewellery)

    def test_catalog_service_restricts_paths_to_catalog_root(self):
        service = self.read("static/js/catalog-service.js")
        self.assertIn('const ROOT = "/static/Catalog/";', service)
        self.assertIn("const FILE_PATH =", service)
        self.assertIn("function catalogPath(path)", service)
        self.assertIn("loadThemeCatalog", service)
        self.assertIn("loadLayer4Catalog", service)
        self.assertIn("loadCameraCatalog", service)


    def test_shared_settings_globals_have_single_owner(self):
        paths = (
            "static/js/theme.js",
            "static/js/jewellery.js",
            "static/js/appearance.js",
        )
        sources = [self.read(path) for path in paths]
        for function_name in (
            "sanitizeSelections",
            "buildCameraBody",
            "buildThemeBody",
            "buildArtBody",
            "buildSimple",
            "clearAllSettings",
            "renderSettingsV1",
        ):
            declarations = sum(
                source.count("function " + function_name + "(")
                for source in sources
            )
            self.assertEqual(declarations, 1, function_name)


    def test_legacy_global_helpers_have_single_owner(self):
        javascript_files = list((ROOT / "static" / "js").glob("*.js"))
        combined = "\n".join(path.read_text(encoding="utf-8") for path in javascript_files)
        for function_name in ("toggleCategoryNode", "showScratchModel"):
            self.assertEqual(
                combined.count("function " + function_name + "("),
                1,
                function_name,
            )

    def test_catalog_consumers_use_the_shared_service(self):
        for relative_path in ("static/js/theme.js", "static/js/jewellery.js"):
            source = self.read(relative_path)
            self.assertIn("AtelierCatalogService.", source, relative_path)
            self.assertNotIn("fetch(", source, relative_path)


    def test_visual_lab_catalog_covers_all_seven_modules_with_valid_fields(self):
        import json

        catalog = json.loads(self.read("static/Catalog/visual_lab/modules.json"))
        expected_modules = {
            "appearance_identity",
            "outfit_styling",
            "poses_expressions",
            "themes_environment",
            "lighting_composition",
            "camera_photography",
            "output_rendering",
        }
        self.assertEqual(set(catalog["modules"]), expected_modules)

        for module_id, definition in catalog["modules"].items():
            with self.subTest(module=module_id):
                self.assertTrue(definition.get("basic"), "Basic fields must exist")
                self.assertTrue(definition.get("advanced"), "Advanced fields must exist")
                for mode in ("basic", "advanced"):
                    field_ids = set()
                    for field in definition[mode]:
                        self.assertIn(field.get("type"), {"select", "multi"})
                        self.assertTrue(field.get("id"))
                        self.assertNotIn(field["id"], field_ids)
                        field_ids.add(field["id"])
                        options = field.get("options")
                        self.assertIsInstance(options, list)
                        self.assertTrue(options)
                        self.assertTrue(all(isinstance(option, str) and option.strip() for option in options))
                        self.assertEqual(len(options), len(set(options)))

    def test_catalog_manifests_reference_existing_safe_json_paths(self):
        import json
        import re

        catalog_root = ROOT / "static" / "Catalog"
        index = json.loads((catalog_root / "index.json").read_text(encoding="utf-8"))
        layer4 = json.loads((catalog_root / "layer4.json").read_text(encoding="utf-8"))
        safe_segment = re.compile(r"^[A-Za-z0-9_-]+$")

        for theme in index["themes"]:
            with self.subTest(theme=theme.get("id")):
                self.assertRegex(theme["id"], safe_segment)
                relative = Path(theme["file"])
                self.assertFalse(relative.is_absolute())
                self.assertNotIn("..", relative.parts)
                self.assertEqual(relative.suffix, ".json")
                self.assertTrue((catalog_root / relative).is_file())

        for category in layer4["categories"]:
            with self.subTest(category=category.get("id")):
                self.assertRegex(category["id"], safe_segment)
                for file_id in category["files"]:
                    self.assertRegex(file_id, safe_segment)
                    self.assertTrue((catalog_root / category["id"] / (file_id + ".json")).is_file())

    def test_catalog_service_uses_strict_json_path_allowlist(self):
        service = self.read("static/js/catalog-service.js")
        self.assertIn("const FILE_PATH =", service)
        self.assertIn('const SEGMENT = /^[A-Za-z0-9_-]+$/;', service)
        self.assertNotIn("path.startsWith(ROOT)", service)
        self.assertIn("catalogPath(ROOT + item.file)", service)
        self.assertIn('catalogSegment(category.id, "category id")', service)
        self.assertIn('catalogSegment(file, "file id")', service)

    def test_shared_request_cache_cannot_be_aborted_by_one_consumer(self):
        service = self.read("static/js/catalog-service.js")
        self.assertNotIn("options.signal", service)
        self.assertIn("let cacheGeneration = 0;", service)
        self.assertIn("if (pending.get(url) === request) pending.delete(url);", service)
        self.assertIn("cacheGeneration += 1;", service)

    def test_visual_lab_catalog_service_loads_before_every_consumer(self):
        template = self.read("templates/index.html")
        service = template.index("js/catalog-service.js")
        for consumer in ("js/vision-lab.js", "js/theme.js", "js/jewellery.js"):
            with self.subTest(consumer=consumer):
                self.assertLess(service, template.index(consumer))


if __name__ == "__main__":
    unittest.main()
