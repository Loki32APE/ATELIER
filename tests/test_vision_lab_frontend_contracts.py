"""Static contracts for critical Vision Lab browser/server payload boundaries."""
from pathlib import Path
import unittest


class VisionLabFrontendContractTests(unittest.TestCase):
    def test_target_model_uses_server_contract_key(self):
        source = (Path(__file__).parents[1] / "static/js/vision-lab.js").read_text()
        self.assertIn("target_model_id:root.querySelector('#vlModel').value", source)
        self.assertNotIn("target_target_model_id", source)

    def test_profile_round_trip_uses_target_model_id(self):
        source = (Path(__file__).parents[1] / "static/js/vision-lab.js").read_text()
        self.assertIn("data.target_model_id||''", source)
        self.assertIn("target_model_id:root.querySelector('#vlModel').value", source)

    def test_generated_prompt_has_explicit_edit_and_revalidation_workflow(self):
        source = (Path(__file__).parents[1] / "static/js/vision-lab.js").read_text()
        self.assertIn("prompt.readOnly=true", source)
        self.assertIn("prompt.readOnly=false", source)
        self.assertIn("Done editing", source)
        self.assertIn("insertBefore(editButton,root.querySelector('#vlValidateBtn'))", source)
        self.assertIn("prompt.readOnly=true;editButton.textContent='Edit';showToast(data.quality.passed", source)

    def test_studio_preview_urls_are_released_when_replaced_or_cleared(self):
        source = (Path(__file__).parents[1] / "static/js/image-upload.js").read_text()
        self.assertIn("const previewObjectUrls = { look: null, outfit: null }", source)
        self.assertIn("URL.revokeObjectURL(previousUrl)", source)
        self.assertIn("releasePreviewUrl(slot);", source)
        self.assertIn("previewObjectUrls[slot] = URL.createObjectURL(file)", source)

    def test_prompt_language_preference_is_sent_with_generation_payload(self):
        source = (Path(__file__).parents[1] / "static/js/vision-lab.js").read_text()
        self.assertIn("localStorage.getItem('ape_settings_v1')", source)
        self.assertIn("return {mode,language,instructions:", source)
        self.assertIn("saved.language", source)

    def test_generation_result_announces_applied_output_language(self):
        source = (Path(__file__).parents[1] / "static/js/vision-lab.js").read_text()
        self.assertIn("Output language:", source)

    def test_vision_lab_remains_text_only(self):
        source = (Path(__file__).parents[1] / "templates/partials/scratchpad.html").read_text()
        self.assertIn("Image references belong exclusively to Vision Studio", source)
        self.assertNotIn('type="file"', source)


if __name__ == "__main__":
    unittest.main()
