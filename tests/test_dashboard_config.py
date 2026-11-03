import tomllib
import unittest
from pathlib import Path


class DashboardConfigTests(unittest.TestCase):
    def test_light_theme_preserves_local_only_and_private_error_settings(self):
        config = tomllib.loads(
            (Path(__file__).resolve().parents[1] / ".streamlit/config.toml").read_text()
        )
        self.assertEqual(config["server"]["address"], "127.0.0.1")
        self.assertTrue(config["server"]["headless"])
        self.assertFalse(config["browser"]["gatherUsageStats"])
        self.assertEqual(config["client"]["showErrorDetails"], "none")
        self.assertEqual(config["theme"]["base"], "light")
        self.assertEqual(config["theme"]["backgroundColor"], "#FFFFFF")
