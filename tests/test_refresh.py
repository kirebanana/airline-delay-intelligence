import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


class RefreshRequestTests(unittest.TestCase):
    def test_complete_baseline_cannot_skip_its_required_weather_at_publication(self):
        from airline_warehouse.publication import publish

        months = {f"{y}-{m:02d}": "a" * 64 for y in range(2023, 2026) for m in range(1, 13)}
        candidate = dict(
            sealed=True,
            schema="WORK_" + "A" * 24,
            expected_rows=36,
            inputs=months,
            source_kinds={m: "official-local-import" for m in months},
        )
        with self.assertRaisesRegex(ValueError, "weather"):
            publish(None, {"target": "january"}, candidate, "b" * 32)

    def test_synthetic_inputs_cannot_replace_the_presenter_release(self):
        from test_prepare import archive

        from airline_warehouse.prepare import prepare
        from airline_warehouse.refresh import refresh

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            archive(root / "source.zip", [{}])
            prepare(root / "source.zip", root / "artifact", "2025-01", synthetic=True)
            with patch(
                "airline_warehouse.refresh.connect_as", side_effect=AssertionError("No cloud")
            ):
                with self.assertRaisesRegex(ValueError, "Synthetic"):
                    refresh(
                        [root / "artifact"],
                        root / "attempt",
                        root / "budget.json",
                        "january",
                        "a" * 32,
                    )
            self.assertFalse((root / "attempt").exists())

    def test_publisher_also_refuses_synthetic_serving_candidate_before_sql(self):
        from airline_warehouse.publication import publish

        candidate = dict(
            sealed=True,
            schema="WORK_" + "A" * 24,
            expected_rows=1,
            inputs={"2025-01": "a" * 64},
            source_kinds={"2025-01": "synthetic-fixture"},
        )
        with self.assertRaisesRegex(ValueError, "Synthetic"):
            publish(None, {"target": "january"}, candidate, "b" * 32)

    def test_incompatible_processing_or_preparation_never_enters_live_refresh(self):
        from test_prepare import archive

        from airline_warehouse.prepare import prepare
        from airline_warehouse.refresh import refresh

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive(root / "source.zip", [{}])
            prepare(root / "source.zip", root / "artifact", "2025-01", synthetic=True)
            candidate = root / "candidate.json"
            candidate.write_text(
                json.dumps(
                    {
                        "sealed": True,
                        "schema": "WORK_" + "A" * 24,
                        "processing_contract": "obsolete",
                    }
                )
            )
            with self.assertRaisesRegex(ValueError, "incompatible"):
                refresh(
                    [root / "artifact"],
                    root / "attempt",
                    root / "budget.json",
                    "january",
                    "a" * 32,
                    stage="publish",
                    candidate_path=candidate,
                )
            self.assertFalse((root / "attempt").exists())
            manifest_path = root / "artifact/manifest.json"
            manifest = json.loads(manifest_path.read_text())
            manifest["preparation_contract"] = "unsupported-preparation-v2"
            manifest_path.write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError, "Unsupported"):
                refresh(
                    [root / "artifact"], root / "attempt", root / "budget.json", "january", "b" * 32
                )
            self.assertFalse((root / "attempt").exists())

    def test_publish_rerun_refuses_missing_dependency_without_connecting(self):
        from airline_warehouse.refresh import refresh

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaisesRegex(ValueError, "candidate dependency"):
                refresh(
                    [], root / "attempt", root / "budget.json", "january", "a" * 32, stage="publish"
                )
            self.assertFalse((root / "attempt").exists())
