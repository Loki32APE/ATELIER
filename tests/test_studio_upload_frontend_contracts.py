"""Static contracts for Vision Studio image upload UX validation."""
from pathlib import Path
import unittest


class StudioUploadFrontendContractTests(unittest.TestCase):
    def test_file_inputs_match_server_supported_image_formats(self):
        source = (Path(__file__).parents[1] / "templates/partials/studio.html").read_text()
        self.assertEqual(source.count('accept="image/jpeg,image/png,image/webp"'), 2)
        self.assertNotIn('accept="image/*"', source)

    def test_client_checks_file_type_and_size_before_preview(self):
        source = (Path(__file__).parents[1] / "static/js/image-upload.js").read_text()
        self.assertIn('new Set(["image/jpeg", "image/png", "image/webp"])', source)
        self.assertIn("file.size > 4 * 1024 * 1024", source)
        self.assertLess(source.index("allowedImageTypes.has(file.type)"), source.index("files[slot] = file"))


if __name__ == "__main__":
    unittest.main()
