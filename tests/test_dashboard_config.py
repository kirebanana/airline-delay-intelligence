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
        self.assertEqual(config["theme"]["dataframeHeaderTextColor"], "#16354A")

    def test_caption_chart_and_table_header_contrast(self):
        def luminance(color):
            rgb = [int(color[i : i + 2], 16) / 255 for i in (1, 3, 5)]
            rgb = [v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in rgb]
            return sum(v * w for v, w in zip(rgb, (0.2126, 0.7152, 0.0722), strict=True))

        for text, background in [
            ("#475569", "#FFFFFF"),
            ("#475569", "#EFF8FD"),
            ("#334155", "#FFFFFF"),
            ("#16354A", "#E3F3FA"),
        ]:
            self.assertGreaterEqual((luminance(background) + 0.05) / (luminance(text) + 0.05), 4.5)
