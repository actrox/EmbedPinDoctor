import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class TestWebAssets(unittest.TestCase):
    def test_bilingual_and_demo_assets_are_wired(self):
        html = (ROOT / "web/index.html").read_text(encoding="utf-8")
        app = (ROOT / "web/app.js").read_text(encoding="utf-8")
        translations = (ROOT / "web/i18n.js").read_text(encoding="utf-8")
        self.assertIn('id="languageSelect"', html)
        self.assertIn("./i18n.js", html)
        self.assertIn("./demo.js", html)
        self.assertIn("./views.js", html)
        self.assertIn("./examples.js", html)
        self.assertIn('hostname.endsWith("github.io")', app)
        self.assertIn("Give your hardware a", translations)

    def test_readmes_and_screenshot_targets_exist(self):
        self.assertTrue((ROOT / "README.md").exists())
        self.assertTrue((ROOT / "README_EN.md").exists())
        self.assertTrue((ROOT / "docs/images/workbench-zh.png").exists())
        self.assertTrue((ROOT / "docs/images/workbench-en.png").exists())
        self.assertTrue((ROOT / "web/generated/demo-data.json").exists())


if __name__ == "__main__":
    unittest.main()
