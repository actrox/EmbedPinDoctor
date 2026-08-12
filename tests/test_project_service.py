import unittest
from pathlib import Path

from app.project_service import ProjectService


ROOT = Path(__file__).resolve().parents[1]


class TestProjectService(unittest.TestCase):
    def setUp(self):
        self.service = ProjectService(ROOT / "data")
        self.payload = {"chip_id": "stm32f103c8t6", "module_ids": ["oled_i2c", "button"]}

    def test_hardware_tiers_are_exposed(self):
        chips = {item["id"]: item for item in self.service.list_chips()}
        self.assertEqual(chips["stm32f103c8t6"]["tier"], "verified")
        self.assertEqual(chips["nrf52840"]["tier"], "experimental")

    def test_solver_performance_and_cache(self):
        first = self.service.build_project(self.payload)
        second = self.service.build_project(self.payload)
        self.assertIn("elapsed_ms", first["solver"])
        self.assertFalse(first["solver"]["cache_hit"])
        self.assertTrue(second["solver"]["cache_hit"])


if __name__ == "__main__":
    unittest.main()
