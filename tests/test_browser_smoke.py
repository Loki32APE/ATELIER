"""Chromium smoke tests for desktop and mobile workspace navigation."""
import json
from pathlib import Path
import unittest
from threading import Thread

from werkzeug.serving import make_server

try:
    from playwright.sync_api import sync_playwright
except ImportError:  # The normal Python unit-test job intentionally omits browsers.
    sync_playwright = None

from app import app


@unittest.skipIf(sync_playwright is None, "Playwright is installed only in the browser CI job")
class BrowserSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = make_server("127.0.0.1", 0, app)
        cls.base_url = f"http://127.0.0.1:{cls.server.server_port}"
        cls.server_thread = Thread(target=cls.server.serve_forever, daemon=True)
        cls.server_thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server_thread.join(timeout=5)

    def test_desktop_home_and_workspace_navigation(self):
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page(viewport={"width": 1440, "height": 900})
            page_errors = []
            page.on("pageerror", lambda error: page_errors.append(str(error)))

            response = page.goto(self.base_url, wait_until="networkidle")
            self.assertEqual(response.status, 200)
            self.assertEqual(page.title(), "Atelier Prompt Engine")
            self.assertTrue(page.locator("#tab-home").is_visible())
            self.assertTrue(page.locator(".home-headline").is_visible())

            page.locator(".cta-ghost").click()
            self.assertTrue(page.locator("#tab-scratchpad").is_visible())
            page.evaluate("switchMainTab('studio')")
            self.assertTrue(page.locator("#tab-studio").is_visible())
            self.assertEqual(page_errors, [])
            browser.close()

    def test_desktop_sidebar_collapses_after_navigation_and_can_reopen(self):
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page(viewport={"width": 1440, "height": 900})
            page.goto(self.base_url, wait_until="networkidle")

            toggle = page.get_by_role("button", name="Toggle navigation")
            self.assertEqual(toggle.get_attribute("aria-expanded"), "false")
            toggle.click()
            page.locator("#drawer [data-tab='studio']").click()
            self.assertIn("sidebar-collapsed", page.locator("body").get_attribute("class"))
            self.assertEqual(toggle.get_attribute("aria-expanded"), "false")
            toggle.click()
            self.assertNotIn("sidebar-collapsed", page.locator("body").get_attribute("class"))
            self.assertEqual(toggle.get_attribute("aria-expanded"), "true")
            browser.close()

    def test_library_controls_stay_full_width_on_phone(self):
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page(viewport={"width": 390, "height": 844})
            page.goto(self.base_url, wait_until="networkidle")
            page.evaluate("switchMainTab('library')")

            search_width = page.locator("#librarySearch").evaluate("el => el.getBoundingClientRect().width")
            filter_width = page.locator("#libraryProjectFilter").evaluate("el => el.getBoundingClientRect().width")
            self.assertGreater(search_width, 250)
            self.assertGreater(filter_width, 250)
            dimensions = page.evaluate("() => ({width: innerWidth, scrollWidth: document.documentElement.scrollWidth})")
            self.assertLessEqual(dimensions["scrollWidth"], dimensions["width"] + 1)
            browser.close()

    def test_vision_lab_and_studio_mode_controls_work_without_model_calls(self):
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page(viewport={"width": 1280, "height": 900})
            page_errors = []
            page.on("pageerror", lambda error: page_errors.append(str(error)))
            page.goto(self.base_url, wait_until="networkidle")

            page.locator("#tab-home").get_by_role("button", name="Visual Lab").click()
            lab = page.locator("#tab-scratchpad")
            self.assertTrue(lab.is_visible())
            self.assertEqual(lab.locator(".vl-module-card").count(), 7)
            self.assertEqual(lab.locator("input[type='file']").count(), 0)
            self.assertGreater(lab.locator("[data-vl-choice]").count(), 20)
            presentation = lab.locator("[data-vl-choice='presentation']")
            presentation.select_option(label="Feminine")
            lab.locator(".vl-mode[data-mode='advanced']").click()
            self.assertEqual(lab.get_attribute("data-mode"), "advanced")
            self.assertTrue(lab.locator("[data-vl-extra]").first.is_visible())
            facial_structure = lab.locator("[data-vl-choice='facial_structure']")
            self.assertTrue(facial_structure.is_visible())
            facial_structure.select_option(label="Soft oval")
            lab.locator(".vl-mode[data-mode='basic']").click()
            self.assertEqual(lab.get_attribute("data-mode"), "basic")
            self.assertEqual(presentation.input_value(), "Feminine")
            lab.locator(".vl-mode[data-mode='advanced']").click()
            self.assertEqual(facial_structure.input_value(), "Soft oval")

            page.evaluate("switchMainTab('studio')")
            studio = page.locator("#tab-studio")
            self.assertEqual(studio.locator("input[type='file']").count(), 2)
            for upload in studio.locator("input[type='file']").all():
                self.assertEqual(upload.get_attribute("accept"), "image/jpeg,image/png,image/webp")
            studio.locator("#studioModeAdvanced").click()
            self.assertEqual(studio.get_attribute("data-mode"), "advanced")
            self.assertTrue(studio.locator("#advancedControlsWrapper").is_visible())
            studio.locator("#studioModeBasic").click()
            self.assertEqual(studio.get_attribute("data-mode"), "basic")
            self.assertEqual(page_errors, [], f"Workspace JavaScript errors: {page_errors}")
            browser.close()

    def test_primary_home_controls_have_accessible_names(self):
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page(viewport={"width": 1280, "height": 800})
            page.goto(self.base_url, wait_until="networkidle")

            home = page.locator("#tab-home")
            for accessible_name in ("Profile", "Studio Mode", "Visual Lab"):
                control = home.get_by_role("button", name=accessible_name)
                self.assertEqual(control.count(), 1, accessible_name)
                self.assertTrue(control.is_visible(), accessible_name)

            missing_alt = page.locator("#tab-home img:not([alt])").count()
            self.assertEqual(missing_alt, 0)
            logo = page.locator("#tab-home .home-logo")
            self.assertTrue(logo.evaluate("(image) => image.complete && image.naturalWidth > 0"),
                            "The supplied Atelier horizontal logo should load successfully")
            browser.close()

    def test_home_has_no_horizontal_overflow_at_common_breakpoints(self):
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page(viewport={"width": 390, "height": 844}, device_scale_factor=1)
            page.goto(self.base_url, wait_until="networkidle")
            for width in (320, 360, 390, 768, 1024, 1440):
                with self.subTest(viewport_width=width):
                    page.set_viewport_size({"width": width, "height": 900})
                    page.wait_for_timeout(100)
                    dimensions = page.evaluate(
                        "() => ({width: window.innerWidth, scrollWidth: document.documentElement.scrollWidth})"
                    )
                    self.assertLessEqual(
                        dimensions["scrollWidth"], dimensions["width"] + 1,
                        f"Horizontal overflow at {width}px: {dimensions}",
                    )
            browser.close()

    def test_home_layout_adapts_to_the_actual_viewport(self):
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page(viewport={"width": 1440, "height": 900})
            page.goto(self.base_url, wait_until="networkidle")

            self.assertEqual(page.locator("#viewDesktopBtn, #viewMobileBtn").count(), 0)
            self.assertIsNone(page.locator("body").get_attribute("data-view-mode"))
            self.assertFalse(page.get_by_role("navigation", name="Primary navigation").is_visible())

            page.set_viewport_size({"width": 390, "height": 844})
            self.assertTrue(page.get_by_role("navigation", name="Primary navigation").is_visible())
            self.assertFalse(page.locator(".menu-btn").is_visible())
            dimensions = page.evaluate("() => ({width: innerWidth, scrollWidth: document.documentElement.scrollWidth})")
            self.assertLessEqual(dimensions["scrollWidth"], dimensions["width"] + 1)

            page.set_viewport_size({"width": 1280, "height": 900})
            self.assertFalse(page.get_by_role("navigation", name="Primary navigation").is_visible())
            browser.close()

    def test_unified_library_projects_favorites_history_and_comparison(self):
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page(viewport={"width": 1280, "height": 900})
            page.goto(self.base_url, wait_until="networkidle")
            page.evaluate("""() => {
                localStorage.setItem("pe_looks", JSON.stringify([
                    {id:"prompt-v1", name:"Editorial portrait", prompt:"Version one portrait prompt", optimized:"", raw:"", ts:"2026-11-11"},
                    {id:"prompt-v2", name:"Editorial portrait", prompt:"Version two portrait prompt", optimized:"", raw:"", ts:"2026-11-11", versionGroupId:"prompt-v1", version:2}
                ]));
                localStorage.setItem("pe_history", JSON.stringify([
                    {id:"history-1", name:"Recent generation", prompt:"A recent cinematic portrait prompt", ts:"2026-11-11"}
                ]));
            }""")
            page.reload(wait_until="networkidle")
            page.evaluate("switchMainTab('library')")
            library = page.locator("#tab-library")
            self.assertTrue(library.is_visible())
            self.assertEqual(library.locator("#libraryPromptList .library-item-card").count(), 2)

            library.get_by_role("tab", name="My Projects").click()
            library.locator("#libraryProjectName").fill("Editorial Series")
            library.locator("#libraryProjectDescription").fill("Portrait experiments")
            library.locator("#libraryProjectForm button[type='submit']").click()
            self.assertEqual(library.locator("#libraryProjectList .library-project-card").count(), 1)

            prompt_tab = library.get_by_role("tab", name="Prompt Library")
            prompt_tab.focus()
            page.keyboard.press("ArrowRight")
            self.assertEqual(library.locator("#library-tab-references").get_attribute("aria-selected"), "true")
            page.keyboard.press("ArrowLeft")
            self.assertEqual(library.locator("#library-tab-prompts").get_attribute("aria-selected"), "true")
            page.keyboard.press("End")
            self.assertEqual(library.locator("#library-tab-history").get_attribute("aria-selected"), "true")
            page.keyboard.press("Home")
            self.assertEqual(library.locator("#library-tab-projects").get_attribute("aria-selected"), "true")
            library.get_by_role("tab", name="Prompt Library").click()
            library.get_by_role("button", name="☆ Favorite").first.click()
            library.get_by_role("tab", name="Favorites").click()
            self.assertEqual(library.locator("#libraryFavoriteList .library-item-card").count(), 1)

            library.get_by_role("tab", name="Prompt Library").click()
            library.locator("#libraryPromptList input[type='checkbox']").nth(0).check()
            library.locator("#libraryPromptList input[type='checkbox']").nth(1).check()
            library.locator("#libraryCompareBtn").click()
            self.assertFalse(library.locator("#libraryComparePanel").is_hidden())
            self.assertIn("Version one", library.locator("#libraryCompareA").input_value())
            self.assertIn("Version two", library.locator("#libraryCompareB").input_value())

            library.locator("#libraryComparePanel").get_by_role("button", name="Close").click()
            library.get_by_role("button", name="Save as new version").first.click()
            self.assertTrue(page.locator("#tab-studio").is_visible())
            self.assertEqual(page.evaluate("window.ATELIER_VERSION_SOURCE_ID"), "prompt-v1")
            page.evaluate("saveCurrentLook()")
            saved_versions = page.evaluate("JSON.parse(localStorage.getItem('pe_looks'))")
            self.assertEqual(len(saved_versions), 3)
            self.assertEqual(saved_versions[0]["versionGroupId"], "prompt-v1")
            self.assertEqual(saved_versions[0]["version"], 3)

            page.evaluate("switchMainTab('library')")
            page.evaluate("minimizeOutput()")
            library.get_by_role("tab", name="History").click()
            self.assertEqual(library.locator("#libraryHistoryList .library-item-card").count(), 1)
            browser.close()

    def test_reference_library_stores_valid_images_locally(self):
        import base64
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page(viewport={"width": 1280, "height": 900})
            page.goto(self.base_url, wait_until="networkidle")
            page.evaluate("switchMainTab('library')")
            page.locator("#tab-library").get_by_role("tab", name="Reference Library").click()
            png = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+nmN8AAAAASUVORK5CYII=")
            page.locator("#libraryReferenceUpload").set_input_files({
                "name": "reference.png",
                "mimeType": "image/png",
                "buffer": png,
            })
            page.wait_for_selector("#libraryReferenceList .library-reference-card")
            self.assertEqual(page.locator("#libraryReferenceList .library-reference-card").count(), 1)
            browser.close()

    def test_settings_persist_workspace_and_prompt_preferences(self):
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page(viewport={"width": 1440, "height": 900})
            page.goto(self.base_url, wait_until="networkidle")
            page.evaluate("switchMainTab('settings')")
            settings = page.locator("#tab-settings")
            self.assertTrue(settings.is_visible())

            settings.locator("[data-settings-view='workspace']").click()
            settings.locator("#settingDefaultMode").select_option("advanced")
            settings.locator("#settingDefaultWorkspace").select_option("home")

            settings.locator("[data-settings-view='prompt']").click()
            settings.locator("#settingTargetModel").select_option("openai/gpt-image")
            settings.locator("#settingDetail").select_option("detailed")
            settings.locator("[data-settings-view='appearance']").click()
            settings.locator("#settingReducedMotion").check()
            settings.locator("#settingsSaveBtn").click()
            self.assertIsNone(page.locator("body").get_attribute("data-view-mode"))
            self.assertEqual(page.locator("body").get_attribute("data-reduced-motion"), "true")

            page.reload(wait_until="networkidle")
            self.assertIsNone(page.locator("body").get_attribute("data-view-mode"))
            page.evaluate("switchMainTab('scratchpad')")
            lab = page.locator("#tab-scratchpad")
            self.assertEqual(lab.get_attribute("data-mode"), "advanced")
            self.assertEqual(lab.locator("#vlModel").input_value(), "openai/gpt-image")
            browser.close()

    def test_keyboard_navigation_reaches_visible_home_controls(self):
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page(viewport={"width": 1280, "height": 800})
            page.goto(self.base_url, wait_until="networkidle")
            page.keyboard.press("Tab")
            focused = page.evaluate("""() => {
                const element = document.activeElement;
                const rect = element.getBoundingClientRect();
                return {
                    tag: element.tagName,
                    text: (element.innerText || element.getAttribute('aria-label') || '').trim(),
                    visible: !!(rect.width && rect.height) &&
                        getComputedStyle(element).visibility !== 'hidden'
                };
            }""")
            self.assertNotEqual(focused["tag"], "BODY", "Tab should move focus to an interactive element")
            self.assertTrue(focused["visible"], f"Keyboard focus is not visible: {focused}")
            focus_style = page.evaluate("""() => {
                const style = getComputedStyle(document.activeElement);
                return {outlineStyle: style.outlineStyle, outlineWidth: style.outlineWidth};
            }""")
            self.assertEqual(focus_style["outlineStyle"], "solid")
            self.assertEqual(focus_style["outlineWidth"], "2px")
            browser.close()

    def test_home_dom_content_loaded_within_smoke_budget(self):
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page(viewport={"width": 1280, "height": 800})
            page.goto(self.base_url, wait_until="networkidle")
            elapsed_ms = page.evaluate("""() => {
                const navigation = performance.getEntriesByType('navigation')[0];
                return navigation ? navigation.domContentLoadedEventEnd : 0;
            }""")
            self.assertGreater(elapsed_ms, 0, "Navigation timing should be available")
            self.assertLess(
                elapsed_ms, 5000,
                f"Home DOMContentLoaded exceeded the 5-second smoke budget: {elapsed_ms:.0f}ms",
            )
            browser.close()


    def test_keyboard_navigation_reaches_primary_home_action(self):
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page(viewport={"width": 1280, "height": 800})
            page.goto(self.base_url, wait_until="networkidle")
            target = page.locator("#tab-home").get_by_role("button", name="Visual Lab")
            target.focus()
            self.assertTrue(target.evaluate("(element) => element === document.activeElement"))
            page.keyboard.press("Enter")
            self.assertTrue(page.locator("#tab-scratchpad").is_visible())
            browser.close()



    def test_studio_detail_levels_and_advanced_directives_are_independent(self):
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page(viewport={"width": 1280, "height": 900})
            page_errors = []
            page.on("pageerror", lambda error: page_errors.append(str(error)))
            page.goto(self.base_url, wait_until="networkidle")
            page.evaluate("switchMainTab('studio')")
            studio = page.locator("#tab-studio")

            for level in ("fast", "balanced", "detailed"):
                selected = studio.locator(f"#det-{level}")
                selected.click()
                self.assertTrue(selected.evaluate(
                    "(el) => el.classList.contains('active') && el.getAttribute('aria-pressed') === 'true'"
                ), f"{level} detail level should be visibly and accessibly selected")
                for other in {"fast", "balanced", "detailed"} - {level}:
                    self.assertEqual(studio.locator(f"#det-{other}").get_attribute("aria-pressed"), "false")

            studio.locator("#studioModeAdvanced").click()
            accordion = studio.locator("#advToggleBtn")
            self.assertEqual(accordion.get_attribute("aria-expanded"), "true")
            self.assertTrue(studio.locator("#advancedControlsWrapper").is_visible())
            accordion.click()
            self.assertEqual(accordion.get_attribute("aria-expanded"), "false")
            self.assertFalse(studio.locator("#advancedControlsWrapper").is_visible())
            accordion.click()
            self.assertEqual(accordion.get_attribute("aria-expanded"), "true")
            self.assertTrue(studio.locator("#advancedControlsWrapper").is_visible())
            for field_id in ("outfitOverride", "subjectText", "hairText", "poseText", "studioAdditional"):
                self.assertEqual(studio.locator(f"#{field_id}").count(), 1, field_id)
            studio.locator("#studioAdditional").fill("Preserve the requested cinematic mood.")
            self.assertEqual(studio.locator("#studioAdditional").input_value(),
                             "Preserve the requested cinematic mood.")
            accordion.click()
            self.assertEqual(accordion.get_attribute("aria-expanded"), "false")
            self.assertEqual(page_errors, [], f"Studio interaction JavaScript errors: {page_errors}")
            browser.close()

    def test_studio_reference_slots_remain_separate_and_accessible(self):
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page(viewport={"width": 1280, "height": 900})
            page.goto(self.base_url, wait_until="networkidle")
            page.evaluate("switchMainTab('studio')")
            studio = page.locator("#tab-studio")
            look_box = studio.locator("#dropLook")
            outfit_box = studio.locator("#dropOutfit")
            self.assertEqual(look_box.get_attribute("aria-label"), "Upload Look reference image")
            self.assertEqual(outfit_box.get_attribute("aria-label"), "Upload Outfit reference image")
            self.assertEqual(look_box.locator("input[type='file']").get_attribute("id"), "fileLook")
            self.assertEqual(outfit_box.locator("input[type='file']").get_attribute("id"), "fileOutfit")
            self.assertEqual(studio.locator("#studioAnalysisPanel").get_attribute("aria-live"), "polite")
            browser.close()

    def test_workspaces_fit_mobile_and_tablet_viewports(self):
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page(viewport={"width": 390, "height": 844}, device_scale_factor=1)
            page.goto(self.base_url, wait_until="networkidle")
            for workspace in ("studio", "scratchpad"):
                page.evaluate(f"switchMainTab('{workspace}')")
                panel = page.locator("#tab-studio" if workspace == "studio" else "#tab-scratchpad")
                self.assertTrue(panel.is_visible())
                for width in (320, 360, 390, 768, 1024):
                    page.set_viewport_size({"width": width, "height": 900})
                    page.wait_for_timeout(80)
                    dimensions = page.evaluate("""() => ({
                        width: window.innerWidth,
                        scrollWidth: document.documentElement.scrollWidth
                    })""")
                    self.assertLessEqual(
                        dimensions["scrollWidth"], dimensions["width"] + 1,
                        f"{workspace} horizontal overflow at {width}px: {dimensions}",
                    )
            browser.close()

    def test_studio_upload_preview_validation_and_slot_isolation(self):
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page(viewport={"width": 1280, "height": 900})
            page.goto(self.base_url, wait_until="networkidle")
            page.evaluate("switchMainTab('studio')")
            studio = page.locator("#tab-studio")
            look_input = studio.locator("#fileLook")
            outfit_input = studio.locator("#fileOutfit")

            look_input.set_input_files({
                "name": "unsupported.gif",
                "mimeType": "image/gif",
                "buffer": b"GIF89a",
            })
            self.assertEqual(look_input.input_value(), "")
            self.assertFalse(studio.locator("#prevLook").is_visible())
            self.assertFalse(studio.locator("#prevOutfit").is_visible())

            # A tiny valid PNG exercises the browser preview path without contacting an AI provider.
            look_input.set_input_files({
                "name": "look.png",
                "mimeType": "image/png",
                "buffer": bytes.fromhex(
                    "89504e470d0a1a0a0000000d494844520000000100000001"
                    "08060000001f15c4890000000b49444154789c636000020000"
                    "050001a5f645400000000049454e44ae426082"
                ),
            })
            self.assertTrue(studio.locator("#prevLook").is_visible())
            self.assertTrue(studio.locator("#prevLook").evaluate(
                "(image) => image.complete && image.naturalWidth === 1"
            ))
            self.assertFalse(studio.locator("#prevOutfit").is_visible())
            studio.locator("#clearLook").click()
            self.assertFalse(studio.locator("#prevLook").is_visible())
            self.assertEqual(look_input.input_value(), "")
            self.assertFalse(studio.locator("#prevOutfit").is_visible())
            browser.close()

    def test_vision_lab_profile_round_trip_preserves_mode_and_brief(self):
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page(viewport={"width": 1280, "height": 900})
            page.goto(self.base_url, wait_until="networkidle")
            page.evaluate("switchMainTab('scratchpad')")
            lab = page.locator("#tab-scratchpad")
            lab.locator(".vl-mode[data-mode='advanced']").click()
            lab.locator("textarea[data-vl-module='appearance_identity']").fill("A poised editorial subject")
            lab.locator("[data-vl-extra='appearance_identity']").fill("Natural skin texture; preserve facial detail")
            lab.locator("#vlInstructions").fill("Keep the requested atmosphere intact.")
            lab.locator("#vlProfileName").fill("QA Editorial Profile")
            lab.locator("#vlSaveProfileBtn").click()
            self.assertEqual(lab.locator("#vlProfileSelect option").count(), 2)

            page.once("dialog", lambda dialog: dialog.accept())
            lab.locator("#vlClearBtn").click()
            self.assertEqual(lab.locator("textarea[data-vl-module='appearance_identity']").input_value(), "")
            lab.locator("#vlProfileSelect").select_option(label="QA Editorial Profile")
            lab.locator("#vlLoadProfileBtn").click()
            self.assertEqual(lab.get_attribute("data-mode"), "advanced")
            self.assertEqual(
                lab.locator("textarea[data-vl-module='appearance_identity']").input_value(),
                "A poised editorial subject",
            )
            self.assertEqual(
                lab.locator("[data-vl-extra='appearance_identity']").input_value(),
                "Natural skin texture; preserve facial detail",
            )
            self.assertEqual(
                lab.locator("#vlInstructions").input_value(),
                "Keep the requested atmosphere intact.",
            )
            page.once("dialog", lambda dialog: dialog.accept())
            lab.locator("#vlDeleteProfileBtn").click()
            self.assertEqual(lab.locator("#vlProfileSelect option").count(), 1)
            browser.close()


    def test_vision_lab_load_profile_requires_an_explicit_selection(self):
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page(viewport={"width": 1280, "height": 900})
            page.goto(self.base_url, wait_until="networkidle")
            page.evaluate("switchMainTab('scratchpad')")
            lab = page.locator("#tab-scratchpad")
            description = lab.locator("textarea[data-vl-module='appearance_identity']")
            description.fill("Saved profile description")
            lab.locator("#vlProfileName").fill("First Profile")
            lab.locator("#vlSaveProfileBtn").click()

            profile_select = lab.locator("#vlProfileSelect")
            self.assertEqual(profile_select.input_value(), "")
            description.fill("Unsaved edits must remain untouched")
            lab.locator("#vlLoadProfileBtn").click()

            self.assertEqual(description.input_value(), "Unsaved edits must remain untouched")
            self.assertEqual(profile_select.input_value(), "")
            self.assertIn("Choose a saved profile first", page.locator("#toast").inner_text())
            browser.close()


    def test_master_and_raw_outputs_remain_isolated_across_formats(self):
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page(viewport={"width": 1280, "height": 900})
            page.goto(self.base_url, wait_until="networkidle")

            result = page.evaluate("""() => {
                setSkeleton("COMPOSITION: Master composition\\n\\nOUTFIT: Master outfit");
                rawRaw = "COMPOSITION: RAW composition\\n\\nOUTFIT: RAW outfit";
                rawSections = parseLabeled(rawRaw);
                activeOutputType = "full";
                configureTabVisibility();
                currentFormat = "prompt";
                const masterPrompt = getFormattedText();
                const masterTabVisibleAfterMasterSelection = getComputedStyle(document.getElementById("fmt-prompt")).display !== "none";
                const rawTabHiddenAfterMasterSelection = getComputedStyle(document.getElementById("fmt-raw")).display === "none";
                setFormat("natural");
                const naturalMaster = getFormattedText();

                activeOutputType = "raw";
                configureTabVisibility();
                currentFormat = "raw";
                const rawPrompt = getFormattedText();
                const masterTabHiddenAfterRawSelection = getComputedStyle(document.getElementById("fmt-prompt")).display === "none";
                const rawTabVisibleAfterRawSelection = getComputedStyle(document.getElementById("fmt-raw")).display !== "none";

                return {
                    masterPrompt, naturalMaster, rawPrompt,
                    masterTabVisibleAfterMasterSelection,
                    rawTabHiddenAfterMasterSelection,
                    masterTabHiddenAfterRawSelection,
                    rawTabVisibleAfterRawSelection,
                    rawContainsMaster: rawPrompt.includes("Master"),
                    masterContainsRaw: masterPrompt.includes("RAW")
                };
            }""")

            self.assertIn("Master composition", result["masterPrompt"])
            self.assertIn("Master outfit", result["masterPrompt"])
            self.assertIn("RAW composition", result["rawPrompt"])
            self.assertIn("RAW outfit", result["rawPrompt"])
            self.assertNotIn("RAW", result["masterPrompt"])
            self.assertNotIn("Master", result["rawPrompt"])
            self.assertTrue(result["masterTabVisibleAfterMasterSelection"])
            self.assertTrue(result["rawTabHiddenAfterMasterSelection"])
            self.assertTrue(result["masterTabHiddenAfterRawSelection"])
            self.assertTrue(result["rawTabVisibleAfterRawSelection"])
            self.assertFalse(result["rawContainsMaster"])
            self.assertFalse(result["masterContainsRaw"])
            self.assertIn("Master composition", result["naturalMaster"])
            browser.close()


    def test_master_and_raw_prompt_edit_and_copy_workflows(self):
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page(viewport={"width": 1280, "height": 900})
            page.goto(self.base_url, wait_until="networkidle")

            result = page.evaluate("""() => {
                const copied = [];
                copyToClipboard = (value, message) => copied.push({ value, message });
                setSkeleton("COMPOSITION: Original master composition\\n\\nOUTFIT: Original master outfit");
                activeOutputType = "full";
                configureTabVisibility();
                currentFormat = "prompt";
                renderFormat();
                let editableCard = document.querySelector("#sectionView .sk-body[contenteditable='true']");
                const masterEditable = !!editableCard;
                if (editableCard) {
                    editableCard.textContent = "Edited master composition";
                    editableCard.dispatchEvent(new InputEvent("input", { bubbles: true, inputType: "insertText", data: "!" }));
                }
                const editedMaster = getFormattedText();
                copyFullPrompt();

                rawRaw = "COMPOSITION: Original RAW composition\\n\\nOUTFIT: Original RAW outfit";
                rawSections = parseLabeled(rawRaw);
                activeOutputType = "raw";
                configureTabVisibility();
                currentFormat = "raw";
                renderFormat();
                editableCard = document.querySelector("#sectionView .sk-body[contenteditable='true']");
                const rawEditable = !!editableCard;
                if (editableCard) {
                    editableCard.textContent = "Edited RAW composition";
                    editableCard.dispatchEvent(new InputEvent("input", { bubbles: true, inputType: "insertText", data: "!" }));
                }
                const editedRaw = getFormattedText();
                copyFullPrompt();

                minimizeOutput();
                return {
                    masterEditable, rawEditable, editedMaster, editedRaw, copied,
                    masterStayedSeparate: !editedMaster.includes("RAW"),
                    rawStayedSeparate: !editedRaw.includes("master"),
                    copyMatchesEditedMaster: copied[0]?.value === editedMaster,
                    copyMatchesEditedRaw: copied[1]?.value === editedRaw
                };
            }""")
            dock = page.locator("#minimizedDock")
            self.assertTrue(dock.is_visible())
            self.assertEqual(dock.get_attribute("role"), "button")
            dock.focus()
            page.keyboard.press("Enter")
            self.assertFalse(dock.is_visible())
            self.assertIn("expanded", page.locator("#outputCard").get_attribute("class"))
            page.wait_for_function("""() => {
                const card = document.getElementById("outputCard");
                return card && card.getAttribute("aria-hidden") === "false" &&
                    card.getBoundingClientRect().top < window.innerHeight;
            }""")
            output_card = page.locator("#outputCard")
            self.assertTrue(output_card.is_visible())
            self.assertEqual(output_card.get_attribute("role"), "dialog")
            self.assertEqual(output_card.get_attribute("aria-modal"), "true")
            self.assertEqual(output_card.get_attribute("aria-labelledby"), "outputHeadingTitle")
            self.assertEqual(output_card.locator("#outputHeadingTitle").inner_text(), "RAW Prompt")
            self.assertEqual(output_card.get_attribute("aria-hidden"), "false")
            minimize = page.get_by_role("button", name="Minimize prompt output")
            self.assertEqual(minimize.count(), 1)
            self.assertTrue(minimize.evaluate("(el) => document.activeElement === el"))
            minimize.focus()
            page.keyboard.press("Tab")
            self.assertTrue(page.locator("#outputCard .sheet-icon-btn").first.evaluate("(el) => document.activeElement === el"))
            page.keyboard.press("Escape")
            self.assertTrue(dock.is_visible())
            self.assertEqual(output_card.get_attribute("aria-hidden"), "true")
            dock.focus()
            page.keyboard.press("Enter")
            self.assertEqual(output_card.get_attribute("aria-hidden"), "false")
            page.keyboard.press("Escape")
            self.assertTrue(dock.is_visible())

            self.assertTrue(result["masterEditable"])
            self.assertTrue(result["rawEditable"])
            self.assertIn("Edited master composition", result["editedMaster"])
            self.assertIn("Edited RAW composition", result["editedRaw"])
            self.assertTrue(result["masterStayedSeparate"])
            self.assertTrue(result["rawStayedSeparate"])
            self.assertTrue(result["copyMatchesEditedMaster"])
            self.assertTrue(result["copyMatchesEditedRaw"])
            browser.close()

    def test_vision_lab_prompt_edit_validate_and_copy_workflow(self):
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page(viewport={"width": 1280, "height": 900})
            page.add_init_script("""
                Object.defineProperty(navigator, 'clipboard', {
                    configurable: true,
                    value: { writeText: async (value) => { window.__copiedPrompt = value; } }
                });
            """)
            page.goto(self.base_url, wait_until="networkidle")
            page.evaluate("switchMainTab('scratchpad')")
            lab = page.locator("#tab-scratchpad")
            prompt = lab.locator("#vlPromptOutput")

            page.evaluate("""() => {
                const output = document.getElementById('vlOutputCard');
                output.hidden = false;
                const field = document.getElementById('vlPromptOutput');
                field.value = 'Original Visual Lab prompt';
                field.readOnly = true;
            }""")
            edit = lab.locator(".vl-output-actions button[aria-controls='vlPromptOutput']")
            self.assertEqual(edit.inner_text(), "Edit")
            edit.click()
            self.assertFalse(prompt.is_disabled())
            self.assertFalse(prompt.evaluate("(field) => field.readOnly"))
            prompt.fill("Edited editorial portrait with natural skin texture and soft studio light.")

            lab.locator("#vlCopyBtn").click()
            page.wait_for_function("window.__copiedPrompt !== undefined")
            copied = page.evaluate("window.__copiedPrompt")
            self.assertEqual(copied, prompt.input_value())

            lab.locator("#vlValidateBtn").click()
            page.wait_for_function(
                "() => document.getElementById('vlValidateBtn').textContent === 'Re-validate edits'"
            )
            self.assertTrue(prompt.evaluate("(field) => field.readOnly"))
            self.assertEqual(edit.inner_text(), "Edit")
            self.assertIn("Manual edit validated", lab.locator("#vlOutputMeta").inner_text())
            browser.close()


    def test_vision_lab_generation_request_polling_and_output_workflow(self):
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page(viewport={"width": 1280, "height": 900})
            page_errors = []
            page.on("pageerror", lambda error: page_errors.append(str(error)))
            generate_requests = []
            status_requests = []

            def mock_generate(route):
                generate_requests.append(route.request.post_data_json)
                route.fulfill(status=202, json={
                    "job_id": "a" * 32,
                    "access_token": "qa-access-token",
                })

            def mock_status(route):
                status_requests.append(route.request.headers.get("authorization"))
                route.fulfill(status=200, json={
                    "status": "done",
                    "step": "",
                    "prompt": "A cinematic editorial portrait with natural skin texture and soft directional studio light.",
                    "ai_status": "completed",
                    "quality": {"score": 92, "issues": []},
                    "model_profile": {"display_name": "QA Model"},
                    "processing_status": "completed",
                    "rule_findings": [],
                    "optimization_warnings": [],
                })

            page.route("**/vision-lab/generate", mock_generate)
            page.route("**/status/" + ("a" * 32), mock_status)
            page.goto(self.base_url, wait_until="networkidle")
            page.evaluate("switchMainTab('scratchpad')")
            lab = page.locator("#tab-scratchpad")
            lab.locator("textarea[data-vl-module='appearance_identity']").fill("A poised editorial subject")
            lab.locator("#vlInstructions").fill("Preserve natural skin texture and the requested mood.")
            generate = lab.locator("#vlGenerateBtn")
            generate.click()

            self.assertTrue(generate.is_disabled())
            self.assertTrue(lab.locator("#vlProgress").is_visible())
            self.assertEqual(generate_requests[0]["mode"], "basic")
            self.assertEqual(
                generate_requests[0]["instructions"],
                "Preserve natural skin texture and the requested mood.",
            )
            self.assertEqual(
                generate_requests[0]["selections"]["appearance_identity"]["description"],
                "A poised editorial subject",
            )

            page.wait_for_function(
                "() => document.getElementById('vlOutputCard').hidden === false",
                timeout=10000,
            )
            self.assertEqual(status_requests, ["Bearer qa-access-token"])
            self.assertEqual(
                lab.locator("#vlPromptOutput").input_value(),
                "A cinematic editorial portrait with natural skin texture and soft directional studio light.",
            )
            self.assertTrue(lab.locator("#vlPromptOutput").evaluate("(field) => field.readOnly"))
            self.assertEqual(lab.locator("#vlQualityBadge").inner_text(), "Quality 92/100")
            self.assertIn("QA Model", lab.locator("#vlOutputMeta").inner_text())
            self.assertTrue(generate.is_enabled())
            self.assertFalse(lab.locator("#vlProgress").is_visible())
            self.assertEqual(page_errors, [], f"Visual Lab generation JavaScript errors: {page_errors}")
            browser.close()


    def test_vision_lab_generation_collects_catalog_choices_from_all_seven_modules(self):
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page(viewport={"width": 1280, "height": 900})
            requests = []

            def mock_generate(route):
                requests.append(route.request.post_data_json)
                route.fulfill(status=202, json={
                    "job_id": "v" * 32,
                    "access_token": "seven-module-token",
                })

            def mock_status(route):
                route.fulfill(status=200, json={
                    "status": "done",
                    "prompt": "Seven-module catalog QA prompt.",
                    "ai_status": "completed",
                    "quality": {"score": 95, "issues": []},
                    "model_profile": {"display_name": "QA Model"},
                    "processing_status": "completed",
                    "rule_findings": [],
                    "optimization_warnings": [],
                })

            page.route("**/vision-lab/generate", mock_generate)
            page.route("**/status/" + ("v" * 32), mock_status)
            page.goto(self.base_url, wait_until="networkidle")
            page.evaluate("switchMainTab('scratchpad')")
            lab = page.locator("#tab-scratchpad")

            basic_choices = {
                "presentation": "Feminine",
                "garment_type": "Sambalpuri saree",
                "pose": "Standing",
                "environment": "Indoor",
                "lighting": "Soft natural window light",
                "camera_type": "Professional full-frame camera",
                "aspect_ratio": "1:1",
            }
            for field, value in basic_choices.items():
                lab.locator("[data-vl-choice='" + field + "']").select_option(label=value)

            lab.locator(".vl-mode[data-mode='advanced']").click()
            advanced_choices = {
                "facial_structure": "Soft oval",
                "neckline": "Round",
                "hand_placement": "Hands relaxed by sides",
                "architecture": "Contemporary minimal",
                "color_temperature": "Warm 2700K–3200K",
                "shutter_speed": "1/50s",
            }
            for field, value in advanced_choices.items():
                lab.locator("[data-vl-choice='" + field + "']").select_option(label=value)
            lab.locator(
                "[data-vl-choice='render_detail'][value='Natural skin texture']"
            ).check()

            lab.locator("#vlGenerateBtn").click()
            page.wait_for_function(
                "() => document.getElementById('vlOutputCard').hidden === false",
                timeout=10000,
            )

            self.assertEqual(len(requests), 1)
            payload = requests[0]
            self.assertEqual(payload["mode"], "advanced")
            expected = {
                "appearance_identity": {"presentation": "Feminine", "facial_structure": "Soft oval"},
                "outfit_styling": {"garment_type": "Sambalpuri saree", "neckline": "Round"},
                "poses_expressions": {"pose": "Standing", "hand_placement": "Hands relaxed by sides"},
                "themes_environment": {"environment": "Indoor", "architecture": "Contemporary minimal"},
                "lighting_composition": {"lighting": "Soft natural window light", "color_temperature": "Warm 2700K–3200K"},
                "camera_photography": {"camera_type": "Professional full-frame camera", "shutter_speed": "1/50s"},
                "output_rendering": {"aspect_ratio": "1:1", "render_detail": ["Natural skin texture"]},
            }
            self.assertEqual(set(payload["selections"]), set(expected))
            for module_id, choices in expected.items():
                self.assertEqual(payload["selections"][module_id]["choices"], choices)
            self.assertEqual(
                lab.locator("#vlPromptOutput").input_value(),
                "Seven-module catalog QA prompt.",
            )
            browser.close()


    def test_vision_lab_displays_non_blocking_outfit_pose_guidance(self):
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page(viewport={"width": 1280, "height": 900})

            def mock_generate(route):
                route.fulfill(status=202, json={
                    "job_id": "g" * 32,
                    "access_token": "guidance-token",
                })

            def mock_status(route):
                route.fulfill(status=200, json={
                    "status": "done",
                    "prompt": "A poised portrait with a naturally draped saree in motion.",
                    "ai_status": "completed",
                    "quality": {"score": 94, "issues": []},
                    "model_profile": {"display_name": "QA Model"},
                    "processing_status": "completed",
                    "rule_findings": [{
                        "code": "OUTFIT_POSE_GUIDANCE",
                        "severity": "info",
                        "message": "Styling suggestion: for a moving saree pose, consider specifying pleat stability, pallu direction, and natural fabric movement.",
                    }],
                    "optimization_warnings": [],
                })

            page.route("**/vision-lab/generate", mock_generate)
            page.route("**/status/" + ("g" * 32), mock_status)
            page.goto(self.base_url, wait_until="networkidle")
            page.evaluate("switchMainTab('scratchpad')")
            lab = page.locator("#tab-scratchpad")
            lab.locator("[data-vl-choice='garment_type']").select_option(label="Sambalpuri saree")
            lab.locator("[data-vl-choice='pose']").select_option(label="Walking")
            lab.locator("#vlGenerateBtn").click()
            page.wait_for_function(
                "() => document.getElementById('vlOutputCard').hidden === false",
                timeout=10000,
            )

            notice = lab.locator("#vlReviewNotice")
            self.assertTrue(notice.is_visible())
            self.assertIn("pallu direction", notice.inner_text())
            self.assertTrue(lab.locator("#vlGenerateBtn").is_enabled())
            browser.close()



    def test_vision_lab_all_catalog_fields_collect_in_basic_and_advanced_modes(self):
        catalog_path = Path(__file__).resolve().parents[1] / "static" / "Catalog" / "visual_lab" / "modules.json"
        catalog = json.loads(catalog_path.read_text(encoding="utf-8"))["modules"]
        expected = {}

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page(viewport={"width": 1440, "height": 1000})
            requests = []

            def mock_generate(route):
                requests.append(route.request.post_data_json)
                route.fulfill(status=202, json={
                    "job_id": "c" * 32,
                    "access_token": "catalog-all-fields-token",
                })

            def mock_status(route):
                route.fulfill(status=200, json={
                    "status": "done",
                    "prompt": "Catalog fields received.",
                    "ai_status": "completed",
                    "quality": {"score": 96, "issues": []},
                    "model_profile": {"display_name": "QA Model"},
                    "processing_status": "completed",
                    "rule_findings": [],
                    "optimization_warnings": [],
                })

            page.route("**/vision-lab/generate", mock_generate)
            page.route("**/status/" + ("c" * 32), mock_status)
            page.goto(self.base_url, wait_until="networkidle")
            page.evaluate("switchMainTab('scratchpad')")
            lab = page.locator("#tab-scratchpad")
            lab.locator("[data-vl-choice]").first.wait_for()
            for module_id in catalog:
                description = lab.locator("textarea[data-vl-module='" + module_id + "']")
                extra = lab.locator("[data-vl-extra='" + module_id + "']")
                self.assertTrue(description.get_attribute("aria-label"), module_id + " description needs an accessible name")
                self.assertTrue(extra.get_attribute("aria-label"), module_id + " advanced notes need an accessible name")

            for module_id, definition in catalog.items():
                expected[module_id] = {}
                for field in definition["basic"]:
                    control = lab.locator(
                        "[data-vl-choice='" + field["id"] + "'][data-vl-module='" + module_id + "']"
                    )
                    if field["type"] == "multi":
                        control.first.check()
                        expected[module_id][field["id"]] = [field["options"][0]]
                    else:
                        control.select_option(label=field["options"][0])
                        expected[module_id][field["id"]] = field["options"][0]

            lab.locator(".vl-mode[data-mode='advanced']").click()
            for module_id, definition in catalog.items():
                for field in definition["advanced"]:
                    control = lab.locator(
                        "[data-vl-choice='" + field["id"] + "'][data-vl-module='" + module_id + "']"
                    )
                    if field["type"] == "multi":
                        control.first.check()
                        expected[module_id][field["id"]] = [field["options"][0]]
                    else:
                        control.select_option(label=field["options"][0])
                        expected[module_id][field["id"]] = field["options"][0]

            lab.locator("#vlGenerateBtn").click()
            page.wait_for_function(
                "() => document.getElementById('vlOutputCard').hidden === false",
                timeout=10000,
            )
            self.assertEqual(len(requests), 1)
            self.assertEqual(requests[0]["mode"], "advanced")
            self.assertEqual(set(requests[0]["selections"]), set(catalog))
            for module_id, fields in expected.items():
                with self.subTest(module=module_id):
                    self.assertEqual(
                        requests[0]["selections"][module_id]["choices"],
                        fields,
                    )
            self.assertEqual(lab.locator("#vlPromptOutput").input_value(), "Catalog fields received.")
            browser.close()



    def test_vision_lab_displays_notice_when_ai_omissions_are_restored(self):
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page(viewport={"width": 1280, "height": 900})

            def mock_generate(route):
                route.fulfill(status=202, json={
                    "job_id": "r" * 32,
                    "access_token": "restore-token",
                })

            def mock_status(route):
                route.fulfill(status=200, json={
                    "status": "done",
                    "prompt": (
                        "A cinematic portrait.\n\n"
                        "Selected creative details retained from your brief:\n"
                        "- Outfit & Styling — Garment type: Sambalpuri saree"
                    ),
                    "ai_status": "completed",
                    "quality": {"score": 100, "issues": []},
                    "model_profile": {"display_name": "QA Model"},
                    "processing_status": "needs_review",
                    "rule_findings": [],
                    "optimization_warnings": [
                        "Some selected details or protected instructions were missing from the AI draft and have been restored verbatim. Review the retained-details section."
                    ],
                })

            page.route("**/vision-lab/generate", mock_generate)
            page.route("**/status/" + ("r" * 32), mock_status)
            page.goto(self.base_url, wait_until="networkidle")
            page.evaluate("switchMainTab('scratchpad')")
            lab = page.locator("#tab-scratchpad")
            lab.locator("#vlInstructions").fill("Keep the original outfit unchanged.")
            lab.locator("#vlGenerateBtn").click()
            page.wait_for_function(
                "() => document.getElementById('vlOutputCard').hidden === false",
                timeout=10000,
            )

            notice = lab.locator("#vlReviewNotice")
            self.assertTrue(notice.is_visible())
            self.assertEqual(notice.get_attribute("role"), "status")
            self.assertEqual(notice.get_attribute("aria-live"), "polite")
            self.assertIn("restored verbatim", notice.inner_text())
            self.assertIn("Sambalpuri saree", lab.locator("#vlPromptOutput").input_value())
            browser.close()



    def test_output_and_picker_controls_have_accessible_names(self):
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page(viewport={"width": 1280, "height": 900})
            page.goto(self.base_url, wait_until="networkidle")

            for button in page.locator(".sheet-action-group button").all():
                self.assertTrue(button.get_attribute("aria-label"))
            self.assertEqual(page.locator("#lookNameInput").get_attribute("aria-label"), "Saved look title")
            self.assertEqual(page.locator("#savedSearch").get_attribute("aria-label"), "Search saved looks")

            page.evaluate("""() => {
                const trigger = document.createElement("button");
                trigger.type = "button";
                document.body.appendChild(trigger);
                trigger.focus();
                openPickerModal({id:"labels", label:"Accessible picker", options:["Any", "Option"]});
            }""")
            self.assertEqual(page.locator("#pickerSearchInput").get_attribute("aria-label"), "Filter picker options")
            self.assertEqual(page.locator(".picker-close-btn").get_attribute("aria-label"), "Close picker")
            browser.close()

    def test_output_format_controls_expose_pressed_state(self):
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page(viewport={"width": 1280, "height": 900})
            page.goto(self.base_url, wait_until="networkidle")
            page.evaluate("setSkeleton('COMPOSITION: Editorial portrait')")
            page.evaluate("setFormat('natural')")
            self.assertEqual(page.locator("#fmt-natural").get_attribute("aria-pressed"), "true")
            self.assertEqual(page.locator("#fmt-prompt").get_attribute("aria-pressed"), "false")
            page.evaluate("setFormat('json')")
            self.assertEqual(page.locator("#fmt-json").get_attribute("aria-pressed"), "true")
            self.assertEqual(page.locator("#fmt-natural").get_attribute("aria-pressed"), "false")
            page.evaluate("setFormat('raw')")
            self.assertEqual(page.locator("#fmt-raw").get_attribute("aria-pressed"), "true")
            self.assertEqual(page.locator("#fmt-json").get_attribute("aria-pressed"), "false")
            browser.close()


    def test_picker_dialog_supports_keyboard_selection_and_focus_return(self):
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page(viewport={"width": 1280, "height": 900})
            page.goto(self.base_url, wait_until="networkidle")
            page.evaluate("""() => {
                const trigger = document.createElement("button");
                trigger.type = "button";
                trigger.id = "picker-test-trigger";
                trigger.textContent = "Open test picker";
                document.body.appendChild(trigger);
                trigger.focus();
                openPickerModal({id:"qa_picker", label:"QA picker", options:["Any", "Option A", "Option B"]});
            }""")

            modal = page.locator("#pickerModal")
            dialog = page.get_by_role("dialog", name="QA picker")
            self.assertTrue(dialog.is_visible())
            self.assertEqual(modal.get_attribute("aria-modal"), "true")
            self.assertTrue(page.locator("#pickerSearchInput").evaluate("(el) => document.activeElement === el"))
            page.get_by_role("radio", name="Any").focus()
            page.keyboard.press("ArrowDown")
            self.assertEqual(page.evaluate("selectedSettings.qa_picker"), "Option A")
            self.assertEqual(modal.get_attribute("aria-hidden"), "true")
            self.assertTrue(page.locator("#picker-test-trigger").evaluate("(el) => document.activeElement === el"))

            page.evaluate("openPickerModal({id:'qa_picker', label:'QA picker', options:['Any', 'Option A']})")
            page.keyboard.press("Escape")
            self.assertEqual(page.locator("#pickerModal").get_attribute("aria-hidden"), "true")
            self.assertTrue(page.locator("#picker-test-trigger").evaluate("(el) => document.activeElement === el"))
            browser.close()

    def test_picker_filter_keeps_a_single_radio_tab_stop_and_traps_focus(self):
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page(viewport={"width": 1280, "height": 900})
            page.goto(self.base_url, wait_until="networkidle")
            page.evaluate("""() => {
                const trigger = document.createElement("button");
                trigger.type = "button";
                trigger.id = "picker-filter-trigger";
                document.body.appendChild(trigger);
                trigger.focus();
                openPickerModal({
                    id: "picker_filter",
                    label: "Picker filter QA",
                    options: ["Any", "Option A", "Option B"]
                });
            }""")

            search = page.locator("#pickerSearchInput")
            search.fill("Option B")
            visible_radios = page.locator("#pickerOptionsList [role='radio']:visible")
            self.assertEqual(visible_radios.count(), 1)
            self.assertEqual(visible_radios.first.inner_text(), "Option B")
            self.assertEqual(
                page.locator("#pickerOptionsList [role='radio'][tabindex='0']:visible").count(),
                1,
            )

            search.fill("")
            self.assertEqual(
                page.locator("#pickerOptionsList [role='radio'][tabindex='0']:visible").count(),
                1,
                "Clearing a filter must not leave multiple radio controls in the Tab order",
            )

            radio_tab_stop = page.locator("#pickerOptionsList [role='radio'][tabindex='0']:visible")
            self.assertEqual(radio_tab_stop.count(), 1)
            radio_tab_stop.focus()
            page.keyboard.press("Tab")
            self.assertTrue(page.locator(".picker-close-btn").evaluate(
                "(el) => document.activeElement === el"
            ), "Tab from the radio tab stop should wrap to the close button")
            page.keyboard.press("Shift+Tab")
            self.assertTrue(radio_tab_stop.evaluate(
                "(el) => document.activeElement === el"
            ), "Shift+Tab from the close button should wrap to the radio tab stop")

            page.keyboard.press("Escape")
            self.assertTrue(page.locator("#picker-filter-trigger").evaluate(
                "(el) => document.activeElement === el"
            ))
            browser.close()


    def test_vision_lab_generation_error_restores_controls(self):
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page(viewport={"width": 1280, "height": 900})
            page_errors = []
            page.on("pageerror", lambda error: page_errors.append(str(error)))
            page.route(
                "**/vision-lab/generate",
                lambda route: route.fulfill(
                    status=503,
                    json={"error": "QA provider unavailable"},
                ),
            )
            page.goto(self.base_url, wait_until="networkidle")
            page.evaluate("switchMainTab('scratchpad')")
            lab = page.locator("#tab-scratchpad")
            lab.locator("textarea[data-vl-module='appearance_identity']").fill("A poised editorial subject")
            generate = lab.locator("#vlGenerateBtn")
            generate.click()
            page.wait_for_function(
                "() => document.getElementById('vlGenerateBtn').disabled === false"
            )
            self.assertFalse(lab.locator("#vlProgress").is_visible())
            self.assertTrue(lab.locator("#vlOutputCard").is_hidden())
            self.assertEqual(page_errors, [], f"Visual Lab error handling JavaScript errors: {page_errors}")
            browser.close()


    def test_vision_studio_full_generation_keeps_reference_slots_and_analysis_separate(self):
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page(viewport={"width": 1280, "height": 900})
            page_errors = []
            page.on("pageerror", lambda error: page_errors.append(str(error)))
            submitted = []
            status_headers = []

            tiny_png = (
                b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
                b"\x00\x00\x00\x01\x00\x00\x00\x01"
                b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
                b"\x00\x00\x00\x0bIDAT\x08\xd7c\xf8\xcf\xc0\x00"
                b"\x00\x03\x01\x01\x00\xc9\xfe\x92\xef"
                b"\x00\x00\x00\x00IEND\xaeB`\x82"
            )

            def mock_generate(route):
                submitted.append(route.request.post_data)
                route.fulfill(status=202, json={
                    "job_id": "b" * 32,
                    "access_token": "studio-qa-token",
                })

            def mock_status(route):
                status_headers.append(route.request.headers.get("authorization"))
                route.fulfill(status=200, json={
                    "kind": "generate",
                    "status": "done",
                    "detail": "balanced",
                    "mode": "BOTH",
                    "prompt": "SUBJECT PHYSIQUE: Natural proportions.\nOUTFIT: Ivory silk saree with woven border.\nPOSE AND ACTION: Seated three-quarter pose.",
                    "compact": "",
                    "studio_quality": {"status": "ready", "warnings": [], "suggestions": []},
                    "visual_analysis_status": "ready",
                    "reference_analysis": {
                        "status": "ready",
                        "coverage_score": 100,
                        "score_note": "Coverage is not visual accuracy.",
                        "references": {
                            "look": {"status": "ready", "summary": "Look framing and pose analyzed."},
                            "outfit": {"status": "ready", "summary": "Outfit fabric and construction analyzed."},
                        },
                        "conflicts": [],
                        "notes": [],
                    },
                })

            page.route("**/generate", mock_generate)
            page.route("**/status/" + ("b" * 32), mock_status)
            page.goto(self.base_url, wait_until="networkidle")
            page.evaluate("switchMainTab('studio')")
            studio = page.locator("#tab-studio")
            studio.locator("#fileLook").set_input_files({
                "name": "look.png", "mimeType": "image/png", "buffer": tiny_png,
            })
            studio.locator("#fileOutfit").set_input_files({
                "name": "outfit.png", "mimeType": "image/png", "buffer": tiny_png,
            })
            studio.locator("#studioBrief").fill("Keep the editorial mood natural.")
            studio.locator("#genBtn").click()
            self.assertTrue(studio.locator("#genBtn").is_disabled())
            self.assertTrue(studio.locator("#progressBox").is_visible())

            page.wait_for_function(
                "() => document.getElementById('studioAnalysisStatus').textContent === 'Analysis complete'",
                timeout=12000,
            )
            self.assertEqual(len(submitted), 1)
            self.assertIn('name="image1"', submitted[0])
            self.assertIn('name="image2"', submitted[0])
            self.assertIn('name="output"\r\n\r\nfull', submitted[0])
            self.assertIn("Keep the editorial mood natural.", submitted[0])
            self.assertEqual(status_headers, ["Bearer studio-qa-token"])
            self.assertEqual(studio.locator("#lookAnalysisState").inner_text(), "Ready")
            self.assertEqual(studio.locator("#outfitAnalysisState").inner_text(), "Ready")
            self.assertIn("Look framing and pose", studio.locator("#lookAnalysisSummary").inner_text())
            self.assertIn("Outfit fabric", studio.locator("#outfitAnalysisSummary").inner_text())
            self.assertEqual(studio.locator("#studioCoverageScore").inner_text(), "100%")
            self.assertTrue(studio.locator("#genBtn").is_enabled())
            self.assertFalse(studio.locator("#progressBox").is_visible())
            self.assertEqual(page_errors, [], f"Vision Studio generation JavaScript errors: {page_errors}")
            browser.close()

    def test_vision_studio_generation_server_error_restores_controls(self):
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page(viewport={"width": 1280, "height": 900})
            page_errors = []
            page.on("pageerror", lambda error: page_errors.append(str(error)))
            tiny_png = (
                b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
                b"\x00\x00\x00\x01\x00\x00\x00\x01"
                b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
                b"\x00\x00\x00\x0bIDAT\x08\xd7c\xf8\xcf\xc0\x00"
                b"\x00\x03\x01\x01\x00\xc9\xfe\x92\xef"
                b"\x00\x00\x00\x00IEND\xaeB`\x82"
            )
            page.route(
                "**/generate",
                lambda route: route.fulfill(status=503, json={"error": "QA provider unavailable"}),
            )
            page.goto(self.base_url, wait_until="networkidle")
            page.evaluate("switchMainTab('studio')")
            studio = page.locator("#tab-studio")
            studio.locator("#fileLook").set_input_files({
                "name": "look.png", "mimeType": "image/png", "buffer": tiny_png,
            })
            studio.locator("#genBtn").click()
            page.wait_for_function(
                "() => document.getElementById('genBtn').disabled === false",
                timeout=10000,
            )
            self.assertFalse(studio.locator("#progressBox").is_visible())
            self.assertEqual(page_errors, [], f"Vision Studio error handling JavaScript errors: {page_errors}")
            browser.close()


    def test_vision_studio_raw_generation_excludes_outfit_reference_and_keeps_raw_output_isolated(self):
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page(viewport={"width": 1280, "height": 900})
            page_errors = []
            page.on("pageerror", lambda error: page_errors.append(str(error)))
            submitted = []
            status_headers = []

            tiny_png = bytes.fromhex(
                "89504e470d0a1a0a0000000d494844520000000100000001"
                "08060000001f15c4890000000b49444154789c636000020000"
                "050001a5f645400000000049454e44ae426082"
            )

            def mock_generate(route):
                submitted.append(route.request.post_data)
                route.fulfill(status=202, json={
                    "job_id": "c" * 32,
                    "access_token": "studio-raw-qa-token",
                })

            def mock_status(route):
                status_headers.append(route.request.headers.get("authorization"))
                route.fulfill(status=200, json={
                    "kind": "generate",
                    "status": "done",
                    "detail": "balanced",
                    "prompt": "RAW LOOK: Preserve the reference framing and natural light.",
                    "visual_analysis_status": "ready",
                    "reference_analysis": {
                        "status": "ready",
                        "coverage_score": 100,
                        "score_note": "Look reference analyzed; Outfit intentionally excluded.",
                        "references": {
                            "look": {"status": "ready", "summary": "Look framing retained."},
                            "outfit": {"status": "excluded"},
                        },
                        "conflicts": [],
                        "notes": [],
                    },
                    "studio_quality": {"status": "ready", "warnings": [], "suggestions": []},
                })

            page.route("**/generate", mock_generate)
            page.route("**/status/" + ("c" * 32), mock_status)
            page.goto(self.base_url, wait_until="networkidle")
            page.evaluate("switchMainTab('studio')")
            studio = page.locator("#tab-studio")
            studio.locator("#fileLook").set_input_files({
                "name": "look.png", "mimeType": "image/png", "buffer": tiny_png,
            })
            studio.locator("#fileOutfit").set_input_files({
                "name": "outfit.png", "mimeType": "image/png", "buffer": tiny_png,
            })
            page.wait_for_function(
                "() => document.getElementById('rawBtn').disabled === false",
                timeout=5000,
            )
            studio.locator("#rawBtn").click()

            page.wait_for_function(
                "() => document.getElementById('outputHeadingTitle').textContent === 'RAW Prompt' && "
                "document.getElementById('progressBox').style.display === 'none'",
                timeout=12000,
            )
            self.assertEqual(len(submitted), 1)
            self.assertIn('name="image1"', submitted[0])
            self.assertNotIn('name="image2"', submitted[0])
            self.assertIn('name="output"\r\n\r\nraw', submitted[0])
            self.assertEqual(status_headers, ["Bearer studio-raw-qa-token"])
            self.assertEqual(studio.locator("#lookAnalysisState").inner_text(), "Ready")
            self.assertEqual(studio.locator("#outfitAnalysisState").inner_text(), "Excluded in RAW")
            self.assertIn("intentionally excludes", studio.locator("#outfitAnalysisSummary").inner_text())
            self.assertTrue(page.locator("#fmt-raw").is_visible())
            self.assertFalse(page.locator("#fmt-prompt").is_visible())
            self.assertIn("RAW LOOK", page.locator("#sectionView").inner_text())
            self.assertNotIn("Master", page.locator("#sectionView").inner_text())
            self.assertTrue(studio.locator("#rawBtn").is_enabled())
            self.assertFalse(studio.locator("#progressBox").is_visible())
            self.assertEqual(page_errors, [], f"Vision Studio RAW generation JavaScript errors: {page_errors}")
            browser.close()


    def test_studio_reference_removal_resets_preview_and_generation_state(self):
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page(viewport={"width": 1280, "height": 900})
            page_errors = []
            page.on("pageerror", lambda error: page_errors.append(str(error)))
            tiny_png = bytes.fromhex(
                "89504e470d0a1a0a0000000d494844520000000100000001"
                "08060000001f15c4890000000b49444154789c636000020000"
                "050001a5f645400000000049454e44ae426082"
            )
            page.goto(self.base_url, wait_until="networkidle")
            page.evaluate("switchMainTab('studio')")
            studio = page.locator("#tab-studio")
            look = {"name": "look.png", "mimeType": "image/png", "buffer": tiny_png}
            outfit = {"name": "outfit.png", "mimeType": "image/png", "buffer": tiny_png}
            studio.locator("#fileLook").set_input_files(look)
            studio.locator("#fileOutfit").set_input_files(outfit)
            page.wait_for_function(
                "() => !document.getElementById('genBtn').disabled && !document.getElementById('rawBtn').disabled"
            )
            self.assertTrue(studio.locator("#prevLook").is_visible())
            self.assertTrue(studio.locator("#prevOutfit").is_visible())

            studio.locator("#clearLook").click(force=True)
            self.assertEqual(studio.locator("#fileLook").input_value(), "")
            self.assertFalse(studio.locator("#prevLook").is_visible())
            self.assertTrue(studio.locator("#prevOutfit").is_visible())
            self.assertTrue(studio.locator("#genBtn").is_enabled())
            self.assertFalse(studio.locator("#rawBtn").is_enabled())

            studio.locator("#clearOutfit").click(force=True)
            self.assertEqual(studio.locator("#fileOutfit").input_value(), "")
            self.assertFalse(studio.locator("#prevOutfit").is_visible())
            self.assertFalse(studio.locator("#genBtn").is_enabled())
            self.assertFalse(studio.locator("#rawBtn").is_enabled())
            self.assertEqual(page_errors, [], f"Reference removal JavaScript errors: {page_errors}")
            browser.close()

    def test_studio_failed_analysis_can_retry_and_complete(self):
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page(viewport={"width": 1280, "height": 900})
            page_errors = []
            page.on("pageerror", lambda error: page_errors.append(str(error)))
            requests = []
            status_calls = {"first": 0, "retry": 0}
            tiny_png = bytes.fromhex(
                "89504e470d0a1a0a0000000d494844520000000100000001"
                "08060000001f15c4890000000b49444154789c636000020000"
                "050001a5f645400000000049454e44ae426082"
            )

            def mock_generate(route):
                requests.append(route.request)
                job_id = ("e" if len(requests) == 1 else "f") * 32
                route.fulfill(status=202, json={"job_id": job_id, "access_token": "retry-qa-token"})

            def mock_status(route):
                if "e" * 32 in route.request.url:
                    status_calls["first"] += 1
                    route.fulfill(status=200, json={
                        "kind": "generate", "status": "error", "error": "Temporary analysis failure",
                    })
                else:
                    status_calls["retry"] += 1
                    route.fulfill(status=200, json={
                        "kind": "generate", "status": "done", "detail": "balanced",
                        "prompt": "SUBJECT PHYSIQUE: Natural proportions.\nOUTFIT: Blue cotton dress.",
                        "visual_analysis_status": "ready",
                        "reference_analysis": {
                            "status": "ready", "coverage_score": 100,
                            "references": {
                                "look": {"status": "ready", "summary": "Look analyzed after retry."},
                                "outfit": {"status": "ready", "summary": "Outfit analyzed after retry."},
                            },
                            "conflicts": [], "notes": [],
                        },
                        "studio_quality": {"status": "ready", "warnings": [], "suggestions": []},
                    })

            page.route("**/generate", mock_generate)
            page.route("**/status/**", mock_status)
            page.goto(self.base_url, wait_until="networkidle")
            page.evaluate("switchMainTab('studio')")
            studio = page.locator("#tab-studio")
            studio.locator("#fileLook").set_input_files({
                "name": "look.png", "mimeType": "image/png", "buffer": tiny_png,
            })
            studio.locator("#fileOutfit").set_input_files({
                "name": "outfit.png", "mimeType": "image/png", "buffer": tiny_png,
            })
            studio.locator("#genBtn").click()
            page.wait_for_function(
                "() => document.getElementById('studioRetryAnalysis').hidden === false",
                timeout=10000,
            )
            self.assertIn("Analysis failed", studio.locator("#studioAnalysisStatus").inner_text())
            self.assertTrue(studio.locator("#genBtn").is_enabled())
            studio.locator("#studioRetryAnalysis").click()
            page.wait_for_function(
                "() => document.getElementById('studioAnalysisStatus').textContent === 'Analysis complete'",
                timeout=12000,
            )
            self.assertEqual(len(requests), 2)
            self.assertGreaterEqual(status_calls["first"], 1)
            self.assertGreaterEqual(status_calls["retry"], 1)
            self.assertEqual(studio.locator("#lookAnalysisState").inner_text(), "Ready")
            self.assertEqual(studio.locator("#outfitAnalysisState").inner_text(), "Ready")
            self.assertFalse(studio.locator("#progressBox").is_visible())
            self.assertEqual(page_errors, [], f"Retry workflow JavaScript errors: {page_errors}")
            browser.close()

    def test_studio_optimize_workflow_returns_compact_output_and_restores_controls(self):
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page(viewport={"width": 1280, "height": 900})
            page_errors = []
            page.on("pageerror", lambda error: page_errors.append(str(error)))
            tiny_png = bytes.fromhex(
                "89504e470d0a1a0a0000000d494844520000000100000001"
                "08060000001f15c4890000000b49444154789c636000020000"
                "050001a5f645400000000049454e44ae426082"
            )
            optimize_payloads = []

            def mock_generate(route):
                route.fulfill(status=202, json={
                    "job_id": "g" * 32, "access_token": "optimize-qa-token",
                })

            def mock_optimize(route):
                optimize_payloads.append(route.request.post_data_json)
                route.fulfill(status=202, json={
                    "job_id": "h" * 32, "access_token": "optimize-qa-token",
                })

            def mock_status(route):
                if "g" * 32 in route.request.url:
                    route.fulfill(status=200, json={
                        "kind": "generate", "status": "done", "detail": "balanced",
                        "prompt": "SUBJECT PHYSIQUE: Natural proportions.\nOUTFIT: Detailed blue silk saree with woven gold border.",
                        "visual_analysis_status": "ready",
                        "reference_analysis": {"status": "ready", "references": {
                            "look": {"status": "ready"}, "outfit": {"status": "not_used"},
                        }},
                        "studio_quality": {"status": "ready", "warnings": [], "suggestions": []},
                    })
                else:
                    route.fulfill(status=200, json={
                        "kind": "optimize", "status": "done",
                        "prompt": "SUBJECT PHYSIQUE: Natural proportions.\nOUTFIT: Blue silk saree.",
                        "optimizer_model": "qa/compact-model", "warnings": [], "over_budget": False,
                    })

            page.route("**/generate", mock_generate)
            page.route("**/optimize", mock_optimize)
            page.route("**/status/**", mock_status)
            page.goto(self.base_url, wait_until="networkidle")
            page.evaluate("switchMainTab('studio')")
            studio = page.locator("#tab-studio")
            studio.locator("#fileLook").set_input_files({
                "name": "look.png", "mimeType": "image/png", "buffer": tiny_png,
            })
            studio.locator("#genBtn").click()
            page.wait_for_function(
                "() => document.getElementById('outputHeadingTitle').textContent === 'Master Prompt'",
                timeout=10000,
            )
            page.locator("#fmt-optimized").click()
            page.locator("#optimizeBtn").click()
            page.wait_for_function(
                "() => document.getElementById('optimizeBtn').disabled === false && "
                "document.getElementById('sectionView').textContent.includes('Blue silk saree.')",
                timeout=12000,
            )
            self.assertEqual(len(optimize_payloads), 1)
            self.assertIn("Detailed blue silk saree", optimize_payloads[0]["skeleton"])
            self.assertIn("compact-model", page.locator("#statusText").inner_text())
            self.assertTrue(page.locator("#optimizeBtn").is_enabled())
            self.assertFalse(studio.locator("#progressBox").is_visible())
            self.assertEqual(page_errors, [], f"Optimize workflow JavaScript errors: {page_errors}")
            browser.close()



    def test_studio_raw_generation_failure_restores_controls_and_reports_error(self):
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page(viewport={"width": 1280, "height": 900})
            page_errors = []
            page.on("pageerror", lambda error: page_errors.append(str(error)))
            tiny_png = bytes.fromhex(
                "89504e470d0a1a0a0000000d494844520000000100000001"
                "08060000001f15c4890000000b49444154789c636000020000"
                "050001a5f645400000000049454e44ae426082"
            )
            requests = []

            def mock_generate(route):
                requests.append(route.request)
                route.fulfill(status=202, json={
                    "job_id": "r" * 32, "access_token": "raw-failure-token",
                })

            def mock_status(route):
                route.fulfill(status=200, json={
                    "kind": "generate", "status": "error",
                    "error": "Temporary RAW synthesis failure",
                })

            page.route("**/generate", mock_generate)
            page.route("**/status/**", mock_status)
            page.goto(self.base_url, wait_until="networkidle")
            page.evaluate("switchMainTab('studio')")
            studio = page.locator("#tab-studio")
            studio.locator("#fileLook").set_input_files({
                "name": "look.png", "mimeType": "image/png", "buffer": tiny_png,
            })
            studio.locator("#rawBtn").click()
            page.wait_for_function(
                "() => document.getElementById('progressBox').style.display === 'none' && "
                "document.getElementById('rawBtn').disabled === false",
                timeout=10000,
            )
            self.assertEqual(len(requests), 1)
            self.assertIn("Temporary RAW synthesis failure", page.locator("#statusText").inner_text())
            self.assertTrue(studio.locator("#rawBtn").is_enabled())
            self.assertFalse(studio.locator("#progressBox").is_visible())
            self.assertEqual(page_errors, [], f"RAW failure JavaScript errors: {page_errors}")
            browser.close()

    def test_studio_optimize_failure_can_retry_successfully(self):
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page(viewport={"width": 1280, "height": 900})
            page_errors = []
            page.on("pageerror", lambda error: page_errors.append(str(error)))
            tiny_png = bytes.fromhex(
                "89504e470d0a1a0a0000000d494844520000000100000001"
                "08060000001f15c4890000000b49444154789c636000020000"
                "050001a5f645400000000049454e44ae426082"
            )
            optimize_calls = {"count": 0}

            def mock_generate(route):
                route.fulfill(status=202, json={
                    "job_id": "s" * 32, "access_token": "optimize-retry-token",
                })

            def mock_optimize(route):
                optimize_calls["count"] += 1
                if optimize_calls["count"] == 1:
                    route.fulfill(status=503, json={"error": "Temporary optimizer outage"})
                else:
                    route.fulfill(status=202, json={
                        "job_id": "t" * 32, "access_token": "optimize-retry-token",
                    })

            def mock_status(route):
                if "s" * 32 in route.request.url:
                    route.fulfill(status=200, json={
                        "kind": "generate", "status": "done", "detail": "balanced",
                        "prompt": "SUBJECT PHYSIQUE: Natural proportions.\nOUTFIT: Detailed blue silk saree.",
                        "visual_analysis_status": "ready",
                        "reference_analysis": {"status": "ready", "references": {
                            "look": {"status": "ready"}, "outfit": {"status": "not_used"},
                        }},
                        "studio_quality": {"status": "ready", "warnings": [], "suggestions": []},
                    })
                else:
                    route.fulfill(status=200, json={
                        "kind": "optimize", "status": "done",
                        "prompt": "SUBJECT PHYSIQUE: Natural proportions.\nOUTFIT: Compact blue silk saree.",
                        "optimizer_model": "qa/retry-model", "warnings": [], "over_budget": False,
                    })

            page.route("**/generate", mock_generate)
            page.route("**/optimize", mock_optimize)
            page.route("**/status/**", mock_status)
            page.goto(self.base_url, wait_until="networkidle")
            page.evaluate("switchMainTab('studio')")
            studio = page.locator("#tab-studio")
            studio.locator("#fileLook").set_input_files({
                "name": "look.png", "mimeType": "image/png", "buffer": tiny_png,
            })
            studio.locator("#genBtn").click()
            page.wait_for_function(
                "() => document.getElementById('outputHeadingTitle').textContent === 'Master Prompt'",
                timeout=10000,
            )
            page.wait_for_function(
                "() => !busy && currentRaw.length > 0 && "
                "document.getElementById('optimizeBtn').style.display !== 'none'",
                timeout=10000,
            )
            page.evaluate("setFormat('optimized')")
            page.evaluate("document.getElementById('optimizeBtn').click()")
            page.wait_for_function(
                "() => document.getElementById('statusText').textContent === 'Temporary optimizer outage' && !busy",
                timeout=10000,
            )
            self.assertIn("Temporary optimizer outage", page.locator("#statusText").inner_text())
            self.assertEqual(optimize_calls["count"], 1)
            self.assertTrue(page.locator("#optimizeBtn").is_enabled())

            page.evaluate("document.getElementById('optimizeBtn').click()")
            page.wait_for_function(
                "() => document.getElementById('optimizeBtn').disabled === false && "
                "document.getElementById('sectionView').textContent.includes('Compact blue silk saree.')",
                timeout=12000,
            )
            self.assertEqual(optimize_calls["count"], 2)
            self.assertIn("retry-model", page.locator("#statusText").inner_text())
            self.assertFalse(studio.locator("#progressBox").is_visible())
            self.assertEqual(page_errors, [], f"Optimize retry JavaScript errors: {page_errors}")
            browser.close()



    def test_untrusted_prompt_markup_is_rendered_as_text_not_executable_html(self):
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page(viewport={"width": 1280, "height": 900})
            page_errors = []
            page.on("pageerror", lambda error: page_errors.append(str(error)))
            page.goto(self.base_url, wait_until="networkidle")
            page.evaluate("switchMainTab('studio')")
            payload = (
                'OUTFIT: <img src=x onerror="window.__atelierXss=1">'
                '<script>window.__atelierXss=2</script>'
            )
            page.evaluate(
                """(value) => {
                    window.__atelierXss = 0;
                    setSkeleton(value);
                    activeOutputType = "full";
                    expandOutput();
                }""",
                payload,
            )
            section = page.locator("#sectionView")
            self.assertEqual(section.locator("img, script").count(), 0)
            self.assertIn("<img src=x", section.inner_text())
            self.assertEqual(page.evaluate("window.__atelierXss"), 0)

            page.evaluate(
                """(value) => {
                    rawRaw = value;
                    rawSections = parseLabeled(value);
                    activeOutputType = "raw";
                    configureTabVisibility();
                    expandOutput();
                }""",
                payload,
            )
            self.assertEqual(section.locator("img, script").count(), 0)
            self.assertIn("<img src=x", section.inner_text())
            self.assertEqual(page.evaluate("window.__atelierXss"), 0)
            self.assertEqual(page_errors, [], f"Untrusted prompt rendering errors: {page_errors}")
            browser.close()


    def test_library_projects_and_saved_prompts_can_be_renamed(self):
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page(viewport={"width": 1280, "height": 900})
            page.on("dialog", lambda dialog: dialog.accept("Renamed from QA") if dialog.type == "prompt" else dialog.accept())
            page_errors = []
            page.on("pageerror", lambda error: page_errors.append(str(error)))
            page.goto(self.base_url, wait_until="networkidle")
            page.evaluate("""() => localStorage.setItem("pe_looks", JSON.stringify([
                {id:"rename-prompt", name:"Original prompt name", prompt:"A saved prompt to rename", ts:"2026-11-12"}
            ]))""")
            page.reload(wait_until="networkidle")
            page.evaluate("switchMainTab('library')")
            library = page.locator("#tab-library")
            library.get_by_role("tab", name="My Projects").click()
            library.locator("#libraryProjectName").fill("Original project name")
            library.locator("#libraryProjectForm button[type='submit']").click()
            library.get_by_role("button", name="Rename project").click()
            self.assertIn("Renamed from QA", library.locator("#libraryProjectList").inner_text())
            library.get_by_role("tab", name="Prompt Library").click()
            library.get_by_role("button", name="Rename prompt").click()
            self.assertIn("Renamed from QA", library.locator("#libraryPromptList .library-item-title").inner_text())
            saved_projects = page.evaluate("JSON.parse(localStorage.getItem('ape_projects'))")
            saved_prompts = page.evaluate("JSON.parse(localStorage.getItem('pe_looks'))")
            self.assertEqual(saved_projects[0]["name"], "Renamed from QA")
            self.assertEqual(saved_prompts[0]["name"], "Renamed from QA")
            self.assertEqual(page_errors, [], f"Library rename JavaScript errors: {page_errors}")
            browser.close()


    def test_library_project_retention_bulk_delete_and_reference_removal(self):
        import base64
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page(viewport={"width": 1280, "height": 900})
            page.on("dialog", lambda dialog: dialog.accept())
            page_errors = []
            page.on("pageerror", lambda error: page_errors.append(str(error)))
            page.goto(self.base_url, wait_until="networkidle")
            page.evaluate("""() => localStorage.setItem("pe_looks", JSON.stringify([
                {id:"library-keep", name:"Keep this prompt", prompt:"Prompt remains after project deletion", ts:"2026-11-11"},
                {id:"library-delete", name:"Delete this prompt", prompt:"Bulk delete candidate", ts:"2026-11-11"}
            ]))""")
            page.reload(wait_until="networkidle")
            page.evaluate("switchMainTab('library')")
            library = page.locator("#tab-library")

            library.get_by_role("tab", name="My Projects").click()
            library.locator("#libraryProjectName").fill("Temporary project")
            library.locator("#libraryProjectForm button[type='submit']").click()
            library.get_by_role("tab", name="Prompt Library").click()
            library.locator("#libraryPromptList select").first.select_option(
                label="Temporary project"
            )
            library.get_by_role("tab", name="My Projects").click()
            library.get_by_role("button", name="Delete project").click()
            remaining = page.evaluate("JSON.parse(localStorage.getItem('pe_looks'))")
            self.assertEqual(len(remaining), 2)
            self.assertTrue(all(item.get("projectId", "") == "" for item in remaining))

            library.get_by_role("tab", name="Prompt Library").click()
            library.locator("#libraryPromptList input[type='checkbox']").nth(1).check()
            library.locator("#libraryBulkDeleteBtn").click()
            remaining = page.evaluate("JSON.parse(localStorage.getItem('pe_looks'))")
            self.assertEqual([item["id"] for item in remaining], ["library-keep"])

            library.get_by_role("tab", name="Reference Library").click()
            png = base64.b64decode(
                "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+nmN8AAAAASUVORK5CYII="
            )
            library.locator("#libraryReferenceUpload").set_input_files({
                "name": "remove-me.png", "mimeType": "image/png", "buffer": png,
            })
            page.wait_for_selector("#libraryReferenceList .library-reference-card")
            library.locator("#libraryReferenceList input[type='checkbox']").check()
            library.locator("#libraryBulkDeleteReferences").click()
            page.wait_for_function(
                "() => document.querySelectorAll('#libraryReferenceList .library-reference-card').length === 0"
            )
            self.assertIn("deleted", library.locator("#libraryStatus").inner_text().lower())
            self.assertEqual(page_errors, [], f"Library action JavaScript errors: {page_errors}")
            browser.close()


    def test_settings_backup_export_import_and_history_clear(self):
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page(viewport={"width": 1280, "height": 900}, accept_downloads=True)
            page.on("dialog", lambda dialog: dialog.accept())
            page.goto(self.base_url, wait_until="networkidle")
            page.evaluate("""() => {
                localStorage.setItem("pe_history", JSON.stringify([
                    {id:"history-clear", name:"History entry", prompt:"Clear this entry"}
                ]));
                localStorage.setItem("pe_looks", JSON.stringify([
                    {id:"backup-existing", name:"Existing", prompt:"Existing prompt"}
                ]));
            }""")
            page.reload(wait_until="networkidle")
            page.evaluate("switchMainTab('settings')")
            settings = page.locator("#tab-settings")
            settings.locator("[data-settings-view='storage']").click()
            self.assertTrue(settings.locator("[data-settings-panel='storage']").is_visible())

            with page.expect_download() as download_info:
                settings.locator("#settingsExportBtn").click()
            download = download_info.value
            self.assertTrue(download.suggested_filename.startswith("Atelier_PE_Backup_"))
            self.assertTrue(download.suggested_filename.endswith(".json"))

            backup = (
                '{"pe_looks":[{"id":"backup-imported","name":"Imported prompt",'
                '"prompt":"Imported prompt text"}],"pe_history":[],"ape_projects":[]}'
            )
            settings.locator("#settingsImportInput").set_input_files({
                "name": "atelier-backup.json",
                "mimeType": "application/json",
                "buffer": backup.encode("utf-8"),
            })
            page.wait_for_function(
                "() => JSON.parse(localStorage.getItem('pe_looks') || '[]').some(item => item.id === 'backup-imported')"
            )
            imported = page.evaluate("JSON.parse(localStorage.getItem('pe_looks'))")
            self.assertTrue(any(item["id"] == "backup-imported" for item in imported))

            settings.locator("#settingsClearHistoryBtn").click()
            self.assertEqual(page.evaluate("JSON.parse(localStorage.getItem('pe_history'))"), [])
            self.assertIn("cleared", settings.locator("#settingsStatus").inner_text().lower())
            browser.close()


    def test_settings_default_mode_applies_to_vision_studio(self):
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page(viewport={"width": 1280, "height": 900})
            page_errors = []
            page.on("pageerror", lambda error: page_errors.append(str(error)))
            page.goto(self.base_url, wait_until="networkidle")
            page.evaluate("switchMainTab('settings')")
            settings = page.locator("#tab-settings")
            settings.locator("[data-settings-view='workspace']").click()
            settings.locator("#settingDefaultWorkspace").select_option("studio")
            settings.locator("#settingDefaultMode").select_option("advanced")
            settings.locator("#settingsSaveBtn").click()
            studio = page.locator("#tab-studio")
            self.assertTrue(studio.is_visible())
            self.assertEqual(studio.get_attribute("data-mode"), "advanced")
            self.assertTrue(studio.locator("#advancedControlsWrapper").is_visible())
            self.assertEqual(studio.locator("#studioModeAdvanced").get_attribute("aria-pressed"), "true")
            page.reload(wait_until="networkidle")
            studio = page.locator("#tab-studio")
            self.assertTrue(studio.is_visible())
            self.assertEqual(studio.get_attribute("data-mode"), "advanced")
            self.assertTrue(studio.locator("#advancedControlsWrapper").is_visible())
            self.assertEqual(page_errors, [], f"Settings default Studio mode errors: {page_errors}")
            browser.close()


    def test_settings_all_sections_switch_visibility_and_accessible_state(self):
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page(viewport={"width": 1280, "height": 900})
            page_errors = []
            page.on("pageerror", lambda error: page_errors.append(str(error)))
            page.goto(self.base_url, wait_until="networkidle")
            page.evaluate("switchMainTab('settings')")
            settings = page.locator("#tab-settings")

            sections = (
                "profile", "appearance", "workspace", "prompt",
                "ai", "storage", "about",
            )
            for section in sections:
                button = settings.locator(f"[data-settings-view='{section}']")
                panel = settings.locator(f"[data-settings-panel='{section}']")
                button.click()
                self.assertTrue(panel.is_visible(), f"{section} panel should be visible")
                self.assertEqual(button.get_attribute("aria-current"), "page")
                self.assertEqual(
                    settings.locator("[data-settings-view][aria-current='page']").count(),
                    1,
                    "Exactly one Settings section should be marked current",
                )
                for other in set(sections) - {section}:
                    self.assertTrue(
                        settings.locator(f"[data-settings-panel='{other}']").is_hidden(),
                        f"{other} panel should be hidden while {section} is active",
                    )
                    self.assertIsNone(
                        settings.locator(f"[data-settings-view='{other}']").get_attribute("aria-current"),
                        f"{other} navigation item must not be marked current",
                    )

            self.assertEqual(page_errors, [], f"Settings navigation JavaScript errors: {page_errors}")
            browser.close()


    def test_settings_reset_cancel_preserves_local_data(self):
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page(viewport={"width": 1280, "height": 900})
            page.on("dialog", lambda dialog: dialog.dismiss())
            page.goto(self.base_url, wait_until="networkidle")
            page.evaluate("""() => {
                localStorage.setItem("pe_looks", JSON.stringify([
                    {id:"keep-on-cancel", name:"Keep me", prompt:"Do not erase"}
                ]));
                localStorage.setItem("pe_history", JSON.stringify([
                    {id:"history-on-cancel", name:"History", prompt:"Keep history"}
                ]));
            }""")
            page.reload(wait_until="networkidle")
            page.evaluate("switchMainTab('settings')")
            settings = page.locator("#tab-settings")
            settings.locator("[data-settings-view='storage']").click()
            settings.locator("#settingsResetBtn").click()

            saved = page.evaluate("JSON.parse(localStorage.getItem('pe_looks') || '[]')")
            history = page.evaluate("JSON.parse(localStorage.getItem('pe_history') || '[]')")
            self.assertEqual([item["id"] for item in saved], ["keep-on-cancel"])
            self.assertEqual([item["id"] for item in history], ["history-on-cancel"])
            self.assertTrue(settings.locator("[data-settings-panel='storage']").is_visible())
            browser.close()


    def test_settings_confirmed_reset_clears_local_data_and_reference_database(self):
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page(viewport={"width": 1280, "height": 900})
            page.on("dialog", lambda dialog: dialog.accept())
            page.goto(self.base_url, wait_until="networkidle")
            page.evaluate("""async () => {
                const keys = ["pe_looks", "pe_history", "pe_subjects", "pe_hairs", "pe_poses", "ape_projects", "ape_settings_v1", "ape_view_mode", "atelier_vision_lab_profiles_v1"];
                keys.forEach((key) => localStorage.setItem(key, JSON.stringify([{id:"reset-me"}])));
                await new Promise((resolve, reject) => {
                    const request = indexedDB.open("AtelierLibraryDB", 1);
                    request.onupgradeneeded = () => request.result.createObjectStore("references", {keyPath:"id"});
                    request.onsuccess = () => {
                        const db = request.result;
                        const tx = db.transaction("references", "readwrite");
                        tx.objectStore("references").put({id:"reference-reset-me", name:"reset-me"});
                        tx.oncomplete = () => { db.close(); resolve(); };
                        tx.onerror = () => reject(tx.error);
                    };
                    request.onerror = () => reject(request.error);
                });
            }""")
            page.reload(wait_until="networkidle")
            page.evaluate("switchMainTab('settings')")
            settings = page.locator("#tab-settings")
            settings.locator("[data-settings-view='storage']").click()
            with page.expect_navigation(wait_until="domcontentloaded"):
                settings.locator("#settingsResetBtn").click()
            page.wait_for_function("() => localStorage.getItem('pe_looks') === null && localStorage.getItem('pe_history') === null")
            remaining_keys = page.evaluate("""() => ["pe_looks", "pe_history", "pe_subjects", "pe_hairs", "pe_poses", "ape_projects", "ape_settings_v1", "ape_view_mode", "atelier_vision_lab_profiles_v1"].filter((key) => localStorage.getItem(key) !== null)""")
            databases = page.evaluate("indexedDB.databases().then(items => items.map(item => item.name))")
            self.assertEqual(remaining_keys, [])
            self.assertNotIn("AtelierLibraryDB", databases)
            browser.close()


    def test_library_bulk_selection_only_affects_current_filtered_items(self):
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page(viewport={"width": 1280, "height": 900})
            page.goto(self.base_url, wait_until="networkidle")
            page.evaluate("""() => {
                localStorage.setItem("pe_looks", JSON.stringify([
                    {id:"alpha-one", name:"Alpha one", prompt:"First alpha"},
                    {id:"alpha-two", name:"Alpha two", prompt:"Second alpha"},
                    {id:"beta-one", name:"Beta one", prompt:"Only beta"}
                ]));
                localStorage.setItem("pe_history", JSON.stringify([
                    {id:"history-alpha", name:"Alpha history", prompt:"Alpha history prompt"},
                    {id:"history-beta", name:"Beta history", prompt:"Beta history prompt"}
                ]));
            }""")
            page.reload(wait_until="networkidle")
            page.evaluate("switchMainTab('library')")
            library = page.locator("#tab-library")

            search = library.locator("#librarySearch")
            search.fill("Alpha")
            select_all = library.locator("#librarySelectAllPrompts")
            select_all.check()
            self.assertEqual(library.locator("#libraryPromptList input[type='checkbox']:checked").count(), 2)

            search.fill("Beta")
            visible_prompt_checks = library.locator("#libraryPromptList input[type='checkbox']")
            self.assertEqual(visible_prompt_checks.count(), 1)
            self.assertFalse(visible_prompt_checks.first.is_checked())
            visible_prompt_checks.first.check()
            library.locator("#libraryBulkFavoriteBtn").click()
            prompts = page.evaluate("JSON.parse(localStorage.getItem('pe_looks'))")
            favorites = {item["id"]: item.get("favorite", False) for item in prompts}
            self.assertFalse(favorites["alpha-one"])
            self.assertFalse(favorites["alpha-two"])
            self.assertTrue(favorites["beta-one"])

            history_tab = library.get_by_role("tab", name="History")
            history_tab.click()
            history_search = library.locator("#libraryHistorySearch")
            history_search.fill("Alpha")
            library.locator("#librarySelectAllHistory").check()
            self.assertEqual(library.locator("#libraryHistoryList input[type='checkbox']:checked").count(), 1)
            history_search.fill("Beta")
            visible_history_checks = library.locator("#libraryHistoryList input[type='checkbox']")
            self.assertEqual(visible_history_checks.count(), 1)
            self.assertFalse(visible_history_checks.first.is_checked())
            visible_history_checks.first.check()
            page.on("dialog", lambda dialog: dialog.accept())
            library.locator("#libraryBulkDeleteHistory").click()
            remaining_history = page.evaluate("JSON.parse(localStorage.getItem('pe_history'))")
            self.assertEqual([item["id"] for item in remaining_history], ["history-alpha"])
            browser.close()

    def test_prompt_and_history_select_all_track_individual_selection(self):
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page(viewport={"width": 1280, "height": 900})
            page.goto(self.base_url, wait_until="networkidle")
            page.evaluate("""() => {
                localStorage.setItem("pe_looks", JSON.stringify([
                    {id:"prompt-one", name:"Prompt one", prompt:"First prompt"},
                    {id:"prompt-two", name:"Prompt two", prompt:"Second prompt"}
                ]));
                localStorage.setItem("pe_history", JSON.stringify([
                    {id:"history-one", name:"History one", prompt:"First history"},
                    {id:"history-two", name:"History two", prompt:"Second history"}
                ]));
            }""")
            page.reload(wait_until="networkidle")
            page.evaluate("switchMainTab('library')")
            library = page.locator("#tab-library")

            prompt_master = library.locator("#librarySelectAllPrompts")
            prompt_cards = library.locator("#libraryPromptList input[type='checkbox']")
            prompt_master.check()
            self.assertTrue(prompt_master.is_checked())
            prompt_cards.first.uncheck()
            self.assertFalse(prompt_master.is_checked())
            self.assertTrue(prompt_master.evaluate("(element) => element.indeterminate"))
            prompt_cards.first.check()
            self.assertTrue(prompt_master.is_checked())

            library.get_by_role("tab", name="History").click()
            history_master = library.locator("#librarySelectAllHistory")
            history_cards = library.locator("#libraryHistoryList input[type='checkbox']")
            history_master.check()
            self.assertTrue(history_master.is_checked())
            history_cards.first.uncheck()
            self.assertFalse(history_master.is_checked())
            self.assertTrue(history_master.evaluate("(element) => element.indeterminate"))
            history_cards.first.check()
            self.assertTrue(history_master.is_checked())
            browser.close()

    def test_reference_upload_limit_counts_only_valid_images(self):
        import base64
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page(viewport={"width": 1280, "height": 900})
            page.goto(self.base_url, wait_until="networkidle")
            page.evaluate("switchMainTab('library')")
            library = page.locator("#tab-library")
            library.get_by_role("tab", name="Reference Library").click()
            valid_png = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+nmN8AAAAASUVORK5CYII=")
            library.locator("#libraryReferenceUpload").set_input_files([
                {"name":f"existing-{index}.png", "mimeType":"image/png", "buffer":valid_png}
                for index in range(99)
            ])
            page.wait_for_function("""async () => {
                const request = indexedDB.open("AtelierLibraryDB", 1);
                return await new Promise(resolve => {
                    request.onsuccess = () => {
                        const db = request.result;
                        const tx = db.transaction("references", "readonly");
                        const count = tx.objectStore("references").count();
                        count.onsuccess = () => { const value = count.result; db.close(); resolve(value === 99); };
                        count.onerror = () => { db.close(); resolve(false); };
                    };
                    request.onerror = () => resolve(false);
                });
            }""")
            library.locator("#libraryReferenceUpload").set_input_files([
                {"name":"invalid.gif", "mimeType":"image/gif", "buffer":b"GIF89a"},
                {"name":"valid.png", "mimeType":"image/png", "buffer":valid_png}
            ])
            page.wait_for_function("""async () => {
                const databases = await indexedDB.databases();
                if (!databases.some(item => item.name === "AtelierLibraryDB")) return false;
                return await new Promise(resolve => {
                    const request = indexedDB.open("AtelierLibraryDB", 1);
                    request.onsuccess = () => {
                        const db = request.result;
                        const tx = db.transaction("references", "readonly");
                        const count = tx.objectStore("references").count();
                        count.onsuccess = () => { const value = count.result; db.close(); resolve(value === 100); };
                        count.onerror = () => { db.close(); resolve(false); };
                    };
                    request.onerror = () => resolve(false);
                });
            }""")
            self.assertIn("1 reference image(s) saved", library.locator("#libraryStatus").inner_text())
            browser.close()

    def test_reference_bulk_delete_storage_failure_is_reported_without_page_error(self):
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page(viewport={"width": 1280, "height": 900})
            page_errors = []
            page.on("pageerror", lambda error: page_errors.append(str(error)))
            page.on("dialog", lambda dialog: dialog.accept())
            page.goto(self.base_url, wait_until="networkidle")
            page.evaluate("""async () => {
                await new Promise((resolve, reject) => {
                    const request = indexedDB.open("AtelierLibraryDB", 1);
                    request.onupgradeneeded = () => request.result.createObjectStore("references", {keyPath:"id"});
                    request.onsuccess = () => {
                        const db = request.result;
                        const tx = db.transaction("references", "readwrite");
                        tx.objectStore("references").put({
                            id:"delete-failure-reference", name:"Failure test",
                            type:"image/png", size:1, createdAt:new Date().toISOString(),
                            blob:new Blob(["x"], {type:"image/png"})
                        });
                        tx.oncomplete = () => { db.close(); resolve(); };
                        tx.onerror = () => { db.close(); reject(tx.error); };
                    };
                    request.onerror = () => reject(request.error);
                });
            }""")
            page.evaluate("switchMainTab('library')")
            library = page.locator("#tab-library")
            library.get_by_role("tab", name="Reference Library").click()
            library.locator("#libraryReferenceList .library-reference-card").wait_for()
            library.locator("#libraryReferenceList input[type='checkbox']").check()
            page.evaluate("""() => {
                const original = IDBDatabase.prototype.transaction;
                IDBDatabase.prototype.transaction = function (storeName, mode) {
                    if (mode === "readwrite") throw new Error("simulated write failure");
                    return original.call(this, storeName, mode);
                };
            }""")
            library.locator("#libraryBulkDeleteReferences").click()
            page.wait_for_function("() => document.querySelector('#libraryStatus').textContent.includes('Could not delete selected reference images')")
            self.assertIn("simulated write failure", library.locator("#libraryStatus").inner_text())
            self.assertEqual(page_errors, [])
            browser.close()


    def test_reference_single_delete_storage_failure_is_reported_without_page_error(self):
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page(viewport={"width": 1280, "height": 900})
            page_errors = []
            page.on("pageerror", lambda error: page_errors.append(str(error)))
            page.goto(self.base_url, wait_until="networkidle")
            page.evaluate("""async () => {
                await new Promise((resolve, reject) => {
                    const request = indexedDB.open("AtelierLibraryDB", 1);
                    request.onupgradeneeded = () => request.result.createObjectStore("references", {keyPath:"id"});
                    request.onsuccess = () => {
                        const db = request.result;
                        const tx = db.transaction("references", "readwrite");
                        tx.objectStore("references").put({
                            id:"single-delete-failure", name:"Single delete failure",
                            type:"image/png", size:1, createdAt:new Date().toISOString(),
                            blob:new Blob(["x"], {type:"image/png"})
                        });
                        tx.oncomplete = () => { db.close(); resolve(); };
                        tx.onerror = () => { db.close(); reject(tx.error); };
                    };
                    request.onerror = () => reject(request.error);
                });
            }""")
            page.evaluate("switchMainTab('library')")
            library = page.locator("#tab-library")
            library.get_by_role("tab", name="Reference Library").click()
            card = library.locator("#libraryReferenceList .library-reference-card")
            card.wait_for()
            page.evaluate("""() => {
                const original = IDBDatabase.prototype.transaction;
                IDBDatabase.prototype.transaction = function (storeName, mode) {
                    if (mode === "readwrite") throw new Error("simulated single delete failure");
                    return original.call(this, storeName, mode);
                };
            }""")
            card.get_by_role("button", name="Delete").click()
            page.wait_for_function("() => document.querySelector('#libraryStatus').textContent.includes('Could not delete reference image')")
            self.assertIn("simulated single delete failure", library.locator("#libraryStatus").inner_text())
            self.assertEqual(page_errors, [])
            browser.close()


    def test_reference_select_all_state_tracks_individual_selection_and_deletion(self):
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page(viewport={"width": 1280, "height": 900})
            page.goto(self.base_url, wait_until="networkidle")
            page.evaluate("""async () => {
                await new Promise((resolve, reject) => {
                    const request = indexedDB.open("AtelierLibraryDB", 1);
                    request.onupgradeneeded = () => request.result.createObjectStore("references", {keyPath:"id"});
                    request.onsuccess = () => {
                        const db = request.result;
                        const tx = db.transaction("references", "readwrite");
                        const store = tx.objectStore("references");
                        ["reference-one", "reference-two"].forEach((id) => store.put({
                            id, name:id, type:"image/png", size:1,
                            createdAt:new Date().toISOString(),
                            blob:new Blob(["x"], {type:"image/png"})
                        }));
                        tx.oncomplete = () => { db.close(); resolve(); };
                        tx.onerror = () => { db.close(); reject(tx.error); };
                    };
                    request.onerror = () => reject(request.error);
                });
            }""")
            page.evaluate("switchMainTab('library')")
            library = page.locator("#tab-library")
            library.get_by_role("tab", name="Reference Library").click()
            cards = library.locator("#libraryReferenceList .library-reference-card")
            cards.first.wait_for()
            master = library.locator("#librarySelectAllReferences")
            master.check()
            page.wait_for_function("""() => document.querySelector("#librarySelectAllReferences").checked && [...document.querySelectorAll("#libraryReferenceList .library-reference-card input[type='checkbox']")].every(input => input.checked)""")
            page.wait_for_timeout(200)
            cards.first.locator("input[type='checkbox']").uncheck()
            page.wait_for_function("""() => { const master = document.querySelector("#tab-library #librarySelectAllReferences"); return !master.checked && master.indeterminate; }""")
            page.wait_for_timeout(100)
            self.assertFalse(master.evaluate("(element) => element.checked"))
            self.assertTrue(master.evaluate("(element) => element.indeterminate"))
            cards.first.locator("input[type='checkbox']").check()
            page.wait_for_function("document.querySelector('#librarySelectAllReferences').checked")
            self.assertTrue(master.is_checked())
            cards.first.get_by_role("button", name="Delete").click()
            page.wait_for_function("document.querySelector('#librarySelectAllReferences').checked && document.querySelectorAll('#libraryReferenceList .library-reference-card').length === 1")
            self.assertTrue(master.is_checked())
            self.assertEqual(cards.count(), 1)
            browser.close()


if __name__ == "__main__":
    unittest.main()
